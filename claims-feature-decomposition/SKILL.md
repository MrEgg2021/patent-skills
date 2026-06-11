---
name: claims-feature-decomposition
description: "Use when a user needs to decompose patent claims into technical features, preserve claim wording as the evidence base, and match each feature to specification support for comparison, OA response, infringement, or claim chart preparation."
metadata:
  triggers:
    - 权利要求拆解
    - 特征拆解
    - 技术特征分解
    - 拆权利要求
    - claims decomposition
    - claim feature
    - 拆特征
    - 权利要求分析
---

# 权利要求技术特征拆解

## 定位

将专利权利要求按语义单位拆解为独立技术特征，并从说明书中匹配每个特征的工作原理、实施例、参数、效果和来源段落，最终输出三列 xlsx。

本 skill 的核心价值是形成可复用的特征表，供专利对比分析、OA 答复、侵权比对或 claim chart 使用。

## 适用边界

使用本 skill：
- 用户只有一篇专利，要求拆解权利要求；
- `patent-comparison-report` 或 `oa-response` 需要逐特征输入；
- 需要把权利要求文本转为表格化特征清单。

不要使用本 skill：
- 只想快速理解专利发明点时，使用 `invention-point-extraction`；
- 要审核发明人交底材料是否完整时，使用 `disclosure-review`；
- 要判断某对比文件是否公开某特征时，使用对比分析/OA skill。

## 核心原则

1. **权利要求原文优先**：技术特征列以权利要求原文为主体，不改写、不缩写、不擅自概括。
2. **允许极少量语义标注**：为保证单个特征可独立理解，可在原文后添加极短标注，例如 `（标注：其中“其”指代A部件）`。标注必须明确为 agent 添加，不得替代原文。
3. **从属权利要求只拆新增限定**：不要重复独立权利要求已有特征；权利要求序号中保留直接引用关系。
4. **说明书匹配必须有来源**：说明书描述必须标注段落号、章节或图号；原文没有的内容写“说明书中未明确描述”。
5. **技术效果不从背景技术硬推**：背景技术可用于理解问题，但“技术效果/优势”应优先来自发明内容、具体实施方式或效果描述。

## 输入处理

从专利文件中提取：
1. 权利要求书全文；
2. 说明书正文，通常为“技术领域”至“具体实施方式”，可含附图说明，不含摘要。

支持 `.pdf`、`.docx`、`.md`、`.txt`。如果文本章节不清，先说明截取假设，再执行拆解。

## 工作流程

```
专利文件 → 提取权利要求+说明书 → 加载提示词 → JSON → json_to_xlsx.py → xlsx
```

加载提示词：

`references/claims_feature_decomposition_reasoning.md`

向模型提供：
1. 权利要求书全文；
2. 说明书正文；
3. 上述提示词全文。

模型输出 JSON 数组：

```json
[
  {
    "权利要求序号": "1",
    "技术特征 (源自权利要求书原文，按语义单位独立分解)": "原文（标注：必要时极少量指代说明）",
    "说明书描述 (主题归类式整合，严格源自说明书原文，并注明来源)": "描述"
  }
]
```

转换 xlsx：

```bash
python scripts/json_to_xlsx.py output.json 权利要求特征拆解.xlsx
```

## 输出格式

| 列 | 内容 |
|----|------|
| 权利要求序号 | 含引用关系，如 `2 (引1)` |
| 技术特征 | 权利要求原文为主体；必要时追加极短语义标注 |
| 说明书描述 | 主题归类整合，包含工作原理、实施例、参数、效果等，并附来源 |

## 质量自检

输出前逐项检查：
- 是否覆盖所有权利要求；
- 每条从属权利要求是否只拆新增限定；
- 技术特征列是否仍以权利要求原文为主体；
- agent 添加的语义标注是否极少、明确、可删除；
- 每条说明书描述是否有来源；
- 未找到支持的特征是否明确写“说明书中未明确描述”。

## 环境

- Python >= 3.9
- 依赖：`pandas`、`openpyxl`
- 安装：`pip install pandas openpyxl`
