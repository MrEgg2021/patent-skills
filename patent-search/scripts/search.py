#!/usr/bin/env python3
from __future__ import annotations

# 跨平台：确保非 ASCII（中文/emoji）输出在 Windows GBK 控制台不崩溃
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import argparse
import json
import urllib.parse
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from search_intelligence import build_search_plan, clean_text, parse_text_list

BASE_URL = 'https://patents.google.com'
ADVANCED_URL = 'https://patents.google.com/advanced'
XHR_BASE_URL = 'https://patents.google.com/xhr/query'


def read_text_flexible(path: Path) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    raise UnicodeDecodeError('codec', b'', 0, 1, f'cannot decode {path}')


def load_answers(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if args.answers:
        payload.update(json.loads(args.answers))
    if args.answers_file:
        payload.update(json.loads(read_text_flexible(Path(args.answers_file))))
    return payload


def build_search_url(query: str) -> str:
    encoded_query = urllib.parse.quote(query)
    return f'{BASE_URL}/?q={encoded_query}'


def build_xhr_url(query: str, page: int = 0) -> str:
    """Build the XHR/query endpoint URL for direct HTTP search (no browser needed).

    The XHR endpoint returns structured JSON, supports ``country:CN``,
    and includes Chinese patents with machine-translated titles.
    This is the preferred search path over the browser-based search page.
    """
    encoded_query = urllib.parse.quote(query)
    url = f'{XHR_BASE_URL}?url=q%3D{encoded_query}'
    if page > 0:
        url += f'&page={page}'
    return url


def build_browser_actions(needs_confirmation: bool) -> list[str]:
    steps = [
        '[优先] 使用 xhr_search.py（纯 HTTP、无需浏览器）。仅当 XHR 路径失败时才用浏览器回退。',
        '[无头强制] 若必须用浏览器：一律以无头模式（headless=True）后台运行，禁止弹出可视窗口、禁止 page.pause()。',
        'Open advanced_url in headless browser tools.',
        'Fill advanced_fields into the Google Patents advanced search form.',
    ]
    if needs_confirmation:
        steps.append('Pause and ask the user to confirm alias candidates before submitting the search.')
    else:
        steps.append('Run query_sets in recommended_order, starting with core_strict.')
        steps.append('Keep Sort by at Relevance unless the user explicitly asks for a different ranking view.')
        steps.append('Save a browser snapshot or structured JSON export for downstream parsing.')
    return steps


def build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    search_plan = build_search_plan(inputs)
    query_sets_for_urls = search_plan['query_sets'] or search_plan['query_sets_draft']
    result_urls = [
        {
            'strategy_name': item['strategy_name'],
            'query': item['query'],
            'result_url': build_search_url(item['query']),
            'xhr_url': build_xhr_url(item['query']),
        }
        for item in query_sets_for_urls
        if clean_text(item.get('query'))
    ]
    primary_query = query_sets_for_urls[0]['query'] if query_sets_for_urls else ''
    primary_result_url = result_urls[0]['result_url'] if result_urls else build_search_url(primary_query)
    primary_xhr_url = result_urls[0]['xhr_url'] if result_urls else build_xhr_url(primary_query)
    advanced_fields = dict(search_plan['advanced_fields'])
    advanced_fields['must_include_terms'] = parse_text_list(inputs.get('must_include_terms'))
    advanced_fields['exclude_terms'] = parse_text_list(inputs.get('exclude_terms'))
    advanced_fields['assignee_aliases'] = parse_text_list(inputs.get('assignee_aliases'))
    advanced_fields['inventor_aliases'] = parse_text_list(inputs.get('inventor_aliases'))
    advanced_fields['confirmed_assignee_aliases'] = parse_text_list(inputs.get('confirmed_assignee_aliases'))
    advanced_fields['confirmed_inventor_aliases'] = parse_text_list(inputs.get('confirmed_inventor_aliases'))

    return {
        'query': primary_query,
        'result_url': primary_result_url,
        'xhr_url': primary_xhr_url,
        'advanced_url': ADVANCED_URL,
        'advanced_fields': advanced_fields,
        'analysis_summary': search_plan['analysis_summary'],
        'concept_terms': search_plan['concept_terms'],
        'expansion_terms': search_plan['expansion_terms'],
        'preferred_language': search_plan['preferred_language'],
        'english_track_confidence': search_plan['english_track_confidence'],
        'alias_candidates': search_plan['alias_candidates'],
        'needs_user_confirmation': search_plan['needs_user_confirmation'],
        'confirmation_prompt_payload': search_plan['confirmation_prompt_payload'],
        'query_sets_draft': search_plan['query_sets_draft'],
        'query_sets': search_plan['query_sets'],
        'result_urls': result_urls,
        'strategy_catalog': search_plan['strategy_catalog'],
        'max_results': inputs.get('max_results'),
        'browser_actions': build_browser_actions(search_plan['needs_user_confirmation']),
    }


def build_automation_payload(
    search_terms: str = '',
    inventor: str | None = None,
    assignee: str | None = None,
    classification: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_results: int | None = None,
    search_input_mode: str = 'query',
    technical_description_text: str | None = None,
    must_include_terms: list[str] | None = None,
    exclude_terms: list[str] | None = None,
    patent_office: list[str] | None = None,
    language: list[str] | None = None,
    status: list[str] | None = None,
    type: list[str] | None = None,
    assignee_aliases: list[str] | None = None,
    inventor_aliases: list[str] | None = None,
    confirmed_assignee_aliases: list[str] | None = None,
    confirmed_inventor_aliases: list[str] | None = None,
) -> dict[str, Any]:
    inputs = {
        'search_terms': search_terms,
        'inventor': inventor or '',
        'assignee': assignee or '',
        'classification': classification or '',
        'date_from': date_from or '',
        'date_to': date_to or '',
        'max_results': max_results,
        'search_input_mode': search_input_mode or 'query',
        'technical_description_text': technical_description_text or '',
        'must_include_terms': must_include_terms or [],
        'exclude_terms': exclude_terms or [],
        'patent_office': patent_office or [],
        'language': language or [],
        'status': status or [],
        'type': type or [],
        'assignee_aliases': assignee_aliases or [],
        'inventor_aliases': inventor_aliases or [],
        'confirmed_assignee_aliases': confirmed_assignee_aliases or [],
        'confirmed_inventor_aliases': confirmed_inventor_aliases or [],
    }
    return build_payload(inputs)


def merge_cli_args(args: argparse.Namespace) -> dict[str, Any]:
    inputs = load_answers(args)

    direct = {
        'search_terms': args.terms,
        'inventor': args.inventor,
        'assignee': args.assignee,
        'classification': args.classification,
        'date_from': args.date_from,
        'date_to': args.date_to,
        'max_results': args.max_results if args.max_results and args.max_results > 0 else None,
        'search_input_mode': args.search_input_mode,
        'technical_description_text': args.technical_description,
        'must_include_terms': parse_text_list(args.must_include),
        'exclude_terms': parse_text_list(args.exclude),
        'patent_office': parse_text_list(args.patent_office),
        'language': parse_text_list(args.language),
        'status': parse_text_list(args.status),
        'type': parse_text_list(args.type),
        'assignee_aliases': parse_text_list(args.assignee_alias),
        'inventor_aliases': parse_text_list(args.inventor_alias),
        'confirmed_assignee_aliases': parse_text_list(args.confirmed_assignee_alias),
        'confirmed_inventor_aliases': parse_text_list(args.confirmed_inventor_alias),
    }
    for key, value in direct.items():
        if key not in inputs or inputs.get(key) in (None, '', [], {}):
            inputs[key] = value

    if inputs.get('search_input_mode') == 'technical_description' and not clean_text(inputs.get('technical_description_text')):
        inputs['technical_description_text'] = clean_text(inputs.get('search_terms'))
    if inputs.get('search_input_mode') != 'technical_description' and clean_text(inputs.get('technical_description_text')):
        inputs['search_input_mode'] = 'technical_description'
    if not clean_text(inputs.get('search_terms')) and inputs.get('search_input_mode') == 'query':
        inputs['search_terms'] = clean_text(inputs.get('technical_description_text'))
    return inputs


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Google Patents query plans and browser automation payloads.')
    parser.add_argument('--answers', help='Inline JSON answers payload.')
    parser.add_argument('--answers-file', help='Path to a JSON answers payload.')
    parser.add_argument('--terms', default='', help='Search terms or Boolean query.')
    parser.add_argument('--inventor', default='', help='Optional inventor filter.')
    parser.add_argument('--assignee', default='', help='Optional assignee filter.')
    parser.add_argument('--classification', default='', help='Optional CPC / IPC filter.')
    parser.add_argument('--date-from', default='', help='Optional start date (YYYY-MM-DD).')
    parser.add_argument('--date-to', default='', help='Optional end date (YYYY-MM-DD).')
    parser.add_argument('--max-results', type=int, default=20, help='Optional downstream result cap.')
    parser.add_argument('--search-input-mode', choices=['query', 'technical_description'], default='query')
    parser.add_argument('--technical-description', default='', help='Technical description or disclosure excerpt.')
    parser.add_argument('--must-include', default='', help='Comma- or newline-separated must-include terms.')
    parser.add_argument('--exclude', default='', help='Comma- or newline-separated exclude terms.')
    parser.add_argument('--patent-office', default='', help='Comma- or newline-separated patent office filters.')
    parser.add_argument('--language', default='', help='Comma- or newline-separated language filters.')
    parser.add_argument('--status', default='', help='Comma- or newline-separated status filters.')
    parser.add_argument('--type', default='', help='Comma- or newline-separated type filters for advanced form use.')
    parser.add_argument('--assignee-alias', default='', help='Comma- or newline-separated tentative assignee aliases.')
    parser.add_argument('--inventor-alias', default='', help='Comma- or newline-separated tentative inventor aliases.')
    parser.add_argument('--confirmed-assignee-alias', default='', help='Comma- or newline-separated confirmed assignee aliases.')
    parser.add_argument('--confirmed-inventor-alias', default='', help='Comma- or newline-separated confirmed inventor aliases.')
    parser.add_argument('--json', action='store_true', help='Print JSON only.')
    args = parser.parse_args()

    inputs = merge_cli_args(args)
    payload = build_payload(inputs)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print('Primary Query:')
    print(payload['query'])
    print()
    print('Primary Result URL:')
    print(payload['result_url'])
    print()
    print('Needs User Confirmation:')
    print(payload['needs_user_confirmation'])
    print()
    print('Analysis Summary:')
    print(payload['analysis_summary'])
    print()
    print('Query Sets:')
    for query_set in payload['query_sets'] or payload['query_sets_draft']:
        print(f"- {query_set['strategy_name']}: {query_set['query']}")
    print()
    print('Browser Actions:')
    for step in payload['browser_actions']:
        print(f'- {step}')


if __name__ == '__main__':
    main()
