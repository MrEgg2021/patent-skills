# Global Dossier 平台技术笔记

## 站点架构

- 主站：https://globaldossier.uspto.gov
- 前端：Angular SPA，**无公开 REST API**
- CDN：CloudFront（`d1kazzu6rbodne.cloudfront.net`，API 直接访问 403）
- 文档下载：通过 Angular 事件触发浏览器原生 download

## 搜索表单

### 关键元素

```html
<select id="country">  <!-- 0=US, 1=CN, 2=EP, 3=KR, 4=JP, 5=WIPO, 6=CASE -->
<select id="type">     <!-- 0=Application, 1=Pre-grant Pub, 2=Patent -->
<input id="query">     <!-- 号码输入 -->
<button name="search"> <!-- 搜索按钮 -->
```

> 2026-06-12 实测：USPTO 前端已将原 `id="office"` 改为 `id="country"`。脚本应优先使用 `#country`，保留 `#office` 作为旧页面回退。

### CN 搜索格式
- 公开号：纯数字（如 `116621800`，不带 `CN` 前缀）
- 申请号：纯数字（如 `202310575536`）
- Office：`1`（CN）
- Type：`1`（Pre-grant Publication）

### US 搜索格式
- 公开号：纯数字（如 `11922587`，不带 `US` 前缀）
- 申请号：纯数字（如 `17740598`）
- Office：`0`（US）
- Type：`2`（Patent）

## Angular 表单操作（关键）

Global Dossier 页面使用 Angular，普通 JS `element.value = "xxx"` 设置的值 Angular 不会检测到，导致 `validQueryCheck` 报 `null`。

### 正确的事件链

```javascript
const setter = Object.getOwnPropertyDescriptor(
  HTMLInputElement.prototype, 'value'
).set;

// 1. 设置 select
const officeSelect = document.getElementById('country') || document.getElementById('office');
officeSelect.selectedIndex = TARGET_OFFICE_INDEX;
officeSelect.dispatchEvent(new Event('change', {bubbles: true}));

const typeSelect = document.getElementById('type');
typeSelect.selectedIndex = TARGET_INDEX;
typeSelect.dispatchEvent(new Event('change', {bubbles: true}));

// 2. 设置 input（必须用 native setter）
const queryInput = document.getElementById('query');
setter.call(queryInput, '11922587');
queryInput.dispatchEvent(new Event('input', {bubbles: true}));
queryInput.dispatchEvent(new Event('change', {bubbles: true}));
queryInput.dispatchEvent(new Event('blur'));
```

## 文档下载

### Enumerate（枚举文档列表）

```javascript
const rows = document.querySelectorAll('tr');
const docs = [];
for (const row of rows) {
  const cells = row.querySelectorAll('td');
  if (cells.length >= 4) {
    const link = cells[1]?.querySelector('a');
    const desc = link ? link.textContent.trim() : '';
    const date = cells[2]?.textContent.trim() || '';
    if (desc && /\d{2}\/\d{2}\/\d{4}/.test(date)) {
      docs.push({desc, date});
    }
  }
}
```

### Download（逐一下载）

```python
# Playwright — 必须原生 click 触发浏览器 download 事件
page.evaluate("""(desc) => {
    for (const row of document.querySelectorAll('tr')) {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 4) {
            const link = cells[1]?.querySelector('a');
            if (link && link.textContent.trim() === desc) {
                link.click();
                return true;
            }
        }
    }
    return false;
}""", doc_desc)

download = page.wait_for_event("download", timeout=20000)
download.save_as(filepath)
```

**注意**：Angular `href="javascript:void(0)"` 的链接，`dispatchEvent(new Event('click'))` 不触发下载，必须 Playwright 原生 `link.click()`。

## 限流策略

### CloudFront 429

USPTO Global Dossier 的 CloudFront 对请求频率敏感。

**退避策略**：
- 单文档下载间隔：**3 秒**
- 同族成员间间隔：**20 秒**
- 遇 429：等待 **60 秒** 后重试
- 重试仍 429：等待 **120 秒** 二次重试
- 三次失败：跳过该成员，继续下一个

### 响应体特征
```json
{"ERROR": "429 - CLOUDFRONT RATE LIMITED, TRY AGAIN LATER"}
```

## 公开号提取

从 Dossier 页面提取公开号的正则（按优先级）：

```python
import re

patterns = [
    # US: 11922587 B2
    (r'(\d{7,8})\s*B\d', 'US'),
    # US: US20230368472A1
    (r'US(\d{11})\s*A\d', 'US'),  
    # CN: CN119156243 A
    (r'CN\s*(\d{7,10})\s*[AB]', 'CN'),
    # EP: EP4522295 A1
    (r'EP\s*(\d{7,8})\s*A\d', 'EP'),
    # WO: WO2023220051 A1
    (r'WO\s*(\d{4}/\d{6})\s*A\d', 'WO'),
]

def parse_pub_number(page_text):
    for pattern, office in patterns:
        m = re.search(pattern, page_text)
        if m:
            num = m.group(1).replace('/', '')
            return f"{office}{num}"
    return None
```

## CNIPA 数据覆盖

- CNIPA：仅 **2010-02-10 之后** 的申请有数据（电子申请系统上线后）
- 2010 年前的 CN 专利在 Global Dossier 无审查历史

## 已测试案例

| 专利 | 类型 | 文档数 | 备注 |
|------|------|--------|------|
| CN116621800B | CN 授权 | 17 | 1 次 OA 直接授权 |
| US11922587B2 | US 授权 | 54 | 3 次 OA（NF→Final→Allowance） |
| US12322056B2 | US 授权（续案） | 56 | 持续审查 |
| US20250272931A1 | US 审查中（续案） | 35 | 最新 OA 2026-04 |
| CN119156243A | CN 申请 | 8 | 国际初步审查 |
| EP4522295A1 | EP 申请 | 27 | ISR + 书面意见 |
| WO2023220051A1 | PCT | 13 | 国际检索报告 |

## 浏览器配置

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    # ...
    browser.close()
```
