# patent-ocr-mineru

面向专利场景的 MinerU OCR 解析 skill。它把扫描版专利、授权公告 PDF、交底书、附图页、胶底/材料配方资料解析为 Markdown、结构化 JSON 和质量报告。

## 为什么不是通用 OCR

专利文件的价值不在于“识别出文字”，而在于保留可用于撰写、审查、检索、对比和答复的证据结构。本 skill 默认关注：

- 说明书摘要、权利要求书、技术领域、背景技术、发明内容、附图说明、具体实施方式；
- 权利要求编号、从属引用关系、“其特征在于”；
- 图号、附图说明、附图标记表；
- 胶底/材料场景下的配方、重量份、百分比、温度、硬度、磨耗、剥离强度、实验表格；
- OCR 质量风险，例如缺章、缺表、图号无标号、标题空格打散。

## 快速使用

精准 API 推荐用于正式资料：

```powershell
$env:MINERU_API_TOKEN = "<your-token>"
python patent-ocr-mineru/scripts/mineru_patent_ocr.py parse "D:\case\scan.pdf" `
  --service precision `
  --profile patent-application `
  --ocr-mode ocr `
  --model-version vlm `
  --output-dir "D:\case\ocr-output"
```

小文件快速预览可用 Agent API：

```powershell
python patent-ocr-mineru/scripts/mineru_patent_ocr.py parse "D:\case\short.pdf" `
  --service agent `
  --profile disclosure `
  --output-dir "D:\case\ocr-preview"
```

已有 MinerU 输出时只做专利后处理：

```powershell
python patent-ocr-mineru/scripts/mineru_patent_ocr.py postprocess "D:\case\mineru_raw\unzipped" `
  --profile material-scan `
  --output-dir "D:\case\ocr-post"
```

## 输出文件

- `mineru_raw/`：MinerU 原始结果；
- `patent_ocr_normalized.md`：轻度清洗全文；
- `patent_ocr_sections.md`：按专利章节切分；
- `patent_ocr_bundle.json`：结构化包；
- `patent_ocr_quality_report.json`：人工复核清单。

## 安全边界

token 只从 `MINERU_API_TOKEN`、`MINERU_TOKEN` 或 `MINERU_API_KEY` 读取。不要把 token 写入仓库、示例配置、命令参数或报告。涉密交底书优先使用本地 MinerU CLI 路径。
