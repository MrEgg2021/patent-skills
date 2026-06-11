---
name: patent-ocr-mineru
description: >
  面向专利场景的 MinerU OCR 与文档解析技能。用于把扫描版专利、授权公告文本、交底书、
  附图页、胶底/材料配方资料等文件解析为 Markdown、结构化 JSON 和质量报告，并对权利要求、
  说明书章节、附图标记、材料配方与实验数据做专利后处理。触发词：OCR解析、扫描专利解析、
  MinerU、PDF转专利文本、交底书OCR、附图OCR、胶底材料解析、专利文件结构化。
metadata:
  triggers:
    - OCR解析
    - 扫描专利解析
    - MinerU
    - PDF转专利文本
    - 专利OCR
    - 交底书OCR
    - 附图OCR
    - 胶底材料解析
    - 专利文件结构化
---

# 专利 OCR 与 MinerU 解析

## 定位

本 skill 不是通用 OCR。它的目标是把专利相关文件解析成后续技能可复用的证据材料，尤其服务于：

- 扫描版中国专利申请文件、授权公告 PDF、全球案卷下载文件；
- 发明人交底书、实验记录、配方表、胶底/材料方案；
- 说明书附图、摘要附图、附图标记页；
- 后续 `claims-feature-decomposition`、`disclosure-review`、`patent-formality-review`、撰写类 skill 的输入预处理。

## 强制原则

1. **密钥不落盘**：MinerU 精准 API token 只从环境变量读取：`MINERU_API_TOKEN`、`MINERU_TOKEN` 或 `MINERU_API_KEY`。不要写入仓库、示例配置、日志或最终报告。
2. **先保留原始证据**：保留 MinerU 原始 `full.md`、`content_list.json`、zip 包或本地 CLI 输出，再做清洗。不得只交付二次整理文本。
3. **专利章节优先**：解析后必须识别并标注说明书摘要、权利要求书、技术领域、背景技术、发明内容、附图说明、具体实施方式、说明书附图等专利章节。
4. **权利要求原文优先**：提取权利要求时不得改写技术特征，只能做 OCR 空格/标题级别的清洗。
5. **附图与标号独立核查**：出现“图1/图2”等图号时，必须检查是否识别到附图标记表或标号说明。
6. **材料场景专门核查**：胶底、橡胶、树脂、硫化、重量份、wt%、硬度、磨耗、剥离等线索必须被单独标注，防止配方表、实验表或单位丢失。
7. **不把 OCR 结果当最终事实**：质量报告中出现缺章、缺表、缺标号、异常空格时，必须提示人工复核原 PDF/图片。

## 选择解析路径

优先级按文件目的决定：

| 场景 | 推荐路径 | 原因 |
|---|---|---|
| 正式专利文件、需要 JSON/zip 证据 | `precision` | MinerU 精准 API 返回 zip，含 Markdown 与结构化 JSON |
| 小文件、临时快速看内容 | `agent` | 无需 token，但有大小/页数限制且只返回 Markdown |
| 本地可装 MinerU、涉密资料不宜上传 | `local` | 通过本地 `mineru` CLI 解析，避免外传 |
| 附图页、复杂扫描页、材料表页 | `precision --model-version vlm --ocr-mode ocr` | 对复杂版面和图文混排更稳 |

## 标准命令

### 精准 API：推荐正式路径

PowerShell 示例：

```powershell
$env:MINERU_API_TOKEN = "<your-token>"
python patent-ocr-mineru/scripts/mineru_patent_ocr.py parse "D:\case\scan.pdf" `
  --service precision `
  --profile patent-application `
  --ocr-mode ocr `
  --model-version vlm `
  --extra-formats docx,html `
  --output-dir "D:\case\ocr-output"
```

不要把 token 写进命令参数。只用环境变量。

### Agent 轻量 API：小文件快速预览

```powershell
python patent-ocr-mineru/scripts/mineru_patent_ocr.py parse "D:\case\short.pdf" `
  --service agent `
  --profile disclosure `
  --ocr-mode auto `
  --output-dir "D:\case\ocr-preview"
```

### 本地 MinerU CLI：涉密或批量资料

```powershell
python patent-ocr-mineru/scripts/mineru_patent_ocr.py parse "D:\case\input.pdf" `
  --service local `
  --profile material-scan `
  --ocr-mode ocr `
  --output-dir "D:\case\ocr-local"
```

### 已有 MinerU 输出的后处理

```powershell
python patent-ocr-mineru/scripts/mineru_patent_ocr.py postprocess "D:\case\mineru_raw\unzipped" `
  --profile official-patent `
  --output-dir "D:\case\ocr-post"
```

## 交付物

脚本统一输出：

- `mineru_raw/`：MinerU 原始结果，含 zip、`full.md` 或 JSON；
- `patent_ocr_normalized.md`：仅做轻度 OCR 清洗后的全文；
- `patent_ocr_sections.md`：按专利章节切分后的 Markdown；
- `patent_ocr_bundle.json`：结构化包，含章节、权利要求、图号、附图标记、材料线索；
- `patent_ocr_quality_report.json`：缺章、缺表、缺标号、OCR 异常等复核项。

## 专利后处理重点

1. **申请文件五件套识别**：说明书摘要、权利要求书、说明书、说明书附图、摘要附图要分开。不能把摘要附图和说明书附图混为正文。
2. **权利要求编号稳定性**：重点检查 `1.`、`1、`、`1．` 是否被 OCR 打散；从属权利要求引用关系必须保留。
3. **“其特征在于”检测**：中国撰写格式下，独立权利要求通常应出现该短语；未出现时不是直接判错，而是列入人工确认。
4. **图号与标号一致性**：正文出现图号时，检查附图说明和标号表是否存在；标号行一般形如 `10-支架`、`10、支架`、`10：支架`。
5. **材料/胶底场景**：配方表、质量份、百分比、粒径、温度、硬度、磨耗、剥离强度等是高价值数据，OCR 后必须单独标注并核查单位。
6. **交底书场景**：优先抽取技术问题、技术方案、有益效果、应用场景、替代方案、实验数据；不要强行套完整申请文件结构。
7. **页眉页脚处理**：MinerU 可能把页眉页脚放入 discarded blocks。正式撰写前必须确认页码、页眉、申请号等是否混入正文证据。

## 质量自检

输出前检查：

- 是否存在 `mineru_raw/` 原始文件；
- `patent_ocr_bundle.json` 是否包含 `sections`、`claims`、`figures`、`quality_report`；
- 质量报告风险等级是否为 `low/medium/high`，且 `warnings` 不为空时已告知用户；
- 材料资料是否标出配方/参数/测试数据线索；
- 未在任何文件中写入 MinerU token。

## 参考资料

- MinerU API 文档：`https://mineru.net/apiManage/docs`
- MinerU CLI 文档：`https://opendatalab.github.io/MinerU/usage/cli_tools/`
- MinerU 输出文件格式：`https://opendatalab.github.io/MinerU/reference/output_files/`

更多接口差异与专利 schema 见 `references/mineru-integration-notes.md` 和 `references/patent-ocr-schema.md`。
