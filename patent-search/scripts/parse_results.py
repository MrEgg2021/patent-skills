#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.dont_write_bytecode = True

PATENT_URL_RE = re.compile(r'https?://patents\.google\.com/patent/([A-Z0-9./-]+)', re.IGNORECASE)
PDF_URL_RE = re.compile(r'https?://patentimages\.storage\.googleapis\.com/[^\s)]+', re.IGNORECASE)
PUBLICATION_RE = re.compile(r'\b(?:CN|US|WO|EP|JP|KR|TW|AU|DE|FR|GB|CA|NL|RU|IN|SG|IL|DK|MX)[A-Z0-9./-]{5,}\b')
DATE_RE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
SORT_MODE_RE = re.compile(r'Sort by\s*[·:]\s*([A-Za-z ]+)', re.IGNORECASE)

FIELD_ALIASES = {
    'title': ['title', 'name'],
    'publication_number': ['publication_number', 'publicationNumber', 'pub_number', 'publication', 'patent_number'],
    'applicant': ['applicant', 'assignee', 'owner'],
    'inventor': ['inventor', 'inventors'],
    'snippet': ['snippet', 'summary', 'abstract', 'description'],
    'abstract': ['abstract', 'snippet', 'summary', 'description'],
    'url': ['url', 'link', 'href'],
    'pdf_url': ['pdf_url', 'pdfUrl'],
    'query_set_name': ['query_set_name', 'strategy_name'],
    'source_sort_mode': ['source_sort_mode', 'sort_mode'],
    'family_countries': ['family_countries', 'familyCountries'],
    'priority_date': ['priority_date', 'priorityDate'],
    'filing_date': ['filing_date', 'filingDate'],
    'publication_date': ['publication_date', 'publicationDate'],
    'grant_date': ['grant_date', 'grantDate'],
    'matched_scope': ['matched_scope'],
    'match_notes': ['match_notes'],
}


def read_text_flexible(path: Path) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    raise UnicodeDecodeError('codec', b'', 0, 1, f'cannot decode {path}')


def maybe_json(text: str) -> Any:
    stripped = text.lstrip()
    if not stripped.startswith('{') and not stripped.startswith('['):
        raise ValueError('not json')
    return json.loads(text)


