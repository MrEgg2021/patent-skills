#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path

import pandas as pd

sys.dont_write_bytecode = True

DEFAULT_COLUMNS = [
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
    'matched_scope',
    'match_notes',
    'snippet',
    'abstract',
    'pdf_url',
    'url',
]


def read_text_flexible(path: Path) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    raise UnicodeDecodeError('codec', b'', 0, 1, f'cannot decode {path}')


def load_results(path: Path) -> list[dict]:
    payload = json.loads(read_text_flexible(path))
    if isinstance(payload, dict):
        # Support both "results" key (parse_results.py output) and "patents" key (xhr_search.py output)
        results = payload.get('results', []) or payload.get('patents', [])
    elif isinstance(payload, list):
        results = payload
    else:
        raise ValueError('Unsupported input structure')
    if not isinstance(results, list):
        raise ValueError('results must be a list')
    return [item for item in results if isinstance(item, dict)]


def ordered_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [column for column in DEFAULT_COLUMNS if column in frame.columns]
    remainder = [column for column in frame.columns if column not in preferred]
    return preferred + remainder


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert parsed Google Patents search results JSON to XLSX.')
    parser.add_argument('input', help='Path to the parsed JSON file')
    parser.add_argument('output', help='Path to the XLSX file to create')
    parser.add_argument('--sheet-name', default='patent_search_workpaper', help='Worksheet name')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    results = load_results(input_path)
    if not results:
        raise SystemExit('No results found in the input JSON.')

    frame = pd.DataFrame(results)
    frame = frame[ordered_columns(frame)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(output_path, index=False, sheet_name=args.sheet_name)

    print(f'Saved to: {output_path}')
    print(f'Rows: {len(frame)}')


if __name__ == '__main__':
    main()
