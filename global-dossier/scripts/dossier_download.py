#!/usr/bin/env python3
"""
Global Dossier 审查历史下载工具 v2.1
Usage:
  python3 dossier_download.py --number CN116621800B --mode single
  python3 dossier_download.py --number US11922587 --mode family
"""

# 跨平台：确保非 ASCII（中文/emoji）输出在 Windows GBK 控制台不崩溃
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8')
    _sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import argparse, os, re, sys, time, zipfile
from playwright.sync_api import sync_playwright

# ─── Configuration ──────────────────────────────────────────────
OUTPUT_BASE = os.path.join(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp")), "global_dossier_downloads")
DOC_DELAY = 4           # between individual document downloads
MEMBER_DELAY = 25       # between family members
SEARCH_GAP = 10         # between searches (CloudFront anti-throttle)
RETRY_DELAY = 90        # after 429 rate-limit
PAGE_TIMEOUT = 30000


# ═══════════════════════════════════════════════════════════════════
#  PAGE HELPERS
# ═══════════════════════════════════════════════════════════════════

def wait_angular(page):
    """Wait for Angular search form to be ready. Returns bool."""
    for attempt in range(20):
        if page.evaluate("""() => {
            const office = document.getElementById('country') || document.getElementById('office');
            return !!office && office.options.length >= 6;
        }"""):
            return True
        time.sleep(3)
        if attempt == 10:
            page.reload(wait_until="load", timeout=PAGE_TIMEOUT)
            time.sleep(8)
    return False


def angular_search(page, office, type_idx, query_str):
    """Search via Angular form. Must use Playwright native click for submit."""
    time.sleep(SEARCH_GAP)
    if not wait_angular(page):
        return False

    page.evaluate("""([o, t, q]) => {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        const office = document.getElementById('country') || document.getElementById('office');
        office.selectedIndex = o;
        office.dispatchEvent(new Event('change', {bubbles: true}));
        document.getElementById('type').selectedIndex = t;
        document.getElementById('type').dispatchEvent(new Event('change', {bubbles: true}));
        const el = document.getElementById('query');
        setter.call(el, q);
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur'));
    }""", [office, type_idx, query_str])
    time.sleep(2)

    try:
        page.click("button[name='search']", timeout=5000)
        time.sleep(12)
    except Exception:
        return False
    return '/home' not in page.url


def has_documents(page):
    """Check if current page has document rows."""
    return page.evaluate("document.querySelectorAll('tr td').length") >= 4


def go_to_dossier(page):
    """Navigate from publication/family/application page to a dossier page with documents.
    Returns True if documents are found."""
    url = page.url

    # Already on dossier page?
    if '/details/' in url:
        time.sleep(5)
        if 'ERROR' in page.evaluate("document.body.innerText"):
            return False
        if has_documents(page):
            return True
        # Try clicking "All Documents" tab
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('a, button, [role="tab"]')) {
                if (el.textContent.trim() === 'All Documents') { el.click(); return; }
            }
        }""")
        time.sleep(5)
        return has_documents(page)

    # Publication page (/result/publication/) → find /true All Documents link
    if '/result/publication/' in url or '/result/application/' in url:
        true_urls = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a'))
                .filter(a => a.href && a.href.includes('/details/') && a.href.endsWith('/true') && !a.href.includes('/officeActions/'))
                .map(a => a.href);
        }""")
        if true_urls:
            page.goto(true_urls[0], wait_until="load", timeout=PAGE_TIMEOUT)
            time.sleep(5)
            if 'ERROR' in page.evaluate("document.body.innerText"):
                return False
            return has_documents(page)

    # Family page (/result/patent/) → Expand → View Dossier → dossier page
    if '/result/' in url:
        page.evaluate("""() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.includes('Expand')) { a.click(); break; }
            }
        }""")
        time.sleep(4)
        try:
            page.click("a:has-text('View Dossier')", timeout=5000)
        except:
            return False
        time.sleep(8)
        if '429' in page.evaluate("document.body.innerText"):
            return False
        return has_documents(page)

    return False


# ═══════════════════════════════════════════════════════════════════
#  INPUT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════

