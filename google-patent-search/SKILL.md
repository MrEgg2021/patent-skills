---
name: google-patent-search
description: Google Patents 语义搜索与专利直取。模式A：输入技术描述自动拆解为检索式；模式B：按公开号直接下载PDF+Word；模式C：调用 invention-point-extraction 从已有专利搜相似。
metadata:
  triggers:
    - 谷歌专利
    - google patent
    - 专利搜索
    - 专利检索
    - 查专利
    - 搜专利
    - 下载专利
    - patent search
    - patent download
---

# Google Patents 语义搜索与直取

## 三种用法

| 用法 | 场景 | 输入 | 实际流程 | 交付物 |
|------|------|------|----------|--------|
| **A 语义搜索** | "帮我找关于XXX的专利" | 技术描述 / 关键词 | 拆概念 → 检索式 → 结果 | **xlsx 表格**（默认） |
| **B 直接抓取** | "把CN123456A下下来" | 公开号 | 抓取 → PDF + Word | PDF + Word |
| **C 从专利搜相似** | "这篇专利有什么相近的？" | PDF/Word文件 / 公开号 | 提取文本 → 送入模式A | xlsx 表格 |

> **交付原则**：搜索结果一律输出 xlsx 表格文件，用户可直接打开查看。表格包含公开号、标题、摘要、申请日、发明人、Google Patents 链接等标准字段。

---

## 模式 A — 语义搜索

把你说的技术描述自动拆成 Google Patents 能消化的检索式，不用你自己写布尔运算。

### 标准交付流程（从搜索到 xlsx）

```
搜索（XHR端点） → JSON结果 → convert_to_xlsx.py → 交付 xlsx
```

xlsx 默认列：`公开号`、`标题`、`摘要`、`申请日`、`发明人`、`申请人`、`Google Patents链接`。

> **XHR 搜索是首选路径**：`xhr_search.py` 直接请求 Google Patents 的 `/xhr/query` 端点，返回结构化 JSON，无需浏览器。`country:CN` 在此端点不被阻断，CN 专利正常出现。`convert_to_xlsx.py` 接受 JSON 输入（字段名：`publication_number` / `title` / `abstract` / `filing_date` / `inventor` / `applicant` / `url`），输出 .xlsx。

### 工作原理
1. 提取核心概念 → 中英文术语扩展（术语表 + LLM 翻译）
2. 匹配检索字段（TI/AB/CL/CPC/IPC）
3. 生成三套检索方案：精准 → 均衡 → 召回
4. **用 XHR 端点执行搜索**（`xhr_search.py`），获取结构化 JSON 结果
5. 如需 CN 专利，加 `country:CN` 过滤（XHR 端点支持）
6. 整理为 JSON → convert_to_xlsx.py → 交付 xlsx

### 用法

**技术描述搜（推荐）**：
```bash
python scripts/search.py --answers-file answers.json --json
```
`answers.json` 里填：
```json
{
  "search_input_mode": "technical_description",
  "technical_description_text": "一种基于多模态特征融合的异常检测方法，用于工业设备状态监测",
  "max_results": 20
}
```

**关键词直接搜**：
```bash
python scripts/search.py --terms "machine learning AND image processing" --classification G06N --max-results 20 --json
```

**结果解析导出（xlsx 是默认交付物）**：

方法一（推荐）：XHR 端点搜索，直接获取结构化 JSON
```bash
# XHR 搜索
python scripts/xhr_search.py '"path planning" AND robot' --proxy http://127.0.0.1:<port> -o results.json
# 搜索中国专利
python scripts/xhr_search.py '"path planning" AND robot country:CN' --proxy http://127.0.0.1:<port> --cn-only -o results_cn.json
# 转 xlsx
python scripts/convert_to_xlsx.py results.json results.xlsx
python scripts/save_cn_results.py results.json results_cn.json --xlsx results_cn.xlsx
```

方法二：有 browser 快照文本时
```bash
python scripts/parse_results.py snapshot.txt -o results.json
python scripts/convert_to_xlsx.py results.json results.xlsx
python scripts/save_cn_results.py results.json results_cn.json --xlsx results_cn.xlsx
```

方法三：手动整理结果（Google Patents 下载链接超时时）
直接构造 JSON 数组（字段：`title` / `publication_number` / `abstract` / `filing_date` / `inventor` / `applicant` / `url`），喂入 `convert_to_xlsx.py`。

### 高级筛选
- `--inventor` / `--assignee`：发明人 / 申请人
- `--classification`：CPC/IPC 分类号
- `--date-from` / `--date-to`：时间范围
- `--patent-office`：专利局（CN/US/WO/KR/EP/JP）
- `--language`：语言
- `--status`：法律状态
- `--type`：专利类型
- `--confirmed-assignee-alias` / `--confirmed-inventor-alias`：别名确认

---

## 模式 B — 直接抓取

给公开号，还你 PDF + Word。不分析不解读，拿完就走。

### 用法

