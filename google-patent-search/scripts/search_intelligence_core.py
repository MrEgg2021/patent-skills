#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests
import yaml

WIKIDATA_SEARCH_URL = 'https://www.wikidata.org/w/api.php'
WIKIPEDIA_OPENSEARCH_URL = 'https://en.wikipedia.org/w/api.php'
REFERENCE_DIR = Path(__file__).resolve().parent.parent / 'references'
QUERY_PATTERN_PATH = REFERENCE_DIR / 'google_patents_query_patterns.yaml'

ASCII_PHRASE_RE = re.compile(r'[A-Za-z][A-Za-z0-9+#/\-.]*(?:\s+[A-Za-z][A-Za-z0-9+#/\-.]*){0,3}')
CLASSIFICATION_RE = re.compile(r'\b(?:[A-HY]\d{2}[A-Z]\d{1,4}(?:/\d+)?|[A-HY]\d{2}[A-Z])\b')
COMPANY_SUFFIX_RE = re.compile(
    r'\b(?:inc|corp|corporation|co|company|ltd|limited|llc|gmbh|kg|ag|sa|plc|group|holdings)\b\.?',
    re.IGNORECASE,
)
BOOLEAN_QUERY_HINT_RE = re.compile(
    r'\b(?:AND|OR|NOT|AROUND\(\d+\)|TI=|AB=|CL=|assignee:|inventor:|country:|status:|language:|after:|before:|cpc:|ipc:)\b',
    re.IGNORECASE,
)

CHINESE_STOPWORDS = {
    '一种', '用于', '基于', '以及', '实现', '进行', '通过', '包括', '相关', '其中', '或者', '及其',
    '用户', '系统中', '设备中', '方法中', '装置中', '终端中', '本发明', '申请', '专利', '技术', '方案',
    '现在', '当前', '一个', '由于', '因此', '导致', '存在', '问题', '这些', '一些', '该', '本',
    '上述', '可以', '能够', '对于', '有', '后', '等', '下',
}

ENGLISH_STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'into', 'that', 'this', 'these', 'those', 'using', 'based',
    'method', 'device', 'system', 'apparatus', 'patent', 'application', 'embodiment', 'disclosure',
}

TECH_GLOSSARY: list[tuple[str, list[str]]] = [
    ('多模态', ['multimodal']),
    ('神经网络', ['neural network']),
    ('深度学习', ['deep learning']),
    ('机器学习', ['machine learning']),
    ('大模型', ['large language model', 'foundation model']),
    ('知识图谱', ['knowledge graph']),
    ('目标检测', ['object detection']),
    ('异常检测', ['anomaly detection']),
    ('故障检测', ['fault detection']),
    ('图像识别', ['image recognition']),
    ('图像处理', ['image processing']),
    ('视频分析', ['video analytics']),
    ('语音识别', ['speech recognition']),
    ('文本生成', ['text generation']),
    ('推荐系统', ['recommendation system']),
    ('特征提取', ['feature extraction']),
    ('特征融合', ['feature fusion']),
    ('数据增强', ['data augmentation']),
    ('数据清洗', ['data cleaning']),
    ('数据压缩', ['data compression']),
    ('边缘计算', ['edge computing']),
    ('云平台', ['cloud platform']),
    ('通信网络', ['communication network']),
    ('无线通信', ['wireless communication']),
    ('传感器', ['sensor']),
    ('控制器', ['controller']),
    ('电池管理', ['battery management']),
    ('芯片', ['chip']),
    ('半导体', ['semiconductor']),
    ('调度', ['scheduling']),
    ('预测', ['prediction']),
    ('识别', ['recognition']),
    ('检测', ['detection']),
    ('控制', ['control']),
    ('训练', ['training']),
    ('推理', ['inference']),
    ('优化', ['optimization']),
    ('终端', ['terminal']),
    ('装置', ['device']),
    ('系统', ['system']),
    ('方法', ['method']),
]