def classify_input(raw):
    raw = raw.strip().upper()

    # CN pub: CN116621800B, CN119156243A
    m = re.match(r'^CN(\d{7,10})[ABUY]?\d*$', raw)
    if m: return (1, 1, m.group(1))

    # CN app: 202310575536
    m = re.match(r'^20(\d{10,11})$', raw)
    if m: return (1, 0, raw)

    # US granted: US11922587B2
    m = re.match(r'^US(\d{7,8})B\d$', raw)
    if m: return (0, 2, m.group(1))

    # US pre-grant: US20230368472A1
    m = re.match(r'^US(\d{10,11})A\d$', raw)
    if m: return (0, 1, m.group(1))

    # US bare: 11922587 or US11922587
    m = re.match(r'^(\d{7,8})$', raw)
    if m: return (0, 2, raw)
    m = re.match(r'^US(\d{7,11})$', raw)
    if m: return (0, 2, m.group(1))

    # EP (A-series pre-grant and B-series granted)
    m = re.match(r'^EP(\d{7,8})[AB]\d$', raw)
    if m: return (2, 1, m.group(1))
    m = re.match(r'^EP(\d{7,8})$', raw)
    if m: return (2, 1, m.group(1))

    # WO/PCT (A-series and B-series)
    m = re.match(r'^WO(\d{4})(\d{6})[AB]\d$', raw)
    if m: return (5, 1, m.group(1) + '/' + m.group(2))
    m = re.match(r'^WO(\d{4})(\d{6})$', raw)
    if m: return (5, 1, m.group(1) + '/' + m.group(2))
    m = re.match(r'^PCTUS(\d{7})$', raw)
    if m: return (5, 0, f"PCT/US{m.group(1)}")

    # CN bare pub
    m = re.match(r'^(\d{7,10})$', raw)
    if m: return (1, 1, raw)

    raise ValueError(f"Cannot classify: {raw}")


# ═══════════════════════════════════════════════════════════════════
#  PARSING & DOWNLOAD
# ═══════════════════════════════════════════════════════════════════

def parse_pub_number(page, orig_input=""):
    """Extract publication number from dossier page or URL.
    Falls back to original input if page has no pub number (common for CN)."""
    # 1. Try page text
    try:
        body = page.evaluate("document.body.innerText") or ""
    except:
        body = ""
    m = re.search(r'(\d{7,8})\s*B\d', body)
    if m: return f"US{m.group(1)}B2"
    m = re.search(r'US\s*(\d{10,11})\s*A\d', body)
    if m: return f"US{m.group(1)}A1"
    m = re.search(r'CN\s*(\d{7,10})\s*([AB])', body)
    if m: return f"CN{m.group(1)}{m.group(2)}"
    m = re.search(r'EP\s*(\d{7,8})\s*A\d', body)
    if m: return f"EP{m.group(1)}A1"
    m = re.search(r'WO\s*(\d{4})/(\d{6})\s*A\d', body)
    if m: return f"WO{m.group(1)}{m.group(2)}A1"
    
    # 2. Try URL extraction (/result/publication/CN/116621800/...)
    url = page.url
    m = re.search(r'/result/(?:publication|patent)/([A-Z]+)/([^/]+)/', url)
    if m:
        office, num = m.group(1), m.group(2)
        return f"{office}{num}"  # e.g. CN116621800
    
    # 3. Try URL on details page: /details/CN/{app_num}/...
    m = re.search(r'/details/([A-Z]+)/([^/]+)/', url)
    if m:
        office, app_num = m.group(1), m.group(2)
        # Prefer original input if it's a pub number for this office
        if orig_input:
            cleaned = re.sub(r'[^A-Z0-9]', '', orig_input.upper())
            if cleaned.startswith(office):
                return cleaned
        return f"{office}{app_num}"
    
    # 4. Use original input if it looks like a pub number
    if orig_input:
        cleaned = re.sub(r'[^A-Z0-9]', '', orig_input.upper())
        if re.match(r'^(CN|US|EP|WO|KR|JP)\d{7,}', cleaned):
            return cleaned
    
    return None


def get_document_list(page):
    return page.evaluate("""() => {
        const docs = [];
        for (const row of document.querySelectorAll('tr')) {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                const link = cells[1]?.querySelector('a');
                const desc = link ? link.textContent.trim() : '';
                const date = cells[2]?.textContent.trim() || '';
                if (desc && /\\d{2}\\/\\d{2}\\/\\d{4}/.test(date))
                    docs.push({desc, date});
            }
        }
        return docs;
    }""")


def click_doc_link(page, desc):
    return page.evaluate("""(d) => {
        for (const row of document.querySelectorAll('tr')) {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                const link = cells[1]?.querySelector('a');
                if (link && link.textContent.trim() === d) { link.click(); return true; }
            }
        }
        return false;
    }""", desc)


