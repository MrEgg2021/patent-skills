# 专利 OCR 结构化 Schema

本 schema 用于把 MinerU 输出转成专利工作流可复用的数据包。

## 顶层结构

`patent_ocr_bundle.json`：

```json
{
  "created_at": "2026-06-12T12:00:00+08:00",
  "source": "D:/case/scan.pdf",
  "profile": "patent-application",
  "title": "一种...",
  "mineru": {},
  "input_files": {},
  "sections": {},
  "claims": [],
  "figures": {},
  "content_stats": {},
  "material_cues": {},
  "quality_report": {},
  "outputs": {}
}
```

## profile 枚举

| profile | 用途 |
|---|---|
| `patent-application` | 中国发明/实用新型申请文件 |
| `official-patent` | 公告文本、授权文本、公开文本 |
| `disclosure` | 发明人交底书、技术说明材料 |
| `scanned-patent` | 扫描版专利全文 |
| `drawings` | 附图、摘要附图、标号页 |
| `material-scan` | 胶底、橡胶、材料配方、实验记录 |

## sections

每个章节对象：

```json
{
  "heading": "权利要求书",
  "label": "权利要求书",
  "start_line": 10,
  "end_line": 80,
  "content": "1. 一种..."
}
```

标准章节键：

- `abstract`
- `claims`
- `description`
- `technical_field`
- `background`
- `summary`
- `drawings_brief`
- `embodiments`
- `drawings`
- `disclosure_problem`
- `disclosure_solution`
- `disclosure_effect`
- `material_formula`
- `test_data`
- `unclassified`

## claims

每条权利要求对象：

```json
{
  "number": "1",
  "text": "一种...其特征在于...",
  "type_hint": "independent",
  "has_characterizing_clause": true
}
```

规则：

1. `text` 以 OCR 原文为主，允许清理多余空格，不允许改写技术特征。
2. `type_hint` 仅做启发式判断。出现“根据权利要求X”时标为 `dependent`，否则标为 `independent`。
3. `has_characterizing_clause=false` 只代表需要人工确认，不代表必然错误。

## figures

```json
{
  "figure_mentions": ["图1", "图2"],
  "figure_count_hint": 2,
  "label_lines": ["10-支架", "20、固定座"],
  "label_count_hint": 2
}
```

使用规则：

- 正文出现图号但 `label_count_hint=0` 时，质量报告必须提示人工检查；
- 标号行不代表已经完整识别，应与原附图逐项对照；
- 图号顺序异常、跳号、重复图号属于后续增强项。

## content_stats

来自 MinerU `content_list.json` 的统计：

```json
{
  "items": 100,
  "tables": 3,
  "images": 8,
  "equations": 0,
  "discarded_blocks": 12,
  "pages": [0, 1, 2],
  "page_count_hint": 3
}
```

用途：

- 表格数量用于判断配方/实验数据是否可能丢失；
- 图片数量用于附图页完整性判断；
- discarded blocks 用于页眉页脚、页码、边注风险复核。

## material_cues

```json
{
  "terms": ["胶底", "橡胶", "重量份", "硬度"],
  "numeric_patterns": {
    "percentage": 2,
    "parts_by_weight": 5,
    "temperature": 1,
    "hardness": 1
  },
  "material_like": true
}
```

材料/胶底资料重点：

- 组分名不能被 OCR 合并或拆分；
- `重量份`、`质量份`、百分比、温度、硬度等单位必须保留；
- 表格错列会改变配方含义，必须在质量报告中提示人工核对；
- 若材料线索存在但 MinerU 未识别表格，应优先回看原图。

## quality_report

```json
{
  "missing_sections": ["权利要求书"],
  "ocr_spacing_heading_hits": ["权 利 要 求 书"],
  "warnings": ["缺少或未识别关键专利章节：权利要求书"],
  "risk_level": "medium",
  "manual_review_required": true
}
```

风险等级：

- `low`：无自动警告；
- `medium`：有 1-2 条警告；
- `high`：有 3 条以上警告。

## 与其他技能的接口

| 下游 skill | 推荐输入 |
|---|---|
| `claims-feature-decomposition` | `patent_ocr_bundle.json.claims` + `sections.description` |
| `disclosure-review` | `sections.disclosure_*` + `material_cues` |
| `patent-formality-review` | 仅作为 OCR 前处理，不替代 DOCX 形式审查 |
| 撰写类 skill | `sections`、`material_cues`、`figures` 和质量报告 |

## 不做的事

- 不自动改写权利要求；
- 不从 OCR 文本推断新技术特征；
- 不把缺失章节补造出来；
- 不把材料配方表格的错列结果直接作为事实；
- 不替代人工核对原始 PDF/附图。
