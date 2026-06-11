# 脚本命中项 LLM 复核提示词

## 使用场景

本提示词用于复核 `scripts/formality_scanner.py` 输出中 `review_policy != "script_final"` 的候选项。

脚本扫描负责高召回发现可疑问题；LLM 复核负责结合上下文判断候选项是否应进入最终审查结论。未经复核确认的候选项不得直接计入最终不合格数量。

## 输入

向 LLM 提供以下内容：

1. `formality_scanner.py` 输出的 JSON。
2. 目标保护中心 `target_center`。
3. 被审查文件的相关文本上下文。
4. 如有，官方客户端转档后的 PDF/XML 预览文件信息。

仅复核 `issues` 数组中 `review_policy` 不等于 `script_final` 的条目。

## 复核原则

1. 对 `review_policy="llm_required"` 的条目，必须判断脚本命中的原文是否真实构成形式问题。
2. 对 `review_policy="official_preview_required"` 的条目，如果没有官方客户端生成的 PDF/XML 预览，不得判定为最终不合格，只能维持“需转档后复核”。
3. 对 `review_policy="manual_required"` 的条目，除非上下文证据非常充分，否则保留人工确认结论。
4. 不得只凭关键词作出结论。必须引用 `matched_text` 和 `context` 说明判断理由。
5. 如果候选数字是数值范围、计量单位、步骤编号、年份、比例、温度、时间、次数、页码或普通数量，应判为误报。
6. 如果裸数字紧跟技术部件名称，且说明书/附图中存在对应标号，通常可判为确认问题。

## 输出 JSON 格式

必须输出 JSON 数组，每个对象对应一个被复核的候选项：

```json
[
  {
    "rule_id": "C-6",
    "matched_text": "101",
    "decision": "confirmed",
    "final_severity": "should_fix",
    "reason": "该数字紧跟技术部件名称“模块”，上下文不是数值、步骤或单位，符合疑似附图标记特征。",
    "evidence": "上下文：包括模块101和控制器"
  }
]
```

字段含义：

| 字段 | 取值 |
|---|---|
| `decision` | `confirmed` / `false_positive` / `manual_required` / `official_preview_required` |
| `final_severity` | `must_fix` / `should_fix` / `confirm` / `suggestion` / `excluded` |
| `reason` | 说明为何保留、剔除或转确认 |
| `evidence` | 引用候选项上下文或官方预览证据 |

## 判定映射

| `decision` | 报告处理 |
|---|---|
| `confirmed` | 进入对应章节的问题表 |
| `false_positive` | 不进入最终问题表，可进入“脚本误报剔除记录” |
| `manual_required` | 进入“人工确认事项” |
| `official_preview_required` | 进入“官方转档后复核事项” |

## 禁止事项

- 不得把 `false_positive` 候选项写入最终问题表。
- 不得在没有 PDF/XML 预览证据时，把 `official_preview_required` 条目改判为 `must_fix`。
- 不得把“约束”“等效”“等级”“等待”等词中的单字误判为不确定用语。
- 不得把“10℃”“20%”“步骤20”“2026年”等普通数字误判为附图标记。