def download_all_docs(page, folder):
    docs = get_document_list(page)
    if not docs:
        return 0

    os.makedirs(folder, exist_ok=True)
    downloaded = 0

    for i, doc in enumerate(docs):
        safe = re.sub(r'[\\/*?:"<>|()\s,]+', '_', doc['desc'])[:70]
        fname = f"{i+1:02d}_{doc['date'].replace('/', '-')}_{safe}.pdf"
        fpath = os.path.join(folder, fname)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
            downloaded += 1
            continue

        if not click_doc_link(page, doc['desc']):
            continue

        try:
            d = page.wait_for_event("download", timeout=20000)
            d.save_as(fpath)
            downloaded += 1
            if downloaded <= 3 or downloaded % 10 == 0:
                print(f"  [{downloaded}/{len(docs)}] {os.path.getsize(fpath):>8}B {fname[:55]}")
        except:
            pass

        time.sleep(DOC_DELAY)

    return downloaded


def zip_folder(folder, pub):
    zp = os.path.join(OUTPUT_BASE, f"{pub}.zip")
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(folder)):
            if f.endswith('.pdf'):
                zf.write(os.path.join(folder, f), f"{pub}/{f}")
    return zp


# ═══════════════════════════════════════════════════════════════════
#  MODE A: Single patent
# ═══════════════════════════════════════════════════════════════════

