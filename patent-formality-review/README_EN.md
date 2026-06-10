# Patent Formality Review Tool

> Automated formality review for Chinese invention/utility model patent application drafts, based on **101 rules** consolidated from self-check tables published by **19** Intellectual Property Protection Centers.

[中文说明](./README.md)

---

## ✨ Key Features

- **101 Comprehensive Rules**: Covers all four sections — Abstract (F-1~F-16), Claims (F-17~F-46), Specification (F-47~F-78), and Drawings (F-79~F-101)
- **19 Protection Centers Covered**: Jilin, Xuzhou, Zhejiang, Beijing, Shanxi, Gansu, Changsha, Changchun, Fujian, Xi'an, Inner Mongolia, Shaanxi, Anhui, Liaoning, Hubei, Hefei, Changzhou, Suzhou, Tianjin
- **Three-Tier Rule Classification**:
  - 🔵 **Type A** (36 rules): Fully automated script checks
  - 🟡 **Type B** (42 rules): Script extraction + LLM judgment
  - 🔴 **Type C** (23 rules): Pure LLM semantic review
- **Center Selection Mechanism**: Select your target protection center — all 101 rules are checked, but disputed/unique items are judged according to the selected center's standards. Unlisted centers trigger the strictest mode.
- **Structured DOCX Report**: 8-chapter professional review report with issue location, severity, source center, and fix suggestions

---

## 📋 Review Scope

| Section | Rule IDs | Count |
|---------|----------|-------|
| Abstract | F-1 ~ F-16 | 16 |
| Claims | F-17 ~ F-46 | 30 |
| Specification | F-47 ~ F-78 | 32 |
| Drawings | F-79 ~ F-101 | 23 |

**Supported**: Chinese invention patents and utility model patents in DOCX format

**Not covered**: Design patents, request forms, power of attorney, statement of opinions

---

## 🚀 Getting Started

### Install Dependencies

```bash
pip install python-docx Pillow lxml
```

### Usage

This tool is designed as a [WorkBuddy](https://www.codebuddy.cn) Skill but can also be used standalone:

```python
from scripts.docx_parser import DocxSectionParser
from scripts.formality_scanner import FormalityScanner

# 1. Parse the DOCX file
parser = DocxSectionParser("your_patent_file.docx")
parsed_doc = parser.parse()

# 2. Run Type-A automated scan (specify target center)
scanner = FormalityScanner(parsed_doc, target_center="Anhui")
results = scanner.scan_all()

# 3. View results
for r in results:
    print(f"[{r['rule_id']}] {r['status']} - {r['message']}")
```

In WorkBuddy, simply use a trigger phrase to start the full review process:

> 形式审查 / 形式自检 / 预审自检 / 预审检查 / 格式扫描 / 格式检查

---

## 📁 Project Structure

```
patent-formality-review/
├── SKILL.md                              # Skill definition (execution flow, rule system)
├── README.md                             # Chinese README
├── README_EN.md                          # English README (this file)
├── LICENSE                               # MIT License
├── .gitignore
├── scripts/
│   ├── docx_parser.py                    # DOCX section parser
│   │                                     #  - Identifies 4 sections via section breaks + headers
│   │                                     #  - Extracts text, figure marks, images, tables, formulas
│   │                                     #  - Auto-detects patent type and invention title
│   └── formality_scanner.py              # Type-A automated scanner (36 rules)
│                                          #  - Contains CENTER_DISPUTE_CONFIG
│                                          #  - Supports center-specific judgment logic
├── references/
│   ├── abstract-checklist.md             # F-1~F-16 Abstract review checklist (Type B/C)
│   ├── claims-checklist.md               # F-17~F-46 Claims review checklist (Type B/C)
│   ├── spec-checklist.md                 # F-47~F-78 Specification review checklist (Type B/C)
│   ├── drawings-checklist.md             # F-79~F-101 Drawings review checklist (Type B/C)
│   ├── word_count_wps.py                 # Chinese word count algorithm for WPS/Word
│   └── python-docx-boilerplate.md        # python-docx boilerplate for generating DOCX reports
```

---

## 🧠 Core Design

### Three-Tier Rule System

| Type | Count | Execution | Example Rules |
|------|-------|-----------|---------------|
| Type A (Automated) | 36 | Pure Python script | Abstract word count, figure mark format, claim numbering continuity |
| Type B (Hybrid) | 42 | Script extraction + LLM judgment | Claim reference relationships, figure mark consistency |
| Type C (Semantic) | 23 | Pure LLM semantic review | Technical solution completeness, drawing description adequacy |

### Three Judgment Scenarios for Center Selection

| Scenario | Example | Judgment |
|----------|---------|----------|
| Selected center is on the **strict side** | Select Anhui → colored drawings | Strict standard applies 🔴 |
| Selected center is on the **lenient side** | Select Jilin → colored drawings | Lenient standard applies ✅, with notes on other centers |
| Selected center **does not mention** | Select Zhejiang → colored drawings | Marked as 💡 Suggestion |

---

## 📊 Review Report Structure

The generated DOCX review report contains 8 chapters:

```
1. Review Overview     → File info, patent type, rule statistics, issue counts by severity
2. Abstract Review     → F-1~F-16 automated scan + LLM review results
3. Claims Review       → F-17~F-46 automated scan + LLM review results
4. Specification Review → F-47~F-78 automated scan + LLM review results
5. Drawings Review     → F-79~F-101 automated scan + LLM review results
6. Items to Note       → Results for requirements not mandated by the selected center
7. Manual Confirmation → Items that cannot be automatically determined
8. Dispute Explanation  → Differences across centers and the selected center's stance
```

**Issue Severity Levels**:

- 🔴 **Must Fix** — Does not meet mandatory requirements; must be corrected before submission
- 🟡 **Suggested** — Non-mandatory but affects review pass rate
- ⚪ **Manual Check** — Cannot be determined by script/LLM; requires human review
- 💡 **FYI** — Not required by the selected center, but required by others

---

## 🏛️ Covered Protection Centers (19)

Jilin (吉林), Xuzhou (徐州), Zhejiang (浙江), Beijing (北京), Shanxi (山西), Gansu (甘肃), Changsha (长沙), Changchun (长春), Fujian (福建), Xi'an (西安), Inner Mongolia (内蒙古), Shaanxi (陕西), Anhui (安徽), Liaoning (辽宁), Hubei (湖北), Hefei (合肥), Changzhou (常州), Suzhou (苏州), Tianjin (天津)

> If the entered center is not in the list above, the "strictest mode" is automatically enabled to ensure the application won't be rejected by any center.

---

## 🙏 Acknowledgements

The review rules in this tool are derived from self-check tables publicly published by the 19 Intellectual Property Protection Centers listed above. We thank these centers for making their standards openly available.

---

## 📄 License

[MIT License](./LICENSE)
