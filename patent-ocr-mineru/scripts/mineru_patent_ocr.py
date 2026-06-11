#!/usr/bin/env python3
"""Patent-oriented OCR parsing wrapper for MinerU.

The script keeps MinerU integration separate from patent-specific cleanup:
1. parse with MinerU precision API, Agent API, or local MinerU CLI;
2. collect Markdown / JSON outputs;
3. normalize patent sections, claims, figures, and material-formulation cues.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MINERU_PRECISION_BASE = "https://mineru.net/api/v4"
MINERU_AGENT_BASE = "https://mineru.net/api/v1/agent"
TOKEN_ENV_CANDIDATES = ("MINERU_API_TOKEN", "MINERU_TOKEN", "MINERU_API_KEY")

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".jp2",
    ".webp",
    ".gif",
    ".bmp",
    ".html",
}

PATENT_TERM_FIXES = {
    "说 明 书 摘 要": "说明书摘要",
    "说 明 书 附 图": "说明书附图",
    "摘 要 附 图": "摘要附图",
    "权 利 要 求 书": "权利要求书",
    "说 明 书": "说明书",
    "技 术 领 域": "技术领域",
    "背 景 技 术": "背景技术",
    "发 明 内 容": "发明内容",
    "实 用 新 型 内 容": "实用新型内容",
    "附 图 说 明": "附图说明",
    "具 体 实 施 方 式": "具体实施方式",
    "其 特 征 在 于": "其特征在于",
    "有 益 效 果": "有益效果",
    "技 术 方 案": "技术方案",
    "交 底 书": "交底书",
    "发 明 点": "发明点",
}

SECTION_RULES = [
    ("abstract", r"^(?:#*\s*)?(?:说明书摘要|摘要)\s*$"),
    ("claims", r"^(?:#*\s*)?(?:权利要求书|权利要求)\s*$"),
    ("description", r"^(?:#*\s*)?说明书\s*$"),
    ("technical_field", r"^(?:#*\s*)?技术领域\s*$"),
    ("background", r"^(?:#*\s*)?背景技术\s*$"),
    ("summary", r"^(?:#*\s*)?(?:发明内容|实用新型内容|发明概述)\s*$"),
    ("drawings_brief", r"^(?:#*\s*)?附图说明\s*$"),
    ("embodiments", r"^(?:#*\s*)?(?:具体实施方式|具体实施例|实施例)\s*$"),
    ("drawings", r"^(?:#*\s*)?(?:说明书附图|附图|摘要附图)\s*$"),
    ("disclosure_problem", r"^(?:#*\s*)?(?:技术问题|待解决的技术问题)\s*$"),
    ("disclosure_solution", r"^(?:#*\s*)?(?:技术方案|核心方案|方案说明)\s*$"),
    ("disclosure_effect", r"^(?:#*\s*)?(?:有益效果|技术效果|效果验证)\s*$"),
    ("material_formula", r"^(?:#*\s*)?(?:材料配方|组成|组分|配比|配方设计)\s*$"),
    ("test_data", r"^(?:#*\s*)?(?:实验数据|性能测试|测试结果|实施例数据)\s*$"),
]

SECTION_LABELS = {
    "abstract": "说明书摘要",
    "claims": "权利要求书",
    "description": "说明书",
    "technical_field": "技术领域",
    "background": "背景技术",
    "summary": "发明内容",
    "drawings_brief": "附图说明",
    "embodiments": "具体实施方式",
    "drawings": "说明书附图",
    "disclosure_problem": "技术问题",
    "disclosure_solution": "技术方案",
    "disclosure_effect": "有益效果",
    "material_formula": "材料配方",
    "test_data": "实验数据",
}

MATERIAL_TERMS = [
    "胶底",
    "橡胶",
    "树脂",
    "聚氨酯",
    "EVA",
    "TPU",
    "TPE",
    "PVC",
    "硫化",
    "发泡",
    "填料",
    "碳黑",
    "白炭黑",
    "重量份",
    "质量份",
    "wt%",
    "mol%",
    "硬度",
    "邵氏",
    "拉伸",
    "断裂伸长率",
    "耐磨",
    "磨耗",
    "剥离",
    "回弹",
    "粒径",
    "交联",
]


@dataclass
class ParseContext:
    source: str
    service: str
    profile: str
    output_dir: Path
    language: str
    model_version: str
    is_ocr: bool
    enable_table: bool
    enable_formula: bool
    page_ranges: str | None
    extra_formats: list[str]
    data_id: str
    timeout: int
    interval: int


class MinerUError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def sanitize_data_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return clean[:128] or f"patent-ocr-{int(time.time())}"


def infer_ocr_flag(source: str, profile: str, mode: str) -> bool:
    if mode == "ocr":
        return True
    if mode == "text":
        return False
    suffix = Path(source).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp"}:
        return True
    return profile in {"scanned-patent", "drawings", "material-scan"}


def infer_model(source: str, profile: str, model: str | None) -> str:
    if model:
        return model
    if Path(source).suffix.lower() == ".html":
        return "MinerU-HTML"
    if profile in {"drawings", "material-scan", "scanned-patent"}:
        return "vlm"
    return "pipeline"


def get_token() -> str:
    for env_name in TOKEN_ENV_CANDIDATES:
        token = os.environ.get(env_name)
        if token:
            return token
    joined = ", ".join(TOKEN_ENV_CANDIDATES)
    raise MinerUError(f"Precision API requires token in one of: {joined}")


def http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    merged_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        merged_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=merged_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise MinerUError(f"HTTP {exc.code} for {url}: {raw[:500]}") from exc
    except urllib.error.URLError as exc:
        raise MinerUError(f"Network error for {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise MinerUError(f"Non-JSON response from {url}") from exc


def put_file(url: str, file_path: Path, timeout: int = 300) -> None:
    data = file_path.read_bytes()
    req = urllib.request.Request(url, data=data, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status not in (200, 201, 204):
                raise MinerUError(f"Upload failed with HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise MinerUError(f"Upload failed with HTTP {exc.code}: {raw[:500]}") from exc


def download_file(url: str, output_path: Path, timeout: int = 600) -> Path:
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        return output_path
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise MinerUError(f"Download failed with HTTP {exc.code}: {raw[:500]}") from exc


def require_success(result: dict[str, Any], operation: str) -> dict[str, Any]:
    if result.get("code") != 0:
        raise MinerUError(f"{operation} failed: {result.get('msg') or result}")
    return result.get("data") or {}


def precision_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_token()}",
    }


def build_precision_payload(ctx: ParseContext, file_item: dict[str, Any]) -> dict[str, Any]:
    if ctx.is_ocr:
        file_item["is_ocr"] = True
    if ctx.page_ranges:
        file_item["page_ranges"] = ctx.page_ranges
    payload: dict[str, Any] = {
        "files": [file_item],
        "model_version": ctx.model_version,
        "language": ctx.language,
        "enable_table": ctx.enable_table,
        "enable_formula": ctx.enable_formula,
    }
    if ctx.extra_formats:
        payload["extra_formats"] = ctx.extra_formats
    return payload


def poll_precision_batch(batch_id: str, ctx: ParseContext) -> dict[str, Any]:
    deadline = time.monotonic() + ctx.timeout
    url = f"{MINERU_PRECISION_BASE}/extract-results/batch/{batch_id}"
    last_state = "pending"
    while time.monotonic() < deadline:
        result = http_json("GET", url, headers=precision_headers(), timeout=60)
        data = require_success(result, "poll precision batch")
        items = data.get("extract_result") or []
        if items:
            item = items[0]
            state = item.get("state", "")
            if state != last_state:
                print(f"[mineru] state={state}", file=sys.stderr)
                last_state = state
            if state == "done":
                return item
            if state == "failed":
                raise MinerUError(f"MinerU precision parse failed: {item.get('err_msg')}")
        time.sleep(ctx.interval)
    raise MinerUError(f"Precision API polling timed out for batch_id={batch_id}")


def parse_precision(ctx: ParseContext) -> dict[str, Any]:
    if is_url(ctx.source):
        payload = build_precision_payload(ctx, {"url": ctx.source, "data_id": ctx.data_id})
        data = require_success(
            http_json(
                "POST",
                f"{MINERU_PRECISION_BASE}/extract/task/batch",
                payload=payload,
                headers=precision_headers(),
                timeout=60,
            ),
            "submit precision URL task",
        )
        batch_id = data["batch_id"]
    else:
        input_path = Path(ctx.source)
        if input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise MinerUError(f"Unsupported file suffix: {input_path.suffix}")
        payload = build_precision_payload(ctx, {"name": input_path.name, "data_id": ctx.data_id})
        data = require_success(
            http_json(
                "POST",
                f"{MINERU_PRECISION_BASE}/file-urls/batch",
                payload=payload,
                headers=precision_headers(),
                timeout=60,
            ),
            "apply precision upload URL",
        )
        batch_id = data["batch_id"]
        file_urls = data.get("file_urls") or []
        if not file_urls:
            raise MinerUError("MinerU did not return upload URL")
        put_file(file_urls[0], input_path, timeout=ctx.timeout)

    item = poll_precision_batch(batch_id, ctx)
    zip_url = item.get("full_zip_url")
    if not zip_url:
        raise MinerUError(f"Precision result missing full_zip_url: {item}")
    raw_dir = ensure_output_dir(ctx.output_dir / "mineru_raw")
    zip_path = download_file(zip_url, raw_dir / f"{ctx.data_id}.zip", timeout=ctx.timeout)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(raw_dir / "unzipped")
    return {
        "service": "precision",
        "batch_id": batch_id,
        "result": item,
        "zip_path": str(zip_path),
        "raw_dir": str(raw_dir / "unzipped"),
    }


def build_agent_payload(ctx: ParseContext, source_is_file: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "language": ctx.language,
        "enable_table": ctx.enable_table,
        "is_ocr": ctx.is_ocr,
        "enable_formula": ctx.enable_formula,
    }
    if ctx.page_ranges:
        # Agent API only supports one range or one page, but it names the field page_range.
        payload["page_range"] = ctx.page_ranges
    if source_is_file:
        payload["file_name"] = Path(ctx.source).name
    else:
        payload["url"] = ctx.source
        payload["file_name"] = Path(ctx.source).name
    return payload


def poll_agent(task_id: str, ctx: ParseContext) -> dict[str, Any]:
    deadline = time.monotonic() + ctx.timeout
    url = f"{MINERU_AGENT_BASE}/parse/{task_id}"
    last_state = "pending"
    while time.monotonic() < deadline:
        result = http_json("GET", url, timeout=60)
        data = require_success(result, "poll agent task")
        state = data.get("state", "")
        if state != last_state:
            print(f"[mineru-agent] state={state}", file=sys.stderr)
            last_state = state
        if state == "done":
            return data
        if state == "failed":
            raise MinerUError(f"MinerU Agent parse failed: {data.get('err_msg')}")
        time.sleep(ctx.interval)
    raise MinerUError(f"Agent API polling timed out for task_id={task_id}")


def parse_agent(ctx: ParseContext) -> dict[str, Any]:
    source_is_file = not is_url(ctx.source)
    endpoint = "file" if source_is_file else "url"
    payload = build_agent_payload(ctx, source_is_file)
    data = require_success(
        http_json("POST", f"{MINERU_AGENT_BASE}/parse/{endpoint}", payload=payload, timeout=60),
        f"submit agent {endpoint} task",
    )
    task_id = data["task_id"]
    if source_is_file:
        file_url = data.get("file_url")
        if not file_url:
            raise MinerUError("MinerU Agent did not return upload URL")
        put_file(file_url, Path(ctx.source), timeout=ctx.timeout)
    done = poll_agent(task_id, ctx)
    markdown_url = done.get("markdown_url")
    if not markdown_url:
        raise MinerUError(f"Agent result missing markdown_url: {done}")
    raw_dir = ensure_output_dir(ctx.output_dir / "mineru_raw")
    md_path = download_file(markdown_url, raw_dir / "full.md", timeout=ctx.timeout)
    return {
        "service": "agent",
        "task_id": task_id,
        "result": done,
        "markdown_path": str(md_path),
        "raw_dir": str(raw_dir),
    }


def parse_local(ctx: ParseContext) -> dict[str, Any]:
    if is_url(ctx.source):
        raise MinerUError("Local MinerU CLI mode requires a local file or directory")
    mineru = shutil.which("mineru")
    if not mineru:
        raise MinerUError("mineru CLI not found on PATH")
    method = "ocr" if ctx.is_ocr else "auto"
    raw_dir = ensure_output_dir(ctx.output_dir / "mineru_raw")
    command = [
        mineru,
        "-p",
        ctx.source,
        "-o",
        str(raw_dir),
        "-m",
        method,
        "-f",
        str(ctx.enable_formula).lower(),
        "-t",
        str(ctx.enable_table).lower(),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    (raw_dir / "mineru_cli_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (raw_dir / "mineru_cli_stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise MinerUError(f"mineru CLI failed with exit code {result.returncode}")
    return {
        "service": "local-cli",
        "command": command,
        "raw_dir": str(raw_dir),
    }


def find_first_file(root: Path, patterns: list[str]) -> Path | None:
    if root.is_file():
        return root
    for pattern in patterns:
        matches = sorted(root.rglob(pattern))
        if matches:
            return matches[0]
    return None


def load_markdown(raw_root: Path) -> tuple[str, Path | None]:
    md_path = find_first_file(raw_root, ["full.md", "*.md"])
    if not md_path:
        return "", None
    return md_path.read_text(encoding="utf-8", errors="replace"), md_path


def load_content_list(raw_root: Path) -> tuple[list[dict[str, Any]], Path | None]:
    content_path = find_first_file(raw_root, ["*_content_list.json", "*content_list*.json"])
    if not content_path:
        return [], None
    loaded = read_json(content_path)
    if isinstance(loaded, list):
        return loaded, content_path
    return [], content_path


def normalize_ocr_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"\r\n?", "\n", text)
    for wrong, right in PATENT_TERM_FIXES.items():
        text = text.replace(wrong, right)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + ("\n" if text.strip() else "")


def detect_sections(markdown: str) -> dict[str, dict[str, Any]]:
    lines = markdown.splitlines()
    markers: list[tuple[int, str, str]] = []
    compiled = [(name, re.compile(pattern)) for name, pattern in SECTION_RULES]
    for index, line in enumerate(lines):
        stripped = line.strip().strip("*").strip()
        for name, pattern in compiled:
            if pattern.match(stripped):
                markers.append((index, name, line.strip()))
                break

    sections: dict[str, dict[str, Any]] = {}
    for pos, (start, name, heading) in enumerate(markers):
        end = markers[pos + 1][0] if pos + 1 < len(markers) else len(lines)
        content = "\n".join(lines[start + 1 : end]).strip()
        if name not in sections or len(content) > len(sections[name].get("content", "")):
            sections[name] = {
                "heading": heading,
                "label": SECTION_LABELS.get(name, name),
                "start_line": start + 1,
                "end_line": end,
                "content": content,
            }
    if not sections and markdown:
        sections["unclassified"] = {
            "heading": "全文",
            "label": "全文",
            "start_line": 1,
            "end_line": len(lines),
            "content": markdown.strip(),
        }
    return sections


def extract_title(markdown: str, sections: dict[str, dict[str, Any]]) -> str:
    title_patterns = [
        r"(?:发明名称|实用新型名称|名称)[:：]\s*(.+)",
        r"^#\s*(.+)",
    ]
    for pattern in title_patterns:
        match = re.search(pattern, markdown, flags=re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value and len(value) <= 80:
                return value
    first_section = sections.get("abstract") or sections.get("description")
    if first_section:
        first_line = next((line.strip() for line in first_section["content"].splitlines() if line.strip()), "")
        return first_line[:80]
    return ""


def extract_claims(sections: dict[str, dict[str, Any]], markdown: str) -> list[dict[str, Any]]:
    claims_text = sections.get("claims", {}).get("content") or ""
    if not claims_text:
        match = re.search(r"权利要求书(.+?)(?:说明书|技术领域|$)", markdown, flags=re.S)
        if match:
            claims_text = match.group(1)
    claims_text = claims_text.strip()
    if not claims_text:
        return []

    pattern = re.compile(r"(?ms)^\s*(\d+)[\.、．]\s*(.+?)(?=^\s*\d+[\.、．]\s*|\Z)")
    claims = []
    for match in pattern.finditer(claims_text):
        number = match.group(1)
        text = re.sub(r"\s+", " ", match.group(2)).strip()
        if not text:
            continue
        claims.append(
            {
                "number": number,
                "text": text,
                "type_hint": "dependent" if re.search(r"根据权利要求\d+", text) else "independent",
                "has_characterizing_clause": "其特征在于" in text,
            }
        )
    return claims


def extract_figures(markdown: str) -> dict[str, Any]:
    figure_mentions = sorted(set(re.findall(r"图\s*\d+[A-Za-z]?", markdown)))
    label_lines = []
    in_label_zone = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if re.search(r"(附图标记|标号说明|附图说明)", stripped):
            in_label_zone = True
        if in_label_zone and re.match(r"^\d{1,4}\s*[-—、.．:：]\s*\S+", stripped):
            label_lines.append(stripped)
        if in_label_zone and len(label_lines) > 0 and not stripped:
            in_label_zone = False
    return {
        "figure_mentions": figure_mentions,
        "figure_count_hint": len(figure_mentions),
        "label_lines": label_lines,
        "label_count_hint": len(label_lines),
    }


def content_stats(content_list: list[dict[str, Any]]) -> dict[str, Any]:
    stats = {
        "items": len(content_list),
        "tables": 0,
        "images": 0,
        "equations": 0,
        "discarded_blocks": 0,
        "pages": [],
    }
    pages = set()
    for item in content_list:
        item_type = item.get("type")
        if item_type in ("table", "chart"):
            stats["tables"] += 1
        elif item_type == "image":
            stats["images"] += 1
        elif item_type in ("equation", "formula"):
            stats["equations"] += 1
        elif item_type in ("header", "footer", "page_number", "aside_text", "page_footnote"):
            stats["discarded_blocks"] += 1
        if "page_idx" in item:
            pages.add(item["page_idx"])
    stats["pages"] = sorted(pages)
    stats["page_count_hint"] = len(pages)
    return stats


def detect_material_cues(text: str) -> dict[str, Any]:
    hits = []
    for term in MATERIAL_TERMS:
        if term.lower() in text.lower():
            hits.append(term)
    numeric_patterns = {
        "percentage": len(re.findall(r"\d+(?:\.\d+)?\s*(?:%|wt%|mol%)", text, flags=re.I)),
        "parts_by_weight": len(re.findall(r"\d+(?:\.\d+)?\s*(?:重量份|质量份|份)", text)),
        "temperature": len(re.findall(r"\d+(?:\.\d+)?\s*(?:℃|摄氏度|°C)", text, flags=re.I)),
        "hardness": len(re.findall(r"(?:邵氏|shore)\s*[A-D]?\s*\d+", text, flags=re.I)),
    }
    return {
        "terms": hits,
        "numeric_patterns": numeric_patterns,
        "material_like": bool(hits) or any(value > 0 for value in numeric_patterns.values()),
    }


def quality_report(
    markdown: str,
    sections: dict[str, dict[str, Any]],
    claims: list[dict[str, Any]],
    figures: dict[str, Any],
    stats: dict[str, Any],
    material: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    missing = []
    for key in ("abstract", "claims", "technical_field", "background", "summary", "embodiments"):
        if key not in sections:
            missing.append(SECTION_LABELS[key])

    spaced_heading_hits = []
    for wrong in PATENT_TERM_FIXES:
        if wrong in markdown:
            spaced_heading_hits.append(wrong)

    warnings = []
    if missing:
        warnings.append("缺少或未识别关键专利章节：" + "、".join(missing))
    if claims and not any(item["has_characterizing_clause"] for item in claims):
        warnings.append("权利要求中未检测到“其特征在于”，需人工确认是否为中国撰写格式。")
    if figures["figure_mentions"] and figures["label_count_hint"] == 0:
        warnings.append("正文出现图号，但未识别到附图标记表或标号说明。")
    if material["material_like"] and stats.get("tables", 0) == 0:
        warnings.append("检测到材料/配方线索但未识别表格，需核查 OCR 是否丢失配方表。")
    if profile in {"material-scan", "disclosure"} and not material["material_like"]:
        warnings.append("目标场景需要交底或材料信息，但未检测到配方、参数或测试数据线索。")

    return {
        "missing_sections": missing,
        "ocr_spacing_heading_hits": spaced_heading_hits,
        "warnings": warnings,
        "risk_level": "high" if len(warnings) >= 3 else "medium" if warnings else "low",
        "manual_review_required": bool(warnings),
    }


def write_sections_markdown(path: Path, title: str, sections: dict[str, dict[str, Any]]) -> None:
    lines = [f"# {title or '专利 OCR 结构化结果'}", ""]
    for name, info in sections.items():
        label = info.get("label") or name
        lines.extend([f"## {label}", "", info.get("content", "").strip(), ""])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def postprocess(raw_root: Path, output_dir: Path, source: str, profile: str, mineru_meta: dict[str, Any]) -> dict[str, Any]:
    markdown, md_path = load_markdown(raw_root)
    content_list, content_path = load_content_list(raw_root)
    normalized = normalize_ocr_text(markdown)
    sections = detect_sections(normalized)
    title = extract_title(normalized, sections)
    claims = extract_claims(sections, normalized)
    figures = extract_figures(normalized)
    stats = content_stats(content_list)
    material = detect_material_cues(normalized)
    report = quality_report(normalized, sections, claims, figures, stats, material, profile)

    normalized_md_path = output_dir / "patent_ocr_normalized.md"
    sections_md_path = output_dir / "patent_ocr_sections.md"
    quality_path = output_dir / "patent_ocr_quality_report.json"
    bundle_path = output_dir / "patent_ocr_bundle.json"

    normalized_md_path.write_text(normalized, encoding="utf-8")
    write_sections_markdown(sections_md_path, title, sections)

    bundle = {
        "created_at": now_iso(),
        "source": source,
        "profile": profile,
        "title": title,
        "mineru": mineru_meta,
        "input_files": {
            "markdown": str(md_path) if md_path else None,
            "content_list": str(content_path) if content_path else None,
        },
        "sections": sections,
        "claims": claims,
        "figures": figures,
        "content_stats": stats,
        "material_cues": material,
        "quality_report": report,
        "outputs": {
            "normalized_markdown": str(normalized_md_path),
            "sections_markdown": str(sections_md_path),
            "quality_report": str(quality_path),
            "bundle_json": str(bundle_path),
        },
    }
    write_json(quality_path, report)
    write_json(bundle_path, bundle)
    return bundle


def parse_extra_formats(value: str | None) -> list[str]:
    if not value:
        return []
    allowed = {"docx", "html", "latex"}
    values = [part.strip() for part in value.split(",") if part.strip()]
    bad = [part for part in values if part not in allowed]
    if bad:
        raise argparse.ArgumentTypeError(f"Unsupported extra format: {', '.join(bad)}")
    return values


def make_context(args: argparse.Namespace) -> ParseContext:
    source = str(args.source)
    output_dir = ensure_output_dir(Path(args.output_dir))
    profile = args.profile
    model_version = infer_model(source, profile, args.model_version)
    is_ocr_flag = infer_ocr_flag(source, profile, args.ocr_mode)
    data_id_source = args.data_id or (Path(source).stem if not is_url(source) else source.rsplit("/", 1)[-1])
    return ParseContext(
        source=source,
        service=args.service,
        profile=profile,
        output_dir=output_dir,
        language=args.language,
        model_version=model_version,
        is_ocr=is_ocr_flag,
        enable_table=not args.disable_table,
        enable_formula=not args.disable_formula,
        page_ranges=args.page_ranges,
        extra_formats=parse_extra_formats(args.extra_formats),
        data_id=sanitize_data_id(data_id_source),
        timeout=args.timeout,
        interval=args.interval,
    )


def run_parse(args: argparse.Namespace) -> int:
    ctx = make_context(args)
    if args.dry_run:
        dry = {
            "source": ctx.source,
            "service": ctx.service,
            "profile": ctx.profile,
            "model_version": ctx.model_version,
            "is_ocr": ctx.is_ocr,
            "enable_table": ctx.enable_table,
            "enable_formula": ctx.enable_formula,
            "page_ranges": ctx.page_ranges,
            "extra_formats": ctx.extra_formats,
            "output_dir": str(ctx.output_dir),
            "token_required": ctx.service == "precision",
        }
        write_json(ctx.output_dir / "dry_run_plan.json", dry)
        print(json.dumps(dry, ensure_ascii=False, indent=2))
        return 0

    if not is_url(ctx.source):
        input_path = Path(ctx.source)
        if not input_path.exists():
            raise MinerUError(f"Input file does not exist: {input_path}")

    if ctx.service == "precision":
        mineru_meta = parse_precision(ctx)
    elif ctx.service == "agent":
        mineru_meta = parse_agent(ctx)
    elif ctx.service == "local":
        mineru_meta = parse_local(ctx)
    else:
        raise MinerUError(f"Unsupported service: {ctx.service}")

    raw_root = Path(mineru_meta["raw_dir"])
    bundle = postprocess(raw_root, ctx.output_dir, ctx.source, ctx.profile, mineru_meta)
    print(json.dumps(bundle["outputs"], ensure_ascii=False, indent=2))
    return 0


def run_postprocess(args: argparse.Namespace) -> int:
    raw_root = Path(args.raw_root)
    if not raw_root.exists():
        raise MinerUError(f"Raw root does not exist: {raw_root}")
    output_dir = ensure_output_dir(Path(args.output_dir))
    mineru_meta = {"service": "postprocess-only", "raw_dir": str(raw_root)}
    bundle = postprocess(raw_root, output_dir, args.source or str(raw_root), args.profile, mineru_meta)
    print(json.dumps(bundle["outputs"], ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse patent/disclosure documents with MinerU and patent-specific postprocessing."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse = subparsers.add_parser("parse", help="Run MinerU parsing and patent postprocessing")
    parse.add_argument("source", help="Local file path or remote URL")
    parse.add_argument("--service", choices=["precision", "agent", "local"], default="precision")
    parse.add_argument(
        "--profile",
        choices=["patent-application", "official-patent", "disclosure", "scanned-patent", "drawings", "material-scan"],
        default="patent-application",
    )
    parse.add_argument("--output-dir", default="output/patent-ocr-mineru")
    parse.add_argument("--language", default="ch")
    parse.add_argument("--model-version", choices=["pipeline", "vlm", "MinerU-HTML"])
    parse.add_argument("--ocr-mode", choices=["auto", "ocr", "text"], default="auto")
    parse.add_argument("--page-ranges", help='Precision API supports values like "2,4-6"; Agent supports one simple range.')
    parse.add_argument("--extra-formats", help="Precision API only: comma-separated docx,html,latex")
    parse.add_argument("--disable-table", action="store_true")
    parse.add_argument("--disable-formula", action="store_true")
    parse.add_argument("--data-id", help="Business id sent to MinerU precision API; token-safe, no secrets.")
    parse.add_argument("--timeout", type=int, default=1200)
    parse.add_argument("--interval", type=int, default=5)
    parse.add_argument("--dry-run", action="store_true", help="Print and save the planned request without calling MinerU")
    parse.set_defaults(func=run_parse)

    post = subparsers.add_parser("postprocess", help="Postprocess existing MinerU output directory or zip extraction")
    post.add_argument("raw_root", help="Directory containing full.md and optional content_list.json")
    post.add_argument("--source", help="Original source label")
    post.add_argument(
        "--profile",
        choices=["patent-application", "official-patent", "disclosure", "scanned-patent", "drawings", "material-scan"],
        default="patent-application",
    )
    post.add_argument("--output-dir", default="output/patent-ocr-mineru")
    post.set_defaults(func=run_postprocess)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MinerUError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