def mode_single(page, office, type_idx, clean_number, orig_input):
    print(f"\n{'─'*60}")
    print(f"Mode A — Single  |  {orig_input}")
    print(f"  office={office} type={type_idx} query={clean_number}")

    page.goto("https://globaldossier.uspto.gov/home", wait_until="load", timeout=PAGE_TIMEOUT)
    if not angular_search(page, office, type_idx, clean_number):
        print("  ✗ Search failed")
        return None

    url = page.url
    print(f"  → {url}")

    # Special handling: search landed on family page — iterate members to match
    if '/result/patent/' in url:
        page.evaluate("""() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.includes('Expand')) { a.click(); break; }
            }
        }""")
        time.sleep(4)
        
        # Collect all View Dossier links
        dossier_links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a'))
                .filter(a => a.href && a.href.includes('/details/') && !a.href.includes('/officeActions/') && !a.href.endsWith('/true'))
                .map(a => a.href);
        }""")
        
        found = False
        for dl in dossier_links:
            page.goto(dl, wait_until="load", timeout=PAGE_TIMEOUT)
            time.sleep(6)
            body = page.evaluate("document.body.innerText")[:500]
            if '429' in body:
                time.sleep(RETRY_DELAY)
                page.goto(dl, wait_until="load", timeout=PAGE_TIMEOUT)
                time.sleep(6)
                body = page.evaluate("document.body.innerText")[:500]
            pub = parse_pub_number(page, orig_input)
            if pub and clean_number in pub:
                found = True
                break
            # Check if this member page already has docs
            if has_documents(page) and pub:
                # Accept if pub contains the query
                if clean_number in pub:
                    found = True
                    break
        
        if not found:
            print("  ✗ Cannot find matching member in family")
            return None

    if not go_to_dossier(page):
        print("  ✗ Cannot reach dossier")
        return None

    pub = parse_pub_number(page, orig_input) or orig_input.replace(' ', '')
    print(f"  Pub: {pub}")

    folder = os.path.join(OUTPUT_BASE, pub)
    count = download_all_docs(page, folder)
    if count == 0:
        print("  ✗ No documents")
        return None

    zp = zip_folder(folder, pub)
    print(f"  ✓ {count} docs → {pub}.zip ({os.path.getsize(zp)/1024:.0f}KB)")
    return zp


# ═══════════════════════════════════════════════════════════════════
#  MODE B: Full family
# ═══════════════════════════════════════════════════════════════════

def mode_family(page, office, type_idx, clean_number, orig_input):
    print(f"\n{'─'*60}")
    print(f"Mode B — Family  |  {orig_input}")
    print(f"  office={office} type={type_idx} query={clean_number}")

    page.goto("https://globaldossier.uspto.gov/home", wait_until="load", timeout=PAGE_TIMEOUT)
    if not angular_search(page, office, type_idx, clean_number):
        print("  ✗ Search failed")
        return []

    url = page.url
    print(f"  → {url}")

    # Check for multi-member family
    if '/result/patent/' not in url:
        member_cnt = page.evaluate("""() => {
            const m = document.body.innerText.match(/(\\d+)\\s+Members? in Patent Family/);
            return m ? parseInt(m[1]) : 1;
        }""")
        if member_cnt <= 1:
            print("  Single-member → Mode A")
            page.goto("https://globaldossier.uspto.gov/home", wait_until="load", timeout=PAGE_TIMEOUT)
            angular_search(page, office, type_idx, clean_number)
            r = mode_single(page, office, type_idx, clean_number, orig_input)
            return [r] if r else []

    # Expand all
    page.evaluate("""() => {
        for (const a of document.querySelectorAll('a')) {
            if (a.textContent.includes('Expand')) { a.click(); break; }
        }
    }""")
    time.sleep(4)

    # Extract members — get /true URLs + extract pub numbers from body text
    body = page.evaluate("document.body.innerText")
    
    # Extract all pub numbers after "Click to view publication number"
    # Format: "Click to view publication number\nUS 11922587 B2"
    pub_pattern = r'Click to view publication number\s*\n\s*([A-Z]{2})\s*(\d{4,11}(?:/\d{6})?)\s*([AB]\d?)'
    pub_matches = re.findall(pub_pattern, body)
    # Collapse to clean format, prefer B2 over A1 for same member
    all_pubs = []
    for o, n, s in pub_matches:
        pub_str = f"{o}{n.replace('/', '')}{s}"
        all_pubs.append(pub_str)
    
    # Remove consecutive A1+B2 pairs (keep B2 as granted)
    deduped_pubs = []
    i = 0
    while i < len(all_pubs):
        if i+1 < len(all_pubs) and all_pubs[i].endswith('A1') and all_pubs[i+1].endswith('B2'):
            # Same member: A1 pre-grant + B2 granted → keep B2
            deduped_pubs.append(all_pubs[i+1])
            i += 2
        else:
            deduped_pubs.append(all_pubs[i])
            i += 1
    
    # Extract /true links
    raw = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a'))
            .filter(a => a.href && a.href.includes('/details/') && a.href.endsWith('/true') && !a.href.includes('/officeActions/'))
            .map(a => { const m = a.href.match(/\\/details\\/([A-Z]+)\\/([^\\/]+)\\//); return m ? {office: m[1], app: m[2], url: a.href} : null; })
            .filter(x => x);
    }""")

    seen = set()
    family = []
    for m in raw:
        key = f"{m['office']}/{m['app']}"
        if key in seen: continue
        seen.add(key)
        family.append({'url': m['url'], 'office': m['office'], 'app': m['app']})

    # Assign pub numbers to family members (same order)
    for i, m in enumerate(family):
        if i < len(deduped_pubs):
            m['pub'] = deduped_pubs[i]

    print(f"  Family: {len(family)} members")
    for i, m in enumerate(family):
        pub_label = f" → {m.get('pub', '?')}" 
        print(f"    [{i+1}] {m['office']} {m['app']}{pub_label}")

    if not family:
        return []

    results = []
    for i, member in enumerate(family):
        print(f"\n  ── [{i+1}/{len(family)}] {member['office']} {member['app']} ──")

        page.goto(member['url'], wait_until="load", timeout=PAGE_TIMEOUT)
        time.sleep(6)

        body = page.evaluate("document.body.innerText")[:300]
        for retry in range(2):
            if '429' in body or 'ERROR' in body:
                wait = RETRY_DELAY * (retry + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                page.goto(member['url'], wait_until="load", timeout=PAGE_TIMEOUT)
                time.sleep(6)
                body = page.evaluate("document.body.innerText")[:300]

        if '429' in body or 'ERROR' in body or 'No Documents' in body:
            print("    ✗ Skipping")
            continue

        if not has_documents(page):
            print("    ✗ No document rows")
            continue

        pub = member.get('pub') or parse_pub_number(page, "") or f"{member['office']}{member['app']}"
        print(f"    Pub: {pub}")

        folder = os.path.join(OUTPUT_BASE, pub)
        count = download_all_docs(page, folder)
        if count > 0:
            zp = zip_folder(folder, pub)
            print(f"    ✓ {count} docs → {pub}.zip ({os.path.getsize(zp)/1024:.0f}KB)")
            results.append(zp)
        else:
            print("    ✗ No documents")

        if i < len(family) - 1:
            time.sleep(MEMBER_DELAY)

    return results


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global OUTPUT_BASE

    p = argparse.ArgumentParser(description="Global Dossier download")
    p.add_argument("--number", "-n", required=True)
    p.add_argument("--mode", "-m", choices=["single", "family"], default="single")
    p.add_argument("--output", "-o", default=OUTPUT_BASE)
    args = p.parse_args()

    OUTPUT_BASE = args.output
    os.makedirs(OUTPUT_BASE, exist_ok=True)

    try:
        office, type_idx, clean_number = classify_input(args.number)
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)

    print(f"Global Dossier v2.1")
    print(f"  mode={args.mode} input={args.number} o={office} t={type_idx} q={clean_number}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        try:
            if args.mode == "single":
                r = mode_single(page, office, type_idx, clean_number, args.number)
            else:
                r = mode_family(page, office, type_idx, clean_number, args.number)

            if r:
                print(f"\n{'='*60}")
                print("✓ Done")
                for pth in (r if isinstance(r, list) else [r]):
                    if pth:
                        print(f"  {pth}")
            else:
                print(f"\n{'='*60}")
                print("✗ Failed")
                sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