**单个专利**：
```bash
# Step 1: intake（⚠️ proxy_url 必传，否则 SSL 错误）
python scripts/intake.py --non-interactive --answers '{
  "mode": "detail",
  "project_id": 1,
  "detail_input_mode": "single",
  "publication_number": "CN113487713A",
  "file_formats": "both",
  "proxy_url": "http://127.0.0.1:<port>"
}' > intake_out.json

# Step 2: file_ingest
python scripts/file_ingest.py --non-interactive --answers-file intake_out.json > ingest_out.json

# Step 3: export（output-dir 填父目录，脚本自动创建 {公开号}/ 子目录）
python scripts/export_artifacts.py --context-file ingest_out.json --output-dir ./output/
```

**批量专利**：`detail_input_mode` 改为 `batch`，`publication_number` 改为 `patent_list_file`。

> ⚠️ **批量模式可靠性低于单专利下载**。batch 模式可能报 `publication_numbers_required` 错误（intake.py 未正确解析 patent_list_file）。**实践建议：用循环逐个调 single 模式，比 batch 更稳。**

**从搜索结果直取**：`detail_input_mode` 改为 `results_json`，传入 `results_json_file`。

### 输出内容
- `{公开号}.pdf` — 专利原文（如有）
- `{公开号}.docx` — 整理后的 Word（摘要 + 权利要求 + 说明书）
- 不输出中间文件（raw_html、parsed.json 等仅供内部使用）

---

## 从已有专利搜相似（用法 C）

用户已有一篇专利，想找相似的。先调 `invention-point-extraction` skill 提取发明点，剥离套话，再送入模式 A 检索。

