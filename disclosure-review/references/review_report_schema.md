# 审核报告 JSON 结构

`render_review_docx.py` 的 `--data` 输入结构。所有字段可选，缺失即优雅跳过。

```json
{
  "invention_title": "发明名称（用于标题和文件名）",
  "domain": "识别领域，如：电学 / 软件 / AI",
  "overall_assessment": "整体评估，3-5 句",

  "review_records": [
    {
      "rule": "Rule D.1.1",
      "name": "必要特征完整性",
      "level": "🔴",
      "status": "一句话描述交底书相关现状",
      "problem": "具体问题；通过项留空",
      "impact": "为什么影响撰写/理解/实施"
    }
  ],

  "part_a": [
    {
      "title": "关于某宏观主题",
      "description": "问题描述",
      "level": "🔴",
      "impact": "为什么影响撰写",
      "options": ["A：……", "B：……", "C：其他情况，请详细说明：______"]
    }
  ],

  "part_b": [
    {
      "title": "关于某具体点",
      "origin_ref": "原文定位：段落号/页码/原文引用",
      "description": "详细问题描述",
      "level": "🔵",
      "impact": "为什么影响撰写",
      "options": ["A：……", "B：……", "C：其他情况，请详细说明：______"]
    }
  ]
}
```

## 字段说明

| 字段 | 用途 |
|:--|:--|
| `level` | 级别。接受 `🔴`/`必须补充`、`🔵`/`建议补充`、`✅`/`通过`，自动上色。未知值原样黑字显示 |
| `review_records` | 第二段表格，逐条审查记录（含通过项 ✅） |
| `part_a` | 第三段宏观问题。`origin_ref` 可省略（宏观项不强制引用原文） |
| `part_b` | 第三段微观问题。`origin_ref` 必填，定位到具体原文 |

## 用法

```bash
python scripts/render_review_docx.py --data report.json --output "{发明名称}_交底书审核报告.docx"
```

`--data` 接受 JSON 文件路径或 JSON 字符串。
