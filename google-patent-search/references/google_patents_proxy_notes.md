# Google Patents 搜索行为实测笔记

> 2026-05-30 会话中通过 playwright + Clash 代理实测总结。
> 2026-06-08 更新：新增 XHR/query 端点实测结果。

## 工作链路

**Mode A 搜索 — XHR 端点（推荐，2026-06-08 验证）**：
1. `search.py` 生成检索策略和查询
2. `xhr_search.py` 用 urllib/requests 直接请求 `/xhr/query` 端点
3. 解析 JSON 响应，提取专利列表
4. **优势**：country:CN 可用、CN 专利正常出现、不需要浏览器

**Mode A 搜索 — Playwright（回退）**：
1. `search.py` 生成检索策略和 URL
2. 使用 playwright 浏览器 + 代理打开搜索结果页
3. 从 HTML/文本中提取专利号

**Mode B 下载（稳定，已验证）**：
1. intake.py → file_ingest.py → export_artifacts.py
2. **必须传 `proxy_url`**，否则 file_ingest 直连超时

## XHR/Query 端点实测（2026-06-08）

### 端点格式
```
GET https://patents.google.com/xhr/query?url=q%3D{URL编码的查询字符串}
```

### 已验证可用
- ✅ 纯英文关键词搜索（HTTP 200，返回完整 JSON，~2.8秒）
- ✅ `country:CN` 过滤（HTTP 200，3274 条结果，**不被阻断**）
- ✅ CN 专利直接出现在结果中（CN104503464B、CN107390684B、CN111220153B 等）
- ✅ 布尔运算符（AND/OR）和字段限定符（TI=/AB=/CL=）可用
- ✅ 不需要浏览器、不需要 JS 渲染

### JSON 响应结构
```json
{
  "results": {
    "total_num_results": 3274,
    "total_num_pages": 99,
    "cluster": [{
      "result": [{
        "id": "patent/CN107390684B/en",
        "patent": {
          "title": "A multi-robot collaborative optimal path planning method…",
          "snippet": "…",
          "publication_number": "CN107390684B",
          "priority_date": "2017-07-14",
          "filing_date": "2017-07-14",
          "inventor": "陈立定",
          "assignee": "华南理工大学",
          "pdf": "67/e4/76/a8fe97d5e4d6fe/CN107390684B.pdf",
          "language": "en",
          "family_metadata": {"aggregated": {"country_status": […]}}
        }
      }]
    }]
  }
}
```

### 频率限制
- 连续 ~5 次请求后返回 HTTP 503 "automated queries"
- 60 秒冷却后可能仍未恢复，需要更长冷却时间
- 建议：每次搜索间隔 ≥30 秒

### 关键发现
- **Google Patents 已将非英文专利机器翻译成英文并建立索引**（来源：support.google.com/faqs/answer/7049585）
- 用英文关键词搜索即可匹配到 CN 专利
- `country:CN` 在 XHR 端点不触发阻断（搜索页会被阻断，但 XHR 不会）

## Playwright 代理配置

```python
context = await browser.new_context(
    proxy={'server': 'http://127.0.0.1:7890'},
    viewport={'width': 1920, 'height': 1080}
)
```

## 已知问题（Playwright 搜索页，XHR 已解决）

1. ~~**中文分词打散**~~ → XHR：用英文搜索，不存在此问题
2. ~~**`country:CN` 阻断**~~ → XHR：country:CN 不被阻断
3. ~~**CN 专利号隐藏**~~ → XHR：CN 专利直接出现，publication_number 正常
4. **连续搜索限流**：XHR 和 Playwright 均受此限制（503/ERR_CONNECTION_CLOSED）

## 成功案例

2026-05-30 会话中使用 6 组英文关键词（document layout analysis 等）成功返回 280-300KB HTML，从中提取了 US11804056B2、CN117436412A 等 5 篇相关专利并通过 Mode B proxy_url 下载成功。

2026-06-08 实测 XHR 端点：
- `"path planning" AND robot` → 124922 条结果，含 JP/TW/ES/CN/KR/US 专利
- `"path planning" AND robot country:CN` → 3274 条结果，CN 专利正常出现
