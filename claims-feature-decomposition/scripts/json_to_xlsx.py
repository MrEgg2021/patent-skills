#!/usr/bin/env python3
"""Convert claims-feature-decomposition JSON output to xlsx."""
from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True

EXPECTED_COLUMNS = [
    "权利要求序号",
    "技术特征 (源自权利要求书原文，按语义单位独立分解)",
    "说明书描述 (主题归类式整合，严格源自说明书原文，并注明来源)",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert claims-feature-decomposition JSON to xlsx"
    )
    parser.add_argument("input", help="Path to the JSON file (array of objects)")
    parser.add_argument("output", help="Path to the xlsx file to create")
    parser.add_argument("--sheet-name", default="权利要求特征拆解", help="Worksheet name")
    args = parser.parse_args()

    input_path = Path(args.input)
    with open(input_path, encoding="utf-8") as f:
        raw = f.read()

    # Strip markdown code blocks if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]  # remove opening ```
        if lines[-1].strip() == "```":
            lines = lines[:-1]  # remove closing ```
        raw = "\n".join(lines)

    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("results", data.get("data", []))
    if not isinstance(data, list):
        raise ValueError("JSON must be an array or object with results/data key")

    frame = pd.DataFrame(data)
    # Keep only expected columns if present
    cols = [c for c in EXPECTED_COLUMNS if c in frame.columns]
    if not cols:
        # Fallback: use all columns
        cols = list(frame.columns)
    frame = frame[cols]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(output_path, index=False, sheet_name=args.sheet_name)

    print(f"Saved: {output_path}")
    print(f"Rows: {len(frame)}")
    print(f"Columns: {', '.join(cols)}")


if __name__ == "__main__":
    main()
