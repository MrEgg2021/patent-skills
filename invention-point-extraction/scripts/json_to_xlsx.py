#!/usr/bin/env python3
"""Convert invention-point-extraction JSON output to XLSX."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment


OUTPUT_COLUMNS = ["专利公开号", "专利标题", "技术问题", "技术方案"]


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    return fenced.group(1).strip() if fenced else text


def load_payload(path: Path) -> list[dict[str, Any]]:
    raw = strip_code_fence(read_text(path))
    payload = json.loads(raw)
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            payload = payload["results"]
        elif isinstance(payload.get("data"), list):
            payload = payload["data"]
        else:
            payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("JSON must be an object, an array, or an object with results/data array")
    rows = [item for item in payload if isinstance(item, dict)]
    if not rows:
        raise ValueError("No object rows found")
    return rows


def numbered(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(f"{idx}. {str(item).strip()}" for idx, item in enumerate(value, 1) if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def split_invention_points(text: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    solutions: list[str] = []
    if not text:
        return problems, solutions
    chunks = re.split(r"\n\s*(?=\d+[\.、])", text.strip())
    for chunk in chunks:
        problem = ""
        solution = ""
        m_problem = re.search(r"技术问题[:：]\s*(.*?)(?=技术方案[:：]|$)", chunk, flags=re.S)
        m_solution = re.search(r"技术方案[:：]\s*(.*)$", chunk, flags=re.S)
        if m_problem:
            problem = m_problem.group(1).strip()
        if m_solution:
            solution = m_solution.group(1).strip()
        if not problem and not solution:
            problem = chunk.strip()
        if problem:
            problems.append(re.sub(r"^\d+[\.、]\s*", "", problem))
        if solution:
            solutions.append(re.sub(r"^\d+[\.、]\s*", "", solution))
    return problems, solutions


def normalize_row(item: dict[str, Any]) -> dict[str, str]:
    pub_no = (
        item.get("专利公开号")
        or item.get("公开号")
        or item.get("publication_number")
        or item.get("文件名称")
        or item.get("file_name")
        or ""
    )
    title = item.get("专利标题") or item.get("标题") or item.get("title") or ""
    problems = item.get("技术问题") or item.get("technical_problem")
    solutions = item.get("技术方案") or item.get("technical_solution")

    if (not problems or not solutions) and item.get("发明点"):
        parsed_problems, parsed_solutions = split_invention_points(numbered(item.get("发明点")))
        problems = problems or parsed_problems
        solutions = solutions or parsed_solutions

    return {
        "专利公开号": numbered(pub_no),
        "专利标题": numbered(title),
        "技术问题": numbered(problems),
        "技术方案": numbered(solutions),
    }


def autosize_and_wrap(writer: pd.ExcelWriter, sheet_name: str) -> None:
    worksheet = writer.sheets[sheet_name]
    for column_cells in worksheet.columns:
        letter = column_cells[0].column_letter
        max_len = 10
        for cell in column_cells:
            text = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, min(80, max((len(line) for line in text.splitlines()), default=0)))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        worksheet.column_dimensions[letter].width = min(max_len + 4, 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert invention point JSON to xlsx")
    parser.add_argument("input", help="JSON file from LLM extraction")
    parser.add_argument("output", help="XLSX output path")
    parser.add_argument("--sheet-name", default="发明点解析")
    args = parser.parse_args()

    rows = [normalize_row(item) for item in load_payload(Path(args.input))]
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=args.sheet_name)
        autosize_and_wrap(writer, args.sheet_name)
    print(f"saved: {output}")
    print(f"rows: {len(frame)}")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
