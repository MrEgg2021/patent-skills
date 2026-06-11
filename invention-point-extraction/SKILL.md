---
name: invention-point-extraction
description: "Use when a user needs to extract a small set of readable core invention points from one or more patent specifications, especially for R&D readers who need to quickly understand the technical problem and solution; also used as patent-search Mode C preprocessing."
metadata:
  triggers:
    - 发明点
    - 发明点提取
    - 发明点解析
    - 专利核心技术
    - 专利技术方案提取
    - 从专利提取发明点
    - 解析专利发明点
    - patent invention points
---

# 专利发明点解析

## 定位

从专利说明书中提取少量、可读、适合研发人员快速理解的核心发明点，输出结构化 xlsx。

核心目标不是把全文压缩成一句话，也不是穷举所有实施细节，而是帮助研发人员快速看懂：
- 该专利主要解决什么技术问题；
- 用什么关键技术方案解决；
- 方案中哪些结构、步骤、算法、参数或协同关系值得关注。

## 适用边界

使用本 skill：
- 用户给出专利 PDF、Word、txt、md 或说明书文本，要求提取发明点；
- `patent-search` Mode C 需要把已有专利转成检索用技术描述；
- 研发、技术调研、立项预研需要快速理解专利技术内核。

不要使用本 skill：
- 要拆权利要求技术特征时，使用 `claims-feature-decomposition`；
- 要做交底书质量审核时，使用 `disclosure-review`；
- 要判断新颖性、创造性或授权前景时，使用对应对比分析/OA skill。

## 核心原则

1. **只吃说明书**：输入范围限定为说明书正文，剔除摘要和权利要求书。完整专利文本先按 `references/description_range_detection.md` 截取。
2. **少量核心发明点**：通常输出 2-5 个；确为单一发明构思时可输出 1 个；复杂组合方案可超过 5 个，但必须合并同质细节，避免流水账。
3. **研发可读**：每个技术问题和技术方案都要写到研发人员能理解关键机制的程度。不要过度浓缩成口号，也不要堆砌无关原文。
4. **严格来源**：所有技术内容必须来自说明书原文。数值、参数、效果、材料、模型结构等，原文没有就不得补。
5. **问题-方案对应**：技术问题数组与技术方案数组必须按同一序号一一对应。

## 输入处理

| 格式 | 处理方式 |
|------|----------|
| `.md` / `.txt` | 直接读取文本，判断是否已是说明书正文 |
| `.pdf` | 调用 PDF 提取能力，随后按说明书范围规则截取 |
| `.docx` | 调用 Word 提取能力，随后按说明书范围规则截取 |
| 目录/多文件 | 逐篇处理，合并到同一个 xlsx |

说明书范围识别规则见 `references/description_range_detection.md`。截取失败或章节异常时，必须在输出前说明所采用的截取假设。

## 工作流程

1. 提取文本，并剔除摘要、权利要求书。
2. 加载 `references/invention_point_extraction_prompt.md`。
3. 对每篇说明书输出 JSON 对象：

```json
{
  "专利公开号": "CN...",
  "专利标题": "...",
  "技术问题": ["问题1", "问题2"],
  "技术方案": ["方案1", "方案2"]
}
```

4. 保存 JSON。
5. 运行转换脚本生成 xlsx：

```bash
python scripts/json_to_xlsx.py invention_points.json 发明点解析.xlsx
```

## xlsx 输出

`.xlsx` 文件一行一个专利，四列：

| 专利公开号 | 专利标题 | 技术问题 | 技术方案 |
|-----------|---------|---------|---------|

格式规范见 `references/xlsx_format_spec.md`。

脚本支持：
- LLM 输出的 ```json code block；
- 单对象、对象数组、`{"results":[...]}`、`{"data":[...]}`；
- 新字段：`专利公开号`、`专利标题`、`技术问题`、`技术方案`；
- 旧字段：`文件名称`、`发明点`，自动映射为表格字段。

## 作为 patent-search 预处理

被 Mode C 调用时：

```
专利文本 → invention-point-extraction → xlsx 中的技术问题+技术方案
  → 拼接为 technical_description_text → patent-search Mode A
```

用于检索时，优先拼接每个发明点的“技术问题 + 技术方案”，不要把说明书全文直接塞入检索。

## 环境

- Python >= 3.9
- 依赖：`pandas`、`openpyxl`
- 安装：`pip install pandas openpyxl`
- 输出默认目录：当前工作目录；如调用方需要固定位置，应显式传入输出文件路径。
