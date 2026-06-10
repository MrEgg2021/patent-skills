#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True


def read_text_flexible(path: Path) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    raise UnicodeDecodeError('codec', b'', 0, 1, f'cannot decode {path}')


def load_results(path: Path) -> tuple[str | None, list[dict]]:
    payload = json.loads(read_text_flexible(path))
    if isinstance(payload, dict):
        query = payload.get('query')
        # Support both "results" key (parse_results.py output) and "patents" key (xhr_search.py output)
        results = payload.get('results', []) or payload.get('patents', [])
    elif isinstance(payload, list):
        query = None
        results = payload
    else:
        raise ValueError('Unsupported input structure')
    if not isinstance(results, list):
        raise ValueError('results must be a list')
    return query, [item for item in results if isinstance(item, dict)]


def is_cn_related(result: dict, mode: str) -> bool:
    publication_number = str(result.get('publication_number', '')).upper()
    has_cn_prefix = publication_number.startswith('CN')
    has_cn_family = bool(result.get('has_cn_family'))
    if mode == 'prefix':
        return has_cn_prefix
    if mode == 'family':
        return has_cn_family
    return has_cn_prefix or has_cn_family


def save_xlsx(path: Path, results: list[dict]) -> None:
    frame = pd.DataFrame(results)
    ordered = [
        column
        for column in [
            'query_set_name',
            'source_sort_mode',
            'title',
            'publication_number',
            'country_code',
            'family_countries',
            'applicant',
            'inventor',
            'priority_date',
            'filing_date',
            'publication_date',
            'grant_date',
            'date',
            'has_cn_family',
            'snippet',
            'abstract',
            'pdf_url',
            'url',
        ]
        if column in frame.columns
    ]
    extras = [column for column in frame.columns if column not in ordered]
    frame = frame[ordered + extras]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description='Filter CN-related results from a parsed Google Patents result set.')
    parser.add_argument('input', help='Path to the parsed JSON file')
    parser.add_argument('output', help='Path to the filtered JSON file')
    parser.add_argument('--xlsx', help='Optional XLSX export path')
    parser.add_argument('--mode', choices=['either', 'prefix', 'family'], default='either')
    parser.add_argument('--limit', type=int, help='Optional maximum number of results to keep')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    query, results = load_results(input_path)
    filtered = [result for result in results if is_cn_related(result, args.mode)]
    if args.limit is not None:
        filtered = filtered[: args.limit]

    payload = {
        'query': query,
        'filter_mode': args.mode,
        'source_file': str(input_path),
        'total_results': len(filtered),
        'results': filtered,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'JSON saved: {output_path}')
    print(f'Total results: {len(filtered)}')

    if args.xlsx:
        xlsx_path = Path(args.xlsx)
        save_xlsx(xlsx_path, filtered)
        print(f'XLSX saved: {xlsx_path}')


if __name__ == '__main__':
    main()
