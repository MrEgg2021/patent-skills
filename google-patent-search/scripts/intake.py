#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SKILL_NAME = 'google-patent-search'
SEARCH_MODE = 'search'
DETAIL_MODE = 'detail'
DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}$'
PUBLICATION_PATTERN = r'^[A-Za-z]{2}(?=.*\d)[A-Za-z0-9./-]+$'

FIELD_DEFS: dict[str, dict[str, Any]] = {
    'mode': {
        'key': 'mode',
        'label': 'mode',
        'required': True,
        'type': 'enum',
        'options': [SEARCH_MODE, DETAIL_MODE],
        'description': 'Choose search for result collection or detail for publication export.',
    },
    'project_id': {
        'key': 'project_id',
        'label': 'project_id',
        'required': True,
        'type': 'int',
        'min': 1,
    },
    'search_input_mode': {
        'key': 'search_input_mode',
        'label': 'search_input_mode',
        'required': False,
        'type': 'enum',
        'options': ['query', 'technical_description'],
        'default': 'query',
        'description': 'Choose direct query mode or technical-description mode.',
    },
    'search_terms': {
        'key': 'search_terms',
        'label': 'search_terms',
        'required': False,
        'type': 'text',
        'description': 'Direct Boolean or keyword query for search_input_mode=query.',
    },
    'technical_description_text': {
        'key': 'technical_description_text',
        'label': 'technical_description_text',
        'required': False,
        'type': 'text',
        'description': 'One-sentence technical idea or longer disclosure excerpt for search_input_mode=technical_description.',
    },
    'inventor': {
        'key': 'inventor',
        'label': 'inventor',
        'required': False,
        'type': 'text',
        'prompt_optional': True,
    },
    'assignee': {
        'key': 'assignee',
        'label': 'assignee',
        'required': False,
        'type': 'text',
        'prompt_optional': True,
    },
    'classification': {
        'key': 'classification',
        'label': 'classification',
        'required': False,
        'type': 'text',
        'prompt_optional': True,
    },
    'date_from': {
        'key': 'date_from',
        'label': 'date_from',
        'required': False,
        'type': 'text',
        'prompt_optional': True,
        'pattern': DATE_PATTERN,
    },
    'date_to': {
        'key': 'date_to',
        'label': 'date_to',
        'required': False,
        'type': 'text',
        'prompt_optional': True,
        'pattern': DATE_PATTERN,
    },
    'must_include_terms': {
        'key': 'must_include_terms',
        'label': 'must_include_terms',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'exclude_terms': {
        'key': 'exclude_terms',
        'label': 'exclude_terms',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'patent_office': {
        'key': 'patent_office',
        'label': 'patent_office',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'language': {
        'key': 'language',
        'label': 'language',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'status': {
        'key': 'status',
        'label': 'status',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'type': {
        'key': 'type',
        'label': 'type',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'assignee_aliases': {
        'key': 'assignee_aliases',
        'label': 'assignee_aliases',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'inventor_aliases': {
        'key': 'inventor_aliases',
        'label': 'inventor_aliases',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'confirmed_assignee_aliases': {
        'key': 'confirmed_assignee_aliases',
        'label': 'confirmed_assignee_aliases',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'confirmed_inventor_aliases': {
        'key': 'confirmed_inventor_aliases',
        'label': 'confirmed_inventor_aliases',
        'required': False,
        'type': 'text_list',
        'prompt_optional': True,
    },
    'max_results': {
        'key': 'max_results',
        'label': 'max_results',
        'required': False,
        'type': 'int',
        'default': 20,
        'min': 1,
        'max': 100,
        'prompt_optional': True,
    },
    'detail_input_mode': {
        'key': 'detail_input_mode',
        'label': 'detail_input_mode',
        'required': False,
        'type': 'enum',
        'options': ['single', 'batch', 'results_json'],
        'description': 'Choose how detail publications are supplied.',
    },
    'publication_number': {
        'key': 'publication_number',
        'label': 'publication_number',
        'required': False,
        'type': 'text',
        'pattern': PUBLICATION_PATTERN,
    },
    'patent_list_file': {
        'key': 'patent_list_file',
        'label': 'patent_list_file',
        'required': False,
        'type': 'text',
        'pattern': r'^.+\.(csv|xlsx)$',
    },
    'results_json_file': {
        'key': 'results_json_file',
        'label': 'results_json_file',
        'required': False,
        'type': 'text',
        'pattern': r'^.+\.json$',
    },
    'file_formats': {
        'key': 'file_formats',
        'label': 'file_formats',
        'required': False,
        'type': 'enum',
        'options': ['docx', 'pdf', 'both'],
        'default': 'both',
    },
    'proxy_url': {
        'key': 'proxy_url',
        'label': 'proxy_url',
        'required': False,
        'type': 'text',
        'default': '',
        'prompt_optional': True,
    },
    'request_timeout_sec': {
        'key': 'request_timeout_sec',
        'label': 'request_timeout_sec',
        'required': False,
        'type': 'int',
        'default': 30,
        'min': 5,
        'max': 120,
        'prompt_optional': True,
    },
    'use_hd_drawings': {
        'key': 'use_hd_drawings',
        'label': 'use_hd_drawings',
        'required': False,
        'type': 'bool',
        'default': True,
        'prompt_optional': True,
    },
    'include_abstract': {
        'key': 'include_abstract',
        'label': 'include_abstract',
        'required': False,
        'type': 'bool',
        'default': True,
        'prompt_optional': True,
    },
    'include_claims': {
        'key': 'include_claims',
        'label': 'include_claims',
        'required': False,
        'type': 'bool',
        'default': True,
        'prompt_optional': True,
    },
    'include_description': {
        'key': 'include_description',
        'label': 'include_description',
        'required': False,
        'type': 'bool',
        'default': True,
        'prompt_optional': True,
    },
    'include_drawings': {
        'key': 'include_drawings',
        'label': 'include_drawings',
        'required': False,
        'type': 'bool',
        'default': True,
        'prompt_optional': True,
    },
}

SEARCH_FIELD_KEYS = [
    'search_input_mode',
    'search_terms',
    'technical_description_text',
    'inventor',
    'assignee',
    'classification',
    'date_from',
    'date_to',
    'must_include_terms',
    'exclude_terms',
    'patent_office',
    'language',
    'status',
    'type',
    'assignee_aliases',
    'inventor_aliases',
    'confirmed_assignee_aliases',
    'confirmed_inventor_aliases',
    'max_results',
]
DETAIL_FIELD_KEYS = [
    'detail_input_mode',
    'publication_number',
    'patent_list_file',
    'results_json_file',
    'file_formats',
    'proxy_url',
    'request_timeout_sec',
    'use_hd_drawings',
    'include_abstract',
    'include_claims',
    'include_description',
    'include_drawings',
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == '') or (
        isinstance(value, list) and len(value) == 0
    )


def clean_text(value: Any) -> str:
    return '' if value is None else str(value).strip()


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if token in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return None


def parse_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = [clean_text(item) for item in value if clean_text(item)]
        return list(dict.fromkeys(parts))
    text = clean_text(value)
    if not text:
        return []
    parts = [part.strip() for part in re.split(r'[\n,;|]+', text) if part.strip()]
    return list(dict.fromkeys(parts))


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


def normalize(field: dict[str, Any], value: Any) -> Any:
    if value is None:
        if 'default' in field:
            return field.get('default')
        return None

    field_type = field.get('type', 'text')
    if field_type == 'int':
        if isinstance(value, int):
            return value
        text = clean_text(value)
        return None if text == '' else int(text)
    if field_type == 'bool':
        parsed = parse_bool(value)
        if parsed is None:
            raise ValueError('bad bool')
        return parsed
    if field_type == 'enum':
        return clean_text(value)
    if field_type == 'text_list':
        return parse_text_list(value)
    return clean_text(value)


def prompt_enum(field: dict[str, Any]) -> str:
    label = field.get('label', field['key'])
    options = list(field.get('options') or [])
    default = field.get('default')
    print(f'\n[{label}] choose one:')
    for idx, option in enumerate(options, 1):
        marker = ' (default)' if option == default else ''
        print(f'  {idx}. {option}{marker}')
    while True:
        raw = input('Enter number or value: ').strip()
        if raw == '' and default is not None:
            return str(default)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print('Invalid option. Try again.')


def prompt_field(field: dict[str, Any]) -> Any:
    field_type = field.get('type', 'text')
    label = field.get('label', field['key'])
    default = field.get('default')
    if field_type == 'enum':
        return prompt_enum(field)
    if field_type == 'bool':
        suffix = f" [default={'yes' if default else 'no'}]" if default is not None else ''
        while True:
            raw = input(f'{label} (yes/no){suffix}: ').strip()
            if raw == '' and default is not None:
                return default
            parsed = parse_bool(raw)
            if parsed is not None:
                return parsed
            print('Please enter yes or no.')
    suffix = f' [default={default}]' if default not in (None, '') else ''
    raw = input(f'{label}{suffix}: ').strip()
    if raw == '' and default is not None:
        return default
    if field_type == 'text_list':
        return parse_text_list(raw)
    return raw


def relevant_field_keys(mode: str | None) -> list[str]:
    return SEARCH_FIELD_KEYS if mode == SEARCH_MODE else DETAIL_FIELD_KEYS


def resolve_mode(answers: dict[str, Any]) -> str | None:
    mode = clean_text(answers.get('mode'))
    return mode or None


def resolve_detail_input_mode(answers: dict[str, Any]) -> str | None:
    explicit = clean_text(answers.get('detail_input_mode'))
    if explicit:
        return explicit
    has_single = not is_blank(answers.get('publication_number'))
    has_batch = not is_blank(answers.get('patent_list_file'))
    has_results = not is_blank(answers.get('results_json_file'))
    if has_single and not has_batch and not has_results:
        return 'single'
    if has_batch and not has_single and not has_results:
        return 'batch'
    if has_results and not has_single and not has_batch:
        return 'results_json'
    return None


def collect_answers(answers: dict[str, Any]) -> dict[str, Any]:
    print()
    print(f'=== {SKILL_NAME} intake ===')

    if is_blank(answers.get('mode')):
        answers['mode'] = prompt_field(FIELD_DEFS['mode'])
    mode = resolve_mode(answers)

    for key in ['project_id'] + relevant_field_keys(mode):
        field = FIELD_DEFS[key]
        if field.get('required') and is_blank(answers.get(key)):
            answers[key] = prompt_field(field)

    if mode == SEARCH_MODE and is_blank(answers.get('search_input_mode')):
        answers['search_input_mode'] = prompt_field(FIELD_DEFS['search_input_mode'])

    if mode == DETAIL_MODE and is_blank(answers.get('detail_input_mode')):
        answers['detail_input_mode'] = prompt_field(FIELD_DEFS['detail_input_mode'])

    detail_mode = resolve_detail_input_mode(answers)
    if mode == DETAIL_MODE:
        if detail_mode == 'single' and is_blank(answers.get('publication_number')):
            answers['publication_number'] = prompt_field(FIELD_DEFS['publication_number'])
        if detail_mode == 'batch' and is_blank(answers.get('patent_list_file')):
            answers['patent_list_file'] = prompt_field(FIELD_DEFS['patent_list_file'])
        if detail_mode == 'results_json' and is_blank(answers.get('results_json_file')):
            answers['results_json_file'] = prompt_field(FIELD_DEFS['results_json_file'])

    for key in relevant_field_keys(mode):
        field = FIELD_DEFS[key]
        if (not field.get('required')) and field.get('prompt_optional') and is_blank(answers.get(key)):
            answers[key] = prompt_field(field)

    return answers


def validate_field(field: dict[str, Any], value: Any) -> list[str]:
    errors: list[str] = []
    key = field['key']

    if is_blank(value):
        return errors

    field_type = field.get('type', 'text')
    if field_type == 'enum':
        options = field.get('options') or []
        if value not in options:
            errors.append(f'{key}:invalid_option')
        return errors

    if field_type == 'int':
        if not isinstance(value, int):
            return [f'{key}:not_integer']
        minimum = field.get('min')
        maximum = field.get('max')
        if minimum is not None and value < minimum:
            errors.append(f'{key}:below_min_{minimum}')
        if maximum is not None and value > maximum:
            errors.append(f'{key}:above_max_{maximum}')
        return errors

    if field_type == 'bool':
        if not isinstance(value, bool):
            errors.append(f'{key}:not_boolean')
        return errors

    if field_type == 'text_list':
        if not isinstance(value, list):
            errors.append(f'{key}:not_list')
        return errors

    if isinstance(value, str):
        pattern = field.get('pattern')
        if pattern and re.fullmatch(pattern, value) is None:
            errors.append(f'{key}:pattern_mismatch')
    return errors


def validate_answers(answers: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(answers)
    errors: list[str] = []

    for key, field in FIELD_DEFS.items():
        try:
            normalized[key] = normalize(field, normalized.get(key))
        except Exception:
            errors.append(f'{key}:normalization_failed')

    mode = resolve_mode(normalized)
    normalized['mode'] = mode
    if mode not in {SEARCH_MODE, DETAIL_MODE}:
        errors.append('mode:required')
        return normalized, sorted(set(errors))

    project_id = normalized.get('project_id')
    if is_blank(project_id):
        errors.append('project_id:required')
    else:
        errors.extend(validate_field(FIELD_DEFS['project_id'], project_id))

    if mode == SEARCH_MODE:
        search_input_mode = clean_text(normalized.get('search_input_mode')) or 'query'
        normalized['search_input_mode'] = search_input_mode
        if search_input_mode not in {'query', 'technical_description'}:
            errors.append('search_input_mode:invalid_option')
        if search_input_mode == 'query' and is_blank(normalized.get('search_terms')):
            errors.append('search_terms:required_for_query_mode')
        if search_input_mode == 'technical_description' and is_blank(normalized.get('technical_description_text')):
            errors.append('technical_description_text:required_for_technical_description_mode')
        for key in SEARCH_FIELD_KEYS:
            errors.extend(validate_field(FIELD_DEFS[key], normalized.get(key)))
    else:
        detail_input_mode = resolve_detail_input_mode(normalized)
        normalized['detail_input_mode'] = detail_input_mode
        if detail_input_mode not in {'single', 'batch', 'results_json'}:
            errors.append('detail_input_mode:required_for_detail')
        for key in DETAIL_FIELD_KEYS:
            field = FIELD_DEFS[key]
            value = normalized.get(key)
            if key == 'publication_number' and detail_input_mode == 'single' and is_blank(value):
                errors.append('publication_number:required_for_single')
            if key == 'patent_list_file' and detail_input_mode == 'batch' and is_blank(value):
                errors.append('patent_list_file:required_for_batch')
            if key == 'results_json_file' and detail_input_mode == 'results_json' and is_blank(value):
                errors.append('results_json_file:required_for_results_json')
            if key not in {'publication_number', 'patent_list_file', 'results_json_file'} or not is_blank(value):
                errors.extend(validate_field(field, value))

    return normalized, sorted(set(errors))


def build_search_payload(answers: dict[str, Any]) -> dict[str, Any] | None:
    if answers.get('mode') != SEARCH_MODE:
        return None
    search_input_mode = answers.get('search_input_mode') or 'query'
    if search_input_mode == 'query' and is_blank(answers.get('search_terms')):
        return None
    if search_input_mode == 'technical_description' and is_blank(answers.get('technical_description_text')):
        return None
    try:
        from search import build_automation_payload
    except Exception:
        return None
    try:
        return build_automation_payload(
            search_terms=answers.get('search_terms'),
            inventor=answers.get('inventor'),
            assignee=answers.get('assignee'),
            classification=answers.get('classification'),
            date_from=answers.get('date_from'),
            date_to=answers.get('date_to'),
            max_results=answers.get('max_results'),
            search_input_mode=answers.get('search_input_mode'),
            technical_description_text=answers.get('technical_description_text'),
            must_include_terms=answers.get('must_include_terms'),
            exclude_terms=answers.get('exclude_terms'),
            patent_office=answers.get('patent_office'),
            language=answers.get('language'),
            status=answers.get('status'),
            type=answers.get('type'),
            assignee_aliases=answers.get('assignee_aliases'),
            inventor_aliases=answers.get('inventor_aliases'),
            confirmed_assignee_aliases=answers.get('confirmed_assignee_aliases'),
            confirmed_inventor_aliases=answers.get('confirmed_inventor_aliases'),
        )
    except Exception:
        return None


def build_required_inputs(answers: dict[str, Any]) -> dict[str, Any]:
    mode = answers.get('mode')
    required_inputs: dict[str, Any] = {
        'mode': mode,
        'project_id': answers.get('project_id'),
    }
    if mode == SEARCH_MODE:
        for key in SEARCH_FIELD_KEYS:
            required_inputs[key] = answers.get(key)
        return required_inputs

    required_inputs.update(
        {
            'detail_input_mode': answers.get('detail_input_mode'),
            'file_formats': answers.get('file_formats'),
            'proxy_url': answers.get('proxy_url'),
            'request_timeout_sec': answers.get('request_timeout_sec'),
            'use_hd_drawings': answers.get('use_hd_drawings'),
            'include_abstract': answers.get('include_abstract'),
            'include_claims': answers.get('include_claims'),
            'include_description': answers.get('include_description'),
            'include_drawings': answers.get('include_drawings'),
        }
    )
    detail_input_mode = answers.get('detail_input_mode')
    if detail_input_mode == 'single':
        required_inputs['publication_number'] = answers.get('publication_number')
    elif detail_input_mode == 'batch':
        required_inputs['patent_list_file'] = answers.get('patent_list_file')
    elif detail_input_mode == 'results_json':
        required_inputs['results_json_file'] = answers.get('results_json_file')
    return required_inputs


def build_output(answers: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    result = {
        'skill_name': SKILL_NAME,
        'timestamp': now_iso(),
        'required_inputs': build_required_inputs(answers),
        'stage_plan': [],
        'validation_errors': errors,
        'ready': len(errors) == 0,
    }
    payload = build_search_payload(answers)
    if payload is not None:
        result['search_payload'] = payload
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=f'{SKILL_NAME} intake collector')
    parser.add_argument('--answers')
    parser.add_argument('--answers-file')
    parser.add_argument('--non-interactive', action='store_true')
    args = parser.parse_args()

    answers = load_answers(args)
    if not args.non_interactive:
        answers = collect_answers(answers)

    normalized, errors = validate_answers(answers)
    print(json.dumps(build_output(normalized, errors), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
