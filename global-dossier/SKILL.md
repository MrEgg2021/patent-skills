---
name: global-dossier
description: USPTO Global Dossier 审查历史文件下载工具。用于下载/拉取/打包审查历史、file wrapper、OA 原文和同族审查文件；不用于撰写 OA 答复或意见陈述书。
metadata:
  triggers:
    - 审查历史
    - 审查文件
    - global dossier
    - dossier
    - 下载OA
    - 拉取OA
    - 下载审查意见
    - 同族审查
    - 专利族下载
    - file wrapper
    - 审查文件包
---

# Global Dossier 审查历史下载

## 定位

| | google-patent-search | **global-dossier** |
|---|---|---|
| 数据层 | 公开文本（PDF/DOCX/HTML） | **审查历史**（OA、答复、IDS、检索报告） |
| 数据源 | Google Patents | USPTO Global Dossier |
| 产出 | 专利全文 | 审查文件包 |

> **简单记**：想看专利写什么 → google-patent-search；想看审查员怎么审的 → global-dossier。
> **边界**：想下载审查历史文件 → global-dossier；想写 OA 答复/意见陈述/修改权利要求 → oa-response。

---

## 两种模式

| 模式 | 场景 | 输入 | 产出 |
|------|------|------|------|
| **A 单专利深挖** | "帮我把 CN116621800B 的审查文件下下来" | 公开号 / 申请号 | `{公开号}.zip`（按日期命名的 PDF） |
| **B 全族批量下载** | "把 US11922587 全族的审查文件都挖出来" | 公开号 / 申请号 | 6 个按公开号命名的 zip |

---

## 模式 A — 单专利深挖

### 调用方式
```bash
python3 scripts/dossier_download.py --number CN116621800B --mode single
python3 scripts/dossier_download.py --number US11922587 --mode single
python3 scripts/dossier_download.py --number 202310575536 --mode single  # 也支持申请号
```

### 工作流程
1. 解析输入（自动识别公开号 vs 申请号，CN/US/EP/WO/PCT 格式）
2. 在 Global Dossier 搜索 → 获取 `All Documents` 页面 URL
3. 枚举所有文档 → 逐一下载（内置 3s 间隔 + 429 退避）
4. 按 `{序号}_{日期}_{文档描述}.pdf` 命名
5. 打包为 `{公开号}.zip`

### 交付
- zip 包直接发送给用户
- 控制台输出下载进度和统计

---

## 模式 B — 全族批量下载

### 调用方式
```bash
python3 scripts/dossier_download.py --number US11922587 --mode family
python3 scripts/dossier_download.py --number CN116621800B --mode family
```

### 工作流程
1. 解析输入 → 搜索 → 进入专利族页面
2. 点击 `Expand All` → 提取所有同族成员信息（Office + Application Number + Publication Number）
3. 对每个同族成员：
   - 获取 `All Documents` URL
   - 枚举并逐一下载所有文档
   - 成员间间隔 20s 防限流
4. 每个成员按公开号建立文件夹 → 各自打包为 zip

### 进度输出示例
```
[1/6] US11922587B2: 54 docs → 15MB ✓
[2/6] US12322056B2: 56 docs → 23MB ✓
[3/6] US20250272931A1: 35 docs → 2.3MB ✓
[4/6] CN119156243A: 8 docs → 2.7MB ✓
[5/6] EP4522295A1: 27 docs → 9.8MB ✓
[6/6] WO2023220051A1: 13 docs → 2.7MB ✓
```

### 交付
- 每个同族成员一个 zip 包
- 控制台输出全族汇总统计

---

## 搜索策略

### 支持的输入格式

| 格式 | 示例 | 说明 |
|------|------|------|
| CN 公开号 | `CN116621800B` | 带前缀，带 AB 后缀 |
| CN 公开号（纯数字） | `116621800` | 不带前缀 |
| CN 申请号 | `202310575536` | 12 位数字 |
| US 公开号 | `US11922587B2` | 带前缀和类型码 |
| US 公开号（纯数字） | `11922587` | 不带前缀 |
| US 申请号 | `17740598` | 8 位数字 |
| EP 公开号 | `EP4522295A1` | 带前缀 |
| WO 公开号 | `WO2023220051A1` | 带前缀 |
| PCT 申请号 | `PCTUS2321525` | 带 PCT 前缀 |

### 自动识别逻辑
- 含 `CN` 前缀 → 中国专利，搜 Pre-grant Publication
- 含 `US` 前缀 → 美国专利，搜 Patent
- 含 `EP` 前缀 → 欧洲专利
- 含 `WO` 或 `PCT` 前缀 → PCT 专利
- 纯数字 13 位（20 开头）→ CN 申请号
- 纯数字 7-8 位 → US 专利号

---

## 技术踩坑记录

详见 `references/platform-notes.md`。

### 关键坑点
1. **Angular SPA 表单操作**：必须 `nativeInputValueSetter` + `input` + `change` + `blur` 四步事件链
2. **CloudFront 429 限流**：下载间隔 ≥3s，遇限流等待 60s 指数退避
3. **URL session ID**：Dossier URL 中的数字 ID 会变化，必须从族页面实时提取
4. **公开号提取**：从页面 `main` 元素文本中正则匹配，不可硬编码
5. **CNIPA 仅支持 2010-02-10 后申请**

---

## 与 google-patent-search 的协作

```
用户请求 → 判断要什么
  ├── 公开文本（PDF/全文） → google-patent-search Mode B
  ├── 审查历史（OA/答复/IDS） → global-dossier Mode A/B
  └── 两者都要 → 先用 google-patent-search 拿全文，再用 global-dossier 拿审查历史
```

---

## 文件结构

```
global-dossier/
├── SKILL.md                          # 本文件
├── scripts/
│   └── dossier_download.py           # 统一下载脚本（Mode A + B）
└── references/
    └── platform-notes.md             # 平台坑点和技术细节
```
