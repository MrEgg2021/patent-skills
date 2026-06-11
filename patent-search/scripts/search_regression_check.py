#!/usr/bin/env python3
from __future__ import annotations

import sys
import json
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

from convert_to_xlsx import load_results
from parse_results import build_output, parse_input
from search import build_automation_payload
import xhr_search


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_query_mode_case() -> None:
    payload = build_automation_payload(
        search_terms='machine learning hardware optimization',
        classification='G06N',
        max_results=20,
    )
    assert_true(payload['query_sets'], 'query mode should produce final query sets')
    assert_true(payload['query_sets'][0]['strategy_name'] == 'core_strict', 'first query set should be core_strict')
    assert_true('ipc:G06N' in payload['query_sets'][0]['query'] or 'cpc:G06N' in payload['query_sets'][0]['query'], 'classification filter should appear in query')


def run_technical_description_case() -> None:
    payload = build_automation_payload(
        search_input_mode='technical_description',
        technical_description_text='一种基于多模态特征融合的异常检测方法及装置，用于工业设备状态监测。',
        must_include_terms=['anomaly detection'],
        max_results=20,
    )
    assert_true(payload['query_sets'], 'technical description mode should produce final query sets when alias confirmation is not needed')
    assert_true(len(payload['query_sets']) == 3, 'default query set count should be three')
    assert_true(payload['analysis_summary'], 'technical description mode should produce analysis summary')


def run_alias_confirmation_case() -> None:
    payload = build_automation_payload(
        search_terms='machine learning scheduling',
        assignee='Intel',
        date_from='2020-01-01',
        date_to='2025-12-31',
        max_results=20,
    )
    assert_true(payload['needs_user_confirmation'] is True, 'public alias expansion should request confirmation')
    assert_true(not payload['query_sets'], 'final query sets should stay empty until aliases are confirmed')
    assert_true(payload['alias_candidates']['assignee'], 'assignee alias candidates should be returned')


def run_parse_and_export_case() -> None:
    snapshot = '''Sort by · Relevance

Distributed machine learning systems including generation of synthetic data
WO EP US CN JP KR AU CA IL MX SG TW • US12518214B2 • Christopher W. Szeto • Nantomics, Llc
Priority 2016-07-18 • Filed 2023-04-21 • Granted 2026-01-06 • Published 2026-01-06
wherein the machine learning model instructions comprise at least one of supervised machine learning instructions.
'''
    with tempfile.TemporaryDirectory(prefix='gp-search-regression-') as tmp_dir:
        snapshot_path = Path(tmp_dir) / 'snapshot.txt'
        json_path = Path(tmp_dir) / 'parsed.json'
        xlsx_path = Path(tmp_dir) / 'parsed.xlsx'
        snapshot_path.write_text(snapshot, encoding='utf-8')
        results = parse_input(snapshot_path, 'text', 'machine learning', None, 'balanced')
        output = build_output(snapshot_path, 'machine learning', results, 'Relevance', 'balanced')
        json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        parsed_results = load_results(json_path)
        assert_true(parsed_results[0]['source_sort_mode'] == 'Relevance', 'sort mode should be captured')
        assert_true(parsed_results[0]['has_cn_family'] is True, 'CN family detection should remain available')

        import pandas as pd

        frame = pd.DataFrame(parsed_results)
        frame.to_excel(xlsx_path, index=False)
        assert_true(xlsx_path.exists(), 'xlsx export smoke file should exist')


def run_xhr_search_smoke_case() -> None:
    """冒烟：保证 xhr_search 可 import 且核心纯函数行为正确。
    （此用例专为防止 import/语法层错误溜过——纯函数，不触发网络请求）"""
    assert_true(xhr_search._strip_html_tags('<b>ML</b> system') == 'ML system', 'strip_html_tags should remove tags')
    assert_true(xhr_search._extract_country('CN107390684B') == 'CN', 'extract_country should derive CN')
    assert_true(xhr_search._extract_country('US123') == 'US', 'extract_country should derive US')
    assert_true('q%3D' in xhr_search._build_xhr_url('robot'), 'build_xhr_url should URL-encode query')


def main() -> None:
    run_query_mode_case()
    run_technical_description_case()
    run_alias_confirmation_case()
    run_parse_and_export_case()
    run_xhr_search_smoke_case()
    print('patent-search search regression checks passed')


if __name__ == '__main__':
    main()