def first_value(data: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        value = data.get(alias)
        if value not in (None, '', []):
            return value
    return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        parts = [clean_text(item) for item in value]
        text = '; '.join(part for part in parts if part)
        return text or None
    text = str(value).strip()
    return text or None


def infer_matched_scope(query: str | None) -> str:
    if not query:
        return 'unknown'
    scopes: list[str] = []
    if 'TI=' in query:
        scopes.append('title')
    if 'AB=' in query:
        scopes.append('abstract')
    if 'CL=' in query:
        scopes.append('claims')
    return ','.join(scopes) if scopes else 'full_text'


def parse_family_countries(text: str) -> tuple[str | None, bool]:
    if not text:
        return None, False
    prefix = text.split('•', 1)[0].strip()
    countries = [token for token in prefix.split() if re.fullmatch(r'[A-Z]{2}', token)]
    if not countries:
        return None, False
    joined = ' '.join(countries)
    return joined, 'CN' in countries


def normalize_date_map(result: dict[str, Any]) -> None:
    if not result.get('date'):
        for key in ['publication_date', 'filing_date', 'priority_date', 'grant_date']:
            if result.get(key):
                result['date'] = result[key]
                break


def normalize_result(item: dict[str, Any], query: str | None = None, source_sort_mode: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for target_key, aliases in FIELD_ALIASES.items():
        value = clean_text(first_value(item, aliases))
        if value:
            result[target_key] = value

    if 'url' in result:
        match = PATENT_URL_RE.search(result['url'])
        if match and 'publication_number' not in result:
            result['publication_number'] = match.group(1)

    if 'publication_number' not in result:
        for candidate in item.values():
            candidate_text = clean_text(candidate)
            if not candidate_text:
                continue
            match = PUBLICATION_RE.search(candidate_text)
            if match:
                result['publication_number'] = match.group(0)
                break

    if 'publication_number' in result and 'url' not in result:
        result['url'] = f'https://patents.google.com/patent/{result["publication_number"]}'

    if result.get('publication_number'):
        result['country_code'] = result['publication_number'][:2]

    family_countries, has_cn_family = parse_family_countries(result.get('family_countries', ''))
    if family_countries:
        result['family_countries'] = family_countries
    if has_cn_family:
        result['has_cn_family'] = True

    for date_key in ['priority_date', 'filing_date', 'publication_date', 'grant_date']:
        if result.get(date_key):
            match = DATE_RE.search(result[date_key])
            if match:
                result[date_key] = match.group(0)

    if result.get('pdf_url'):
        pdf_match = PDF_URL_RE.search(result['pdf_url'])
        if pdf_match:
            result['pdf_url'] = pdf_match.group(0)

    result.setdefault('query_set_name', item.get('query_set_name') or 'unknown')
    result.setdefault('source_sort_mode', source_sort_mode or item.get('source_sort_mode') or 'unknown')
    result.setdefault('matched_scope', item.get('matched_scope') or infer_matched_scope(query))
    result.setdefault('match_notes', item.get('match_notes') or 'Normalized from structured search results.')
    if 'snippet' in result and 'abstract' not in result:
        result['abstract'] = result['snippet']
    normalize_date_map(result)

    if 'title' in result or 'publication_number' in result:
        return result
    return {}


def iter_candidate_dicts(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        score_keys = sum(1 for aliases in FIELD_ALIASES.values() for alias in aliases if alias in node)
        contains_patent_url = any(
            isinstance(value, str) and 'patents.google.com/patent/' in value
            for value in node.values()
        )
        if score_keys >= 2 or contains_patent_url:
            yield node
        for value in node.values():
            yield from iter_candidate_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_candidate_dicts(item)


def dedupe_results(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for result in results:
        if not result:
            continue
        key = (result.get('publication_number'), result.get('url'), result.get('title'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def parse_json_payload(payload: Any, query: str | None, source_sort_mode: str | None) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get('results'), list):
        local_query = payload.get('query') or query
        local_sort = payload.get('source_sort_mode') or source_sort_mode
        return dedupe_results(normalize_result(item, local_query, local_sort) for item in payload['results'] if isinstance(item, dict))
    if isinstance(payload, list):
        return dedupe_results(normalize_result(item, query, source_sort_mode) for item in payload if isinstance(item, dict))
    return dedupe_results(normalize_result(item, query, source_sort_mode) for item in iter_candidate_dicts(payload))


def split_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r'\n\s*\n+', text) if block.strip()]
    return blocks if blocks else [text]


def parse_metadata_line(line: str, result: dict[str, Any]) -> None:
    family_countries, has_cn_family = parse_family_countries(line)
    if family_countries:
        result['family_countries'] = family_countries
    if has_cn_family:
        result['has_cn_family'] = True

    publication_match = PUBLICATION_RE.search(line)
    if publication_match:
        result['publication_number'] = publication_match.group(0)
        result.setdefault('url', f'https://patents.google.com/patent/{publication_match.group(0)}')

    bullets = [part.strip() for part in line.split('•') if part.strip()]
    if publication_match and bullets:
        without_country_tokens = [part for part in bullets if not re.fullmatch(r'[A-Z]{2}(?:\s+[A-Z]{2})*', part)]
        if len(without_country_tokens) >= 2 and 'inventor' not in result:
            result['inventor'] = without_country_tokens[1]
        if len(without_country_tokens) >= 3 and 'applicant' not in result:
            result['applicant'] = without_country_tokens[2]


def parse_date_line(line: str, result: dict[str, Any]) -> None:
    pairs = {
        'Priority': 'priority_date',
        'Filed': 'filing_date',
        'Published': 'publication_date',
        'Granted': 'grant_date',
    }
    for label, key in pairs.items():
        match = re.search(rf'{label}\s+(\d{{4}}-\d{{2}}-\d{{2}})', line, re.IGNORECASE)
        if match:
            result[key] = match.group(1)


def infer_result_from_block(block: str, query: str | None, source_sort_mode: str | None, query_set_name: str | None) -> dict[str, Any]:
    lines = [line.strip(' -\t') for line in block.splitlines() if line.strip()]
    result: dict[str, Any] = {
        'query_set_name': query_set_name or 'unknown',
        'source_sort_mode': source_sort_mode or 'unknown',
        'matched_scope': infer_matched_scope(query),
        'match_notes': 'Parsed from browser text snapshot.',
    }

    for line in lines:
        url_match = PATENT_URL_RE.search(line)
        if url_match:
            result['url'] = url_match.group(0)
            result.setdefault('publication_number', url_match.group(1))
        pdf_match = PDF_URL_RE.search(line)
        if pdf_match:
            result['pdf_url'] = pdf_match.group(0)

    if 'publication_number' not in result:
        publication_match = PUBLICATION_RE.search(block)
        if publication_match:
            result['publication_number'] = publication_match.group(0)
            result['url'] = f'https://patents.google.com/patent/{publication_match.group(0)}'

    for line in lines:
        lowered = line.lower()
        if line.startswith('http'):
            continue
        if lowered.startswith('sort by'):
            continue
        if '•' in line and result.get('publication_number'):
            parse_metadata_line(line, result)
            if 'Priority ' in line or 'Filed ' in line or 'Published ' in line or 'Granted ' in line:
                parse_date_line(line, result)
            continue
        if 'Priority ' in line or 'Filed ' in line or 'Published ' in line or 'Granted ' in line:
            parse_date_line(line, result)
            continue
        if lowered.startswith(('inventor:', 'inventors:')):
            result['inventor'] = line.split(':', 1)[1].strip()
            continue
        if lowered.startswith(('assignee:', 'applicant:', 'owner:')):
            result['applicant'] = line.split(':', 1)[1].strip()
            continue
        if 'title' not in result and not PUBLICATION_RE.search(line):
            result['title'] = line
            continue
        if 'snippet' not in result and len(line) > 40:
            result['snippet'] = line
            result.setdefault('abstract', line)

    if 'publication_number' in result:
        result['country_code'] = result['publication_number'][:2]
    normalize_date_map(result)
    if 'title' in result or 'publication_number' in result:
        return result
    return {}


def infer_source_sort_mode(text: str, explicit_sort_mode: str | None) -> str | None:
    if explicit_sort_mode:
        return explicit_sort_mode
    match = SORT_MODE_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def parse_text_payload(text: str, query: str | None, explicit_sort_mode: str | None, query_set_name: str | None) -> list[dict[str, Any]]:
    source_sort_mode = infer_source_sort_mode(text, explicit_sort_mode)
    return dedupe_results(
        infer_result_from_block(block, query, source_sort_mode, query_set_name)
        for block in split_blocks(text)
    )


def parse_input(path: Path, source_format: str, query: str | None, source_sort_mode: str | None, query_set_name: str | None) -> list[dict[str, Any]]:
    text = read_text_flexible(path)
    if source_format in {'auto', 'json'}:
        try:
            return parse_json_payload(maybe_json(text), query, source_sort_mode)
        except Exception:
            if source_format == 'json':
                raise
    return parse_text_payload(text, query, source_sort_mode, query_set_name)


def build_output(path: Path, query: str | None, results: list[dict[str, Any]], source_sort_mode: str | None, query_set_name: str | None) -> dict[str, Any]:
    return {
        'query': query,
        'query_set_name': query_set_name,
        'source_sort_mode': source_sort_mode,
        'source_file': str(path),
        'total_results': len(results),
        'results': results,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Parse Google Patents search results from a browser snapshot or JSON export.')
    parser.add_argument('input', help='Path to a text snapshot or JSON file')
    parser.add_argument('-o', '--output', help='Optional output JSON path')
    parser.add_argument('--query', help='Search query string to embed in the output')
    parser.add_argument('--query-set-name', help='Optional query strategy name to embed in each row')
    parser.add_argument('--source-sort-mode', help='Optional source sort mode override')
    parser.add_argument('--source-format', choices=['auto', 'json', 'text'], default='auto')
    args = parser.parse_args()

    input_path = Path(args.input)
    results = parse_input(input_path, args.source_format, args.query, args.source_sort_mode, args.query_set_name)
    source_sort_mode = args.source_sort_mode
    if args.source_format != 'json':
        source_sort_mode = infer_source_sort_mode(read_text_flexible(input_path), args.source_sort_mode)
    payload = build_output(input_path, args.query, results, source_sort_mode, args.query_set_name)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Saved parsed results to: {output_path}')
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