GLOSSARY_TERMS = tuple(term for term, _ in TECH_GLOSSARY)
OBJECT_SUFFIXES = (
    '方法', '装置', '系统', '设备', '模块', '平台', '介质', '单元', '终端', '网络', '电路',
    '模型', '机器人', '控制器', '传感器', '吸尘器', '检测器', '识别器', '物体', '障碍物',
)
ACTION_TERMS = (
    '检测', '识别', '预测', '推荐', '控制', '调度', '训练', '推理', '优化', '压缩', '加密',
    '解码', '编码', '分析', '生成', '规划', '导航', '定位', '清洁', '清扫',
)
EFFECT_TERMS = (
    '覆盖率', '效率', '精度', '稳定性', '可靠性', '吞吐量', '时延', '延迟',
    '功耗', '鲁棒性', '准确率', '召回率',
)
SCENARIO_TERMS = (
    '工业', '制造', '车辆', '车载', '医疗', '家居', '通信', '物流', '能源', '机器人',
    '清洁', '室内', '室外', '仓储',
)
PRIMARY_OBJECT_HINTS = ('机器人', '吸尘器', '设备', '装置', '系统', '平台', '终端', '控制器', '传感器', '方法')
MECHANISM_HINTS = ('检测', '识别', '预测', '调度', '控制', '训练', '推理', '优化', '导航', '定位', '融合')
LEADING_FILLER_PREFIXES = (
    '一种', '现在的', '当前的', '对于', '一些', '这些', '那些', '该', '本', '用于', '基于',
    '但是', '所以', '导致', '由于', '其', '它', '是', '将', '会', '等',
)
INNER_SPLIT_MARKERS = ('因为', '但是', '所以', '导致', '对于', '用于')


def clean_text(value: Any) -> str:
    return '' if value is None else str(value).strip()


def normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = normalize_whitespace(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def parse_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = [clean_text(item) for item in value]
        return dedupe_preserve_order([item for item in items if item])
    text = clean_text(value)
    if not text:
        return []
    parts = [part.strip() for part in re.split(r'[\n,;|]+', text) if part.strip()]
    if parts:
        return dedupe_preserve_order(parts)
    return [text]


def contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def load_query_patterns() -> dict[str, Any]:
    if not QUERY_PATTERN_PATH.exists():
        return {}
    return yaml.safe_load(QUERY_PATTERN_PATH.read_text(encoding='utf-8')) or {}


def extract_classification_hints(text: str) -> list[str]:
    return dedupe_preserve_order(CLASSIFICATION_RE.findall(text.upper()))


def extract_ascii_terms(text: str) -> list[str]:
    phrases = [normalize_whitespace(match.group(0)) for match in ASCII_PHRASE_RE.finditer(text)]
    weighted: list[str] = []
    for phrase in phrases:
        words = [word for word in phrase.split() if word.casefold() not in ENGLISH_STOPWORDS]
        if not words:
            continue
        normalized = ' '.join(words)
        if len(normalized) < 3:
            continue
        weighted.append(normalized)
    counts = Counter(weighted)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [phrase for phrase, _ in ranked[:8]]


def is_meaningful_chinese_term(term: str) -> bool:
    if not term or term in CHINESE_STOPWORDS or len(term) < 2:
        return False
    if term.endswith(('的问题', '的功能', '的区域', '的技术', '的物体')):
        return False
    if '的' in term and len(term) > 8:
        return False
    return True


def normalize_chinese_candidate(term: str) -> str:
    normalized = normalize_whitespace(term)
    changed = True
    while changed and normalized:
        changed = False
        for prefix in LEADING_FILLER_PREFIXES:
            if normalized.startswith(prefix) and len(normalized) > len(prefix) + 1:
                normalized = normalized[len(prefix):]
                changed = True
    for marker in INNER_SPLIT_MARKERS:
        if marker in normalized:
            tail = normalized.rsplit(marker, 1)[-1].strip()
            if len(tail) >= 2:
                normalized = tail
    changed = True
    while changed and normalized:
        changed = False
        for prefix in LEADING_FILLER_PREFIXES:
            if normalized.startswith(prefix) and len(normalized) > len(prefix) + 1:
                normalized = normalized[len(prefix):]
                changed = True
    return normalized


def extract_chinese_object_terms(text: str) -> list[str]:
    exact_matches = [keyword for keyword in sorted(GLOSSARY_TERMS, key=len, reverse=True) if len(keyword) >= 3 and keyword in text]
    candidates: list[str] = list(exact_matches)
    for suffix in OBJECT_SUFFIXES:
        pattern = re.compile(rf'[\u4e00-\u9fff]{{0,4}}{suffix}')
        candidates.extend(match.group(0) for match in pattern.finditer(text))
    for term in ACTION_TERMS:
        pattern = re.compile(rf'[\u4e00-\u9fff]{{1,4}}{term}')
        candidates.extend(match.group(0) for match in pattern.finditer(text))
    for term in EFFECT_TERMS:
        pattern = re.compile(rf'[\u4e00-\u9fff]{{0,4}}{term}')
        candidates.extend(match.group(0) for match in pattern.finditer(text))
    normalized_candidates = [normalize_chinese_candidate(item) for item in candidates]
    filtered = [item for item in normalized_candidates if is_meaningful_chinese_term(item) and 2 <= len(item) <= 18]
    counts = Counter(filtered)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return dedupe_preserve_order(exact_matches + [phrase for phrase, _ in ranked[:12]])


def extract_glossary_expansions(text: str) -> list[str]:
    expansions: list[str] = []
    for chinese_term, english_terms in TECH_GLOSSARY:
        if chinese_term in text:
            expansions.extend(english_terms)
    return dedupe_preserve_order(expansions)


def extract_scenarios(text: str) -> list[str]:
    found = [term for term in SCENARIO_TERMS if term in text]
    return dedupe_preserve_order(found)


def pick_primary_object(chinese_terms: list[str], english_terms: list[str]) -> str:
    for term in chinese_terms:
        if any(hint in term for hint in PRIMARY_OBJECT_HINTS):
            return term
    return chinese_terms[0] if chinese_terms else (english_terms[0] if english_terms else '')


def pick_key_mechanism(chinese_terms: list[str], english_terms: list[str], primary_object: str) -> str:
    for term in chinese_terms:
        if term != primary_object and any(hint in term for hint in MECHANISM_HINTS):
            return term
    fallback_terms = [term for term in chinese_terms if term != primary_object]
    return fallback_terms[0] if fallback_terms else (english_terms[1] if len(english_terms) > 1 else '')


def pick_technical_effect(chinese_terms: list[str], english_terms: list[str], primary_object: str, key_mechanism: str) -> str:
    for term in chinese_terms:
        if term not in {primary_object, key_mechanism} and any(marker in term for marker in EFFECT_TERMS):
            return term
    fallback_terms = [term for term in chinese_terms if term not in {primary_object, key_mechanism}]
    return fallback_terms[0] if fallback_terms else (english_terms[2] if len(english_terms) > 2 else '')


def tokenize_input_description(text: str, must_include_terms: list[str]) -> dict[str, Any]:
    normalized = normalize_whitespace(text)
    classification_hints = extract_classification_hints(normalized)
    english_terms = dedupe_preserve_order(extract_ascii_terms(normalized) + must_include_terms)
    chinese_terms = extract_chinese_object_terms(normalized)
    glossary_expansions = extract_glossary_expansions(normalized)
    scenarios = extract_scenarios(normalized)
    primary_object = pick_primary_object(chinese_terms, english_terms)
    key_mechanism = pick_key_mechanism(chinese_terms, english_terms, primary_object)
    technical_effect = pick_technical_effect(chinese_terms, english_terms, primary_object, key_mechanism)
    analysis_summary = ' / '.join(part for part in [primary_object, key_mechanism, technical_effect] if part) or normalized[:120]
    return {
        'analysis_summary': analysis_summary,
        'classification_hints': classification_hints,
        'english_terms': english_terms,
        'chinese_terms': chinese_terms,
        'glossary_expansions': glossary_expansions,
        'scenarios': scenarios,
        'primary_object': primary_object,
        'key_mechanism': key_mechanism,
        'technical_effect': technical_effect,
    }


def build_translation_candidates(technical_description_text: str, must_include_terms: list[str]) -> dict[str, Any]:
    concept = tokenize_input_description(technical_description_text, must_include_terms)
    english_track = dedupe_preserve_order(
        concept['english_terms'] + concept['glossary_expansions'] + concept['classification_hints']
    )
    chinese_track = dedupe_preserve_order(concept['chinese_terms'] + must_include_terms)
    mixed_track = dedupe_preserve_order(english_track[:6] + chinese_track[:6])
    english_track_confidence = 'high' if concept['glossary_expansions'] else 'medium' if concept['english_terms'] else 'low'
    preferred_language = 'english' if english_track else 'mixed'
    return {
        'analysis_summary': concept['analysis_summary'],
        'concept_terms': {
            'primary_object': concept['primary_object'],
            'key_mechanism': concept['key_mechanism'],
            'technical_effect': concept['technical_effect'],
            'scenarios': concept['scenarios'],
            'classification_hints': concept['classification_hints'],
        },
        'expansion_terms': {
            'english': english_track,
            'chinese': chinese_track,
            'mixed': mixed_track,
        },
        'preferred_language': preferred_language,
        'english_track_confidence': english_track_confidence,
    }


def normalize_entity_name(name: str) -> str:
    return normalize_whitespace(name.replace('"', '').replace("'", ''))


def heuristic_entity_aliases(name: str, entity_type: str) -> list[dict[str, Any]]:
    normalized = normalize_entity_name(name)
    if not normalized:
        return []
    candidates = [{
        'value': normalized,
        'source': 'user_input',
        'confidence': 'high',
        'reason': 'Original user-provided entity name.',
    }]
    suffix_stripped = normalize_whitespace(COMPANY_SUFFIX_RE.sub('', normalized)).strip(' ,.-')
    if suffix_stripped and suffix_stripped.casefold() != normalized.casefold():
        candidates.append({
            'value': suffix_stripped,
            'source': 'heuristic_normalization',
            'confidence': 'medium',
            'reason': 'Corporate suffix removed for broader matching.',
        })
    if normalized.isupper() and len(normalized) <= 10:
        candidates.append({
            'value': normalized.title(),
            'source': 'heuristic_case_variant',
            'confidence': 'low',
            'reason': 'Case-normalized alias candidate.',
        })
    if entity_type == 'assignee' and ' ' not in normalized and COMPANY_SUFFIX_RE.search(normalized) is None:
        for suffix in ['Corporation', 'Inc.', 'Ltd.']:
            candidates.append({
                'value': f'{normalized} {suffix}',
                'source': 'heuristic_corporate_suffix',
                'confidence': 'low',
                'reason': 'Low-confidence corporate suffix expansion for user confirmation.',
            })
    return candidates


def fetch_wikidata_aliases(name: str, entity_type: str, timeout_sec: int = 5) -> list[dict[str, Any]]:
    if not name:
        return []
    try:
        search_response = requests.get(
            WIKIDATA_SEARCH_URL,
            params={
                'action': 'wbsearchentities',
                'format': 'json',
                'language': 'en',
                'type': 'item',
                'limit': 3,
                'search': name,
            },
            timeout=timeout_sec,
        )
        search_response.raise_for_status()
        payload = search_response.json()
    except Exception:
        return []
    entity_ids = [item.get('id') for item in payload.get('search', []) if item.get('id')]
    if not entity_ids:
        return []
    try:
        entity_response = requests.get(
            WIKIDATA_SEARCH_URL,
            params={
                'action': 'wbgetentities',
                'format': 'json',
                'props': 'labels|aliases|descriptions',
                'languages': 'en|zh',
                'ids': '|'.join(entity_ids),
            },
            timeout=timeout_sec,
        )
        entity_response.raise_for_status()
        entities_payload = entity_response.json().get('entities', {})
    except Exception:
        return []
    candidates: list[dict[str, Any]] = []
    query_token = normalize_entity_name(name).casefold()
    for entity_id in entity_ids:
        entity = entities_payload.get(entity_id) or {}
        labels = entity.get('labels') or {}
        aliases = entity.get('aliases') or {}
        description = ((entity.get('descriptions') or {}).get('en') or {}).get('value', '')
        raw_names: list[str] = []
        raw_names.extend(label.get('value', '') for label in labels.values() if isinstance(label, dict))
        for alias_values in aliases.values():
            if isinstance(alias_values, list):
                raw_names.extend(item.get('value', '') for item in alias_values if isinstance(item, dict))
        for alias_name in dedupe_preserve_order([item for item in raw_names if item]):
            normalized_alias = normalize_entity_name(alias_name)
            if not normalized_alias:
                continue
            confidence = (
                'high' if query_token and query_token in normalized_alias.casefold()
                else 'medium' if entity_type == 'assignee'
                else 'low'
            )
            candidates.append({
                'value': normalized_alias,
                'source': 'wikidata',
                'confidence': confidence,
                'reason': f'Public alias candidate from Wikidata ({entity_id}{": " + description if description else ""}).',
            })
    return candidates


def fetch_wikipedia_titles(name: str, timeout_sec: int = 5) -> list[dict[str, Any]]:
    if not name:
        return []
    try:
        response = requests.get(
            WIKIPEDIA_OPENSEARCH_URL,
            params={
                'action': 'opensearch',
                'limit': 3,
                'namespace': 0,
                'format': 'json',
                'search': name,
            },
            timeout=timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    titles = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    results: list[dict[str, Any]] = []
    for title in titles:
        normalized = normalize_entity_name(title)
        if normalized:
            results.append({
                'value': normalized,
                'source': 'wikipedia',
                'confidence': 'low',
                'reason': 'Public title candidate from Wikipedia search.',
            })
    return results


def merge_alias_candidates(name: str, entity_type: str, manual_aliases: list[str]) -> list[dict[str, Any]]:
    candidates = heuristic_entity_aliases(name, entity_type)
    for alias in manual_aliases:
        candidates.append({
            'value': normalize_entity_name(alias),
            'source': 'user_alias',
            'confidence': 'medium',
            'reason': 'User-provided alias candidate pending confirmation.',
        })
    if name:
        candidates.extend(fetch_wikidata_aliases(name, entity_type))
        candidates.extend(fetch_wikipedia_titles(name))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = normalize_entity_name(candidate.get('value', ''))
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append({**candidate, 'value': value})
    return deduped[:10]


def entity_alias_payload(
    assignee: str | None,
    inventor: str | None,
    assignee_aliases: list[str],
    inventor_aliases: list[str],
    confirmed_assignee_aliases: list[str],
    confirmed_inventor_aliases: list[str],
) -> dict[str, Any]:
    payload = {'assignee': [], 'inventor': []}
    if clean_text(assignee) or assignee_aliases:
        payload['assignee'] = merge_alias_candidates(clean_text(assignee), 'assignee', assignee_aliases)
    if clean_text(inventor) or inventor_aliases:
        payload['inventor'] = merge_alias_candidates(clean_text(inventor), 'inventor', inventor_aliases)
    confirmed_assignee = dedupe_preserve_order(confirmed_assignee_aliases)
    confirmed_inventor = dedupe_preserve_order(confirmed_inventor_aliases)
    needs_user_confirmation = False
    if payload['assignee']:
        candidate_values = [item['value'] for item in payload['assignee']]
        expanded_values = [item for item in candidate_values if item.casefold() != clean_text(assignee).casefold()]
        if expanded_values and not confirmed_assignee:
            needs_user_confirmation = True
    if payload['inventor']:
        candidate_values = [item['value'] for item in payload['inventor']]
        expanded_values = [item for item in candidate_values if item.casefold() != clean_text(inventor).casefold()]
        if expanded_values and not confirmed_inventor:
            needs_user_confirmation = True
    return {
        'needs_user_confirmation': needs_user_confirmation,
        'alias_candidates': payload,
        'confirmation_prompt_payload': {
            'assignee': {
                'input': clean_text(assignee),
                'recommended': confirmed_assignee or [item['value'] for item in payload['assignee'][:3]],
            },
            'inventor': {
                'input': clean_text(inventor),
                'recommended': confirmed_inventor or [item['value'] for item in payload['inventor'][:3]],
            },
        },
    }


def normalize_query_term(term: str) -> str:
    normalized = normalize_whitespace(term)
    if not normalized:
        return ''
    return f'"{normalized}"' if ' ' in normalized or contains_chinese(normalized) else normalized


def join_or_group(terms: list[str]) -> str:
    normalized_terms = [normalize_query_term(term) for term in dedupe_preserve_order(terms) if normalize_query_term(term)]
    if not normalized_terms:
        return ''
    return normalized_terms[0] if len(normalized_terms) == 1 else '(' + ' OR '.join(normalized_terms) + ')'


def join_raw_group(terms: list[str]) -> str:
    normalized_terms = [normalize_whitespace(term) for term in dedupe_preserve_order(terms) if normalize_whitespace(term)]
    if not normalized_terms:
        return ''
    return normalized_terms[0] if len(normalized_terms) == 1 else '(' + ' OR '.join(normalized_terms) + ')'


def build_metadata_query_parts(inputs: dict[str, Any], use_confirmed_aliases: bool) -> tuple[list[str], dict[str, Any]]:
    advanced_fields = {
        'search_terms': clean_text(inputs.get('search_terms')),
        'technical_description_text': clean_text(inputs.get('technical_description_text')),
        'inventor': clean_text(inputs.get('inventor')),
        'assignee': clean_text(inputs.get('assignee')),
        'classification': clean_text(inputs.get('classification')),
        'date_from': clean_text(inputs.get('date_from')),
        'date_to': clean_text(inputs.get('date_to')),
        'patent_office': parse_text_list(inputs.get('patent_office')),
        'language': parse_text_list(inputs.get('language')),
        'status': parse_text_list(inputs.get('status')),
        'type': parse_text_list(inputs.get('type')),
        'must_include_terms': parse_text_list(inputs.get('must_include_terms')),
        'exclude_terms': parse_text_list(inputs.get('exclude_terms')),
    }
    parts: list[str] = []
    inventor_terms = parse_text_list(inputs.get('confirmed_inventor_aliases' if use_confirmed_aliases else 'inventor_aliases'))
    assignee_terms = parse_text_list(inputs.get('confirmed_assignee_aliases' if use_confirmed_aliases else 'assignee_aliases'))
    if not inventor_terms and clean_text(inputs.get('inventor')):
        inventor_terms = [clean_text(inputs.get('inventor'))]
    if not assignee_terms and clean_text(inputs.get('assignee')):
        assignee_terms = [clean_text(inputs.get('assignee'))]
    inventor_group = join_raw_group([f'inventor:{normalize_query_term(term)}' for term in inventor_terms])
    assignee_group = join_raw_group([f'assignee:{normalize_query_term(term)}' for term in assignee_terms])
    if inventor_group:
        parts.append(inventor_group)
    if assignee_group:
        parts.append(assignee_group)
    classification = clean_text(inputs.get('classification'))
    if classification:
        lowered = classification.lower()
        parts.append(
            classification if lowered.startswith(('cpc:', 'ipc:'))
            else f'cpc:{classification}' if '/' in classification
            else f'ipc:{classification}'
        )
    office_group = join_raw_group(
        [f'country:{office.upper()}' for office in parse_text_list(inputs.get('patent_office')) if office]
    )
    language_group = join_raw_group(
        [f'language:{normalize_whitespace(language).lower()}' for language in parse_text_list(inputs.get('language')) if language]
    )
    status_group = join_raw_group(
        [f'status:{normalize_whitespace(status).lower()}' for status in parse_text_list(inputs.get('status')) if status]
    )
    if office_group:
        parts.append(office_group)
    if language_group:
        parts.append(language_group)
    if status_group:
        parts.append(status_group)
    for term in parse_text_list(inputs.get('exclude_terms')):
        token = normalize_query_term(term)
        if token:
            parts.append(f'-{token}')
    date_from = clean_text(inputs.get('date_from'))
    date_to = clean_text(inputs.get('date_to'))
    if date_from:
        parts.append(f'after:{date_from}')
    if date_to:
        parts.append(f'before:{date_to}')
    return parts, advanced_fields


def looks_like_advanced_query(text: str) -> bool:
    return bool(BOOLEAN_QUERY_HINT_RE.search(text))


def build_search_term_groups(inputs: dict[str, Any]) -> dict[str, Any]:
    search_terms = clean_text(inputs.get('search_terms'))
    technical_description_text = clean_text(inputs.get('technical_description_text'))
    must_include_terms = parse_text_list(inputs.get('must_include_terms'))
    mode = clean_text(inputs.get('search_input_mode')) or 'query'
    if mode == 'technical_description':
        translation = build_translation_candidates(technical_description_text, must_include_terms)
        english_terms = translation['expansion_terms']['english']
        chinese_terms = translation['expansion_terms']['chinese']
        mixed_terms = translation['expansion_terms']['mixed']
        concept_terms = translation['concept_terms']
        primary_object = clean_text(concept_terms.get('primary_object'))
        key_mechanism = clean_text(concept_terms.get('key_mechanism'))
        technical_effect = clean_text(concept_terms.get('technical_effect'))
        core_seed = dedupe_preserve_order(
            [primary_object, key_mechanism] + english_terms[:2] + chinese_terms[:2] + must_include_terms[:1]
        )
        balanced_seed = dedupe_preserve_order(
            [primary_object, key_mechanism, technical_effect]
            + english_terms[:4]
            + chinese_terms[:4]
            + must_include_terms[:2]
        )
        recall_seed = dedupe_preserve_order(mixed_terms[:6] + chinese_terms[:4] + must_include_terms[:3])
        if not core_seed:
            core_seed = dedupe_preserve_order(chinese_terms[:2] + english_terms[:2] + must_include_terms[:1])
        if not balanced_seed:
            balanced_seed = dedupe_preserve_order(core_seed + mixed_terms[:4] + must_include_terms[:2])
        if not recall_seed:
            recall_seed = dedupe_preserve_order(balanced_seed + mixed_terms[:4])
        return {
            'analysis_summary': translation['analysis_summary'],
            'concept_terms': concept_terms,
            'expansion_terms': translation['expansion_terms'],
            'preferred_language': translation['preferred_language'],
            'english_track_confidence': translation['english_track_confidence'],
            'core_strict_terms': core_seed,
            'balanced_terms': balanced_seed,
            'recall_terms': recall_seed,
            'verbatim_query': '',
        }

    raw_terms = dedupe_preserve_order(parse_text_list(search_terms) + must_include_terms)
    english_terms = [term for term in raw_terms if not contains_chinese(term)]
    chinese_terms = [term for term in raw_terms if contains_chinese(term)]
    mixed_terms = dedupe_preserve_order(raw_terms)
    concept_terms = {
        'primary_object': raw_terms[0] if raw_terms else '',
        'key_mechanism': raw_terms[1] if len(raw_terms) > 1 else '',
        'technical_effect': '',
        'scenarios': [],
        'classification_hints': extract_classification_hints(search_terms),
    }
    translation = {
        'analysis_summary': normalize_whitespace(search_terms) or 'Direct query mode',
        'concept_terms': concept_terms,
        'expansion_terms': {
            'english': english_terms,
            'chinese': chinese_terms,
            'mixed': mixed_terms,
        },
        'preferred_language': 'english' if english_terms else 'mixed',
        'english_track_confidence': 'high' if english_terms else 'low',
    }
    verbatim_query = search_terms if looks_like_advanced_query(search_terms) else ''
    core_seed = [search_terms] if search_terms and not verbatim_query else dedupe_preserve_order((english_terms or mixed_terms)[:3] + must_include_terms[:1])
    balanced_seed = [search_terms] if search_terms and not verbatim_query else dedupe_preserve_order((english_terms or mixed_terms)[:4] + chinese_terms[:2] + must_include_terms[:2])
    recall_seed = [search_terms] if search_terms and not verbatim_query else dedupe_preserve_order(mixed_terms[:5] + chinese_terms[:3] + must_include_terms[:2])
    return {
        'analysis_summary': translation['analysis_summary'],
        'concept_terms': concept_terms,
        'expansion_terms': translation['expansion_terms'],
        'preferred_language': translation['preferred_language'],
        'english_track_confidence': translation['english_track_confidence'],
        'core_strict_terms': core_seed,
        'balanced_terms': balanced_seed,
        'recall_terms': recall_seed,
        'verbatim_query': verbatim_query,
    }


def build_query_sets(inputs: dict[str, Any], use_confirmed_aliases: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    term_groups = build_search_term_groups(inputs)
    metadata_parts, advanced_fields = build_metadata_query_parts(inputs, use_confirmed_aliases=use_confirmed_aliases)
    operator_labels = ['AND', 'quotes']
    for part in metadata_parts:
        for label in ('inventor:', 'assignee:', 'country:', 'status:', 'language:', 'after:', 'before:', 'ipc:', 'cpc:'):
            if label in part and label not in operator_labels:
                operator_labels.append(label)

    verbatim_query = clean_text(term_groups.get('verbatim_query'))
    if verbatim_query:
        core_query_parts = [verbatim_query]
        balanced_query_parts = [verbatim_query]
        recall_query_parts = [verbatim_query]
    else:
        core_query_parts = [join_or_group(term_groups['core_strict_terms'][:4])]
        balanced_query_parts = [
            join_or_group(term_groups['balanced_terms'][:4]),
            join_raw_group([f'TI={normalize_query_term(term)}' for term in term_groups['balanced_terms'][:2]]),
        ]
        recall_query_parts = [join_or_group(term_groups['recall_terms'][:7])]

    must_include_terms = parse_text_list(inputs.get('must_include_terms'))
    if must_include_terms and not verbatim_query:
        core_query_parts.append(join_or_group(must_include_terms[:2]))
        balanced_query_parts.append(join_or_group(must_include_terms[:3]))
        recall_query_parts.append(join_or_group(must_include_terms[:3]))

    query_sets = [
        {
            'strategy_name': 'core_strict',
            'query': ' AND '.join(part for part in core_query_parts + metadata_parts if part),
            'why_this_query': 'Shortest stable query anchored on the primary technical object and mechanism.',
            'operators_used': operator_labels,
            'risk_note': 'Highest precision and lowest recall. Best first pass for relevance-sorted review.',
            'recommended_order': 1,
        },
        {
            'strategy_name': 'balanced',
            'query': ' AND '.join(part for part in balanced_query_parts + metadata_parts if part),
            'why_this_query': 'Adds controlled field focus and light synonym expansion without over-constraining the search.',
            'operators_used': ['AND', 'OR', 'TI=', 'quotes'] + [label for label in operator_labels if label not in {'AND', 'quotes'}],
            'risk_note': 'Balanced recall and precision. Use after core_strict if too few or too narrow results appear.',
            'recommended_order': 2,
        },
        {
            'strategy_name': 'recall_fallback',
            'query': ' AND '.join(part for part in recall_query_parts + metadata_parts if part),
            'why_this_query': 'Relaxes field focus and keeps a broader concept blend to avoid empty or overly narrow result sets.',
            'operators_used': ['AND', 'OR', 'quotes'] + [label for label in operator_labels if label not in {'AND', 'quotes'}],
            'risk_note': 'Highest recall. Review relevance carefully before exporting or bridging into detail mode.',
            'recommended_order': 3,
        },
    ]
    return query_sets, {
        'analysis_summary': term_groups['analysis_summary'],
        'concept_terms': term_groups['concept_terms'],
        'expansion_terms': term_groups['expansion_terms'],
        'preferred_language': term_groups['preferred_language'],
        'english_track_confidence': term_groups['english_track_confidence'],
        'advanced_fields': advanced_fields,
    }


def build_alias_workflow(inputs: dict[str, Any]) -> dict[str, Any]:
    return entity_alias_payload(
        assignee=clean_text(inputs.get('assignee')),
        inventor=clean_text(inputs.get('inventor')),
        assignee_aliases=parse_text_list(inputs.get('assignee_aliases')),
        inventor_aliases=parse_text_list(inputs.get('inventor_aliases')),
        confirmed_assignee_aliases=parse_text_list(inputs.get('confirmed_assignee_aliases')),
        confirmed_inventor_aliases=parse_text_list(inputs.get('confirmed_inventor_aliases')),
    )


def build_search_plan(inputs: dict[str, Any]) -> dict[str, Any]:
    alias_payload = build_alias_workflow(inputs)
    query_sets_draft, search_analysis = build_query_sets(inputs, use_confirmed_aliases=False)
    query_sets = [] if alias_payload['needs_user_confirmation'] else build_query_sets(inputs, use_confirmed_aliases=True)[0]
    strategy_catalog = load_query_patterns()
    return {
        'analysis_summary': search_analysis['analysis_summary'],
        'concept_terms': search_analysis['concept_terms'],
        'expansion_terms': search_analysis['expansion_terms'],
        'preferred_language': search_analysis['preferred_language'],
        'english_track_confidence': search_analysis['english_track_confidence'],
        'alias_candidates': alias_payload['alias_candidates'],
        'needs_user_confirmation': alias_payload['needs_user_confirmation'],
        'confirmation_prompt_payload': alias_payload['confirmation_prompt_payload'],
        'query_sets_draft': query_sets_draft,
        'query_sets': query_sets,
        'strategy_catalog': strategy_catalog,
        'advanced_fields': search_analysis['advanced_fields'],
    }


def debug_dump(inputs: dict[str, Any]) -> str:
    return json.dumps(build_search_plan(inputs), ensure_ascii=False, indent=2)