调用方式：从 [invention-point-extraction](https://github.com/MrEgg2021/invention-point-extraction) 公开仓库获取 SKILL.md，按其流程处理目标专利文本，将提取的发明点作为 Mode A 的检索输入。

### 流程

```
专利文本 → [invention-point-extraction skill] → 技术问题+技术方案 → Mode A 检索
```

### 三条输入路径

**路径 1：用户传了 PDF / Word 文件**
1. 调 `invention-point-extraction` skill 解析专利（skill 内部自动处理 PDF/Word 提取 + 发明点提取）
2. 取输出的 xlsx 中 `技术问题` + `技术方案` 列，拼接为 `technical_description_text`
3. 走模式 A 搜索

**路径 2：用户只给了公开号**
1. 先走模式 B，从 `parsed.json` 取 `sections.description`（说明书全文）
2. 将说明书文本送入 `invention-point-extraction` skill 提取发明点
3. 取 xlsx 中发明点文本灌入 `technical_description_text`
4. 走模式 A 搜索相似专利

**路径 3：用户要求"下下来再搜"**
同路径 2，拿到 PDF+Word 后，顺手提取发明点搜相似，一并交付。

---

## 环境

- Python ≥ 3.11
- 依赖：`pyyaml`、`beautifulsoup4`（export_artifacts.py 解析 Google Patents HTML 需要）
- 安装：`uv pip install pyyaml beautifulsoup4`（或 `pip install pyyaml beautifulsoup4`）
- 需要网络访问 Google Patents（或国内镜像 `https://patents.glgoo.top`）

## 代理配置（🔴 关键）

**Mode B 下载链路（intake → file_ingest → export_artifacts）必须通过 `proxy_url` 参数传代理，HTTP_PROXY 环境变量对 export_artifacts.py 无效。**

```json
// intake answers 中必须包含 proxy_url
{
  "mode": "detail",
  "detail_input_mode": "single",
  "publication_number": "US11804056B2",
  "file_formats": "both",
  "proxy_url": "http://127.0.0.1:<port>"
}
```

> **请将 `<port>` 替换为你的代理端口**（如 Clash 默认为 7890，v2rayN 默认为 10808，不同代理工具端口不同）。

**不传 proxy_url 的后果**：file_ingest.py 会尝试直连 Google Patents，在国内网络环境下直接超时或 SSL 错误，下载失败但不会报代理相关错误（报 `SSLEOFError` 或 `Max retries exceeded`）。

## 搜索行为注意事项

### XHR 搜索（推荐，模式 A 首选路径）

Google Patents 前端搜索时调用的内部 `xhr/query` 端点可以直接用 HTTP 请求访问，**不需要浏览器**：

```bash
# 单查询搜索
python scripts/xhr_search.py '"path planning" AND robot' --proxy http://127.0.0.1:<port>

# 搜索中国专利（country:CN 在 XHR 端点不被阻断！）
python scripts/xhr_search.py '"path planning" AND robot country:CN' --proxy http://127.0.0.1:<port> --cn-only

# 多策略搜索
python scripts/xhr_search.py --query-file payload.json --proxy http://127.0.0.1:<port>
```

**XHR 端点的核心优势**：
- ✅ **country:CN 可用** — 不像搜索页那样被阻断（已实测验证）
- ✅ **CN 专利直接出现** — Google 已将中国专利机器翻译成英文并建立索引
- ✅ **纯 HTTP 请求** — 无需 Playwright/浏览器，速度快（~2.8秒/次）
- ✅ **结构化 JSON** — 不需要解析 HTML
- ✅ **中文关键词无需使用** — 用英文搜索即可匹配到已翻译索引的 CN 专利

**XHR 端点的限制**：
- ⚠️ **频率限制** — 连续 ~5 次请求后返回 HTTP 503，需间隔 ≥30 秒
- ⚠️ **非官方接口** — Google 可能随时改动，但已被多个开源项目验证可用
- ⚠️ **单页约 10 条结果** — 需翻页获取更多

### Playwright 浏览器搜索（回退路径）

当 XHR 端点 503 时，可用 Playwright headless 模式作为回退：
```python
browser = await playwright.chromium.launch(headless=True)
```

### 中文关键词处理

- **不要用中文关键词搜索** — Google Patents 会将中文切成单字（"版面分析"→"版"+"面"+"分"+"析"）
- **用英文关键词搜索** — Google 已将非英文专利机器翻译成英文并建立索引，英文搜索即可命中 CN 专利
- **中文术语自动翻译** — 执行搜索前，将中文术语翻译为英文：
  1. 术语表覆盖的词（83条）→ 自动翻译（`extract_glossary_expansions()`）
  2. 术语表未覆盖的词 → **LLM 翻译为英文后再搜索**
  3. 翻译提示词模板：`将以下中文技术术语翻译为英文，用于专利检索：{中文术语}。只输出英文翻译，多个同义词用逗号分隔。`

### 搜索前中文术语翻译示例

用户输入：`一种基于多模态特征融合的异常检测方法`

1. 术语表命中："多模态" → `multimodal`、"异常检测" → `anomaly detection`
2. 术语表未命中："特征融合" → LLM翻译 → `feature fusion, feature concatenation`
3. 最终英文检索式：`multimodal AND "feature fusion" AND "anomaly detection"`

## 代理配置（国内环境 🔴 必读）

用户环境通过代理访问 Google。

### Mode B 下载（最关键）

**`proxy_url` 参数必须显式传入 intake 命令**。脚本使用 `requests` 库，不会自动读取 `HTTP_PROXY` 环境变量。如果不传，下载全部失败（SSL EOF 错误）。

```bash
# ✅ 正确：intake 时必须传 proxy_url
python scripts/intake.py --non-interactive --answers '{
  ...,
  "proxy_url": "http://127.0.0.1:<port>"
}'
```

### Playwright 浏览器搜索

```python
context = await browser.new_context(
    proxy={'server': 'http://127.0.0.1:<port>'}
)
```

### XHR 搜索（推荐优先）

```bash
python scripts/xhr_search.py "query" --proxy http://127.0.0.1:<port>
```

### curl 命令行

```bash
HTTP_PROXY="http://127.0.0.1:<port>" HTTPS_PROXY="http://127.0.0.1:<port>" curl ...
```

### 搜索稳定性

**XHR 端点（优先）**：
1. ✅ **country:CN 可用** — 不触发阻断（与搜索页行为不同）
2. ✅ **CN 专利直接出现** — publication_number 以 CN 开头的专利正常返回
3. ⚠️ **频率限制** — 连续 ~5 次请求后 HTTP 503，需间隔 ≥30 秒
4. ✅ **响应格式** — 结构化 JSON，无需解析 HTML

**Playwright 搜索页（回退）**：
1. **频率限制**：连续多次请求后会被限流（ERR_CONNECTION_CLOSED）。建议每次搜索间隔 ≥15 秒。
2. **CN 专利不出现**：英文关键词搜索返回 US/WO/EP/JP 专利，CN 专利号不在搜索结果链接中。
3. **中文分词问题**：中文关键词会被切成单字。
4. **`country:CN` 过滤触发阻断**：在搜索页 query 中使用 `country:CN` 语法会导致连接立即被关闭。

**推荐的实际工作流**：用 XHR 端点 + 英文关键词搜索 → 结果中包含 CN 专利 → 用 Mode B（带 `proxy_url`）批量下载 PDF。

---

## 模式可用性总结

| 模式 | 可用性 | 说明 |
|------|--------|------|
| **A 语义搜索** | ✅ 可用（XHR） | XHR 端点直接搜索，country:CN 可用、CN 专利正常出现。Playwright headless 作为 503 回退。 |
| **B 直接抓取** | ✅ 可靠 | 详情页是服务端渲染的。**必须传 `proxy_url` 参数**，否则 SSL 错误。 |
| **C 从专利搜相似** | ✅ 可用 | 提取发明点后走 XHR 搜索，country:CN 可用，CN 专利正常出现。 |

### 实践建议

- **获取 CN 专利**：XHR 端点 + 英文关键词 + `country:CN` → Mode B 批量下载
- **获取 US/WO 专利**：XHR 端点 + 英文关键词（注意频率限制 ≥30秒间隔）
- **永远不要**：① 不传 `proxy_url` 就调 intake（SSL 错误）；② 用中文关键词搜索（会被切成单字）；③ 连续快速搜索（触发 503）

---

## 工作目录

- 产出物统一落到当前工作目录下的 `output/` 子目录，不污染 skill 目录
