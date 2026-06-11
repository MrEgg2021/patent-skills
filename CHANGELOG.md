# Changelog

本项目所有重要变更记录于此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.4.0] - 2026-06-12

### Added
- **新增 `patent-ocr-mineru`**：专利场景 MinerU OCR 解析 skill。支持精准 API / agent / local 三路径，专利章节识别、权要原文优先、附图标号核查、材料配方场景专项标注；作撰写/审核类 skill 的输入预处理。
- `global-dossier` 新增 `scripts/dossier_regression_check.py` 回归测试脚本。
- `patent-formality-review` 新增 `references/script-issue-review-prompt.md`（脚本命中项人工复核提示词）和 `tests/` 目录。

### Changed
- `patent-search`：`xhr_search.py` 与回归测试脚本修订。
- `global-dossier`：平台说明与下载脚本更新。
- `invention-point-extraction`：SKILL.md、参考文档、脚本优化。
- `claims-feature-decomposition`：推理参考文档与脚本优化。
- `disclosure-review`：审核清单与电学领域规则更新。
- `patent-formality-review`：`formality_scanner.py` 与 SKILL.md/README 修订。

## [1.3.0] - 2026-06-12

### Changed
- **`patent-formality-review` 全局重编号**：脚本、checklist、SKILL.md、README 统一从旧 F-数字编号迁移到字母前缀（C/S/D/AB/AF）。`formality_scanner.py` 137 处编号、31 个方法名、CENTER_DISPUTE_CONFIG 全部键一并更新，py_compile + grep 验证零残留。
- 摘要附图规则从 abstract-checklist.md 拆出，独立为 `references/abstract-figure-checklist.md`（AF-1 ~ AF-4）。
- abstract-checklist.md 重编为 AB-1 ~ AB-12（原 AB-14~16 → AB-10~12）。

## [1.2.0] - 2026-06-12

### Changed
- **`google-patent-search` 改名为 `patent-search`**（中性名，反映多源定位）。目录、frontmatter `name`、脚本内 `SKILL_NAME` 常量及跨仓引用同步更新。历史 changelog 条目保留原名以记录当时事实。

### Added
- **新增 Mode D：国家知识产权局公布公告站中文原生检索**。收编 `cnipa_epub_search.py` / `cnipa_epub_crawler.py` / `cnipa_epub_parse.py` 三脚本（Playwright 过 WAF，内存解析不落盘），补 `requirements-cnipa.txt`。适用于需免翻译中文检索、需官方源、或 Google 索引不足的场景；WAF 超时/0命中降级到 Mode A。
- SKILL.md 定位扩写为"多源专利检索：Google Patents（主力）+ 国知局公布站（中文原生补充）"，用法表与模式可用性总结同步加 Mode D。

## [1.0.1] - 2026-06-10

### Fixed
- **致命**：`google-patent-search/xhr_search.py` 因 `from __future__ import annotations` 前被插入了跨平台 reconfigure 块，导致 `SyntaxError`、Mode A（CN 专利首选检索路径）完全无法运行。修正块的位置（移到 `from __future__` 之后）。该 bug 在 v1.0.0 中存在。
- `search_regression_check.py` 新增 xhr_search 冒烟用例（import + 核心纯函数），防止同类 import/语法错误再次溜过测试。

### Changed
- `search.py` 的浏览器回退引导文案补充"无头强制"约束：优先 XHR（纯 HTTP 无浏览器），必须用浏览器时一律 headless=True 后台运行、禁止弹窗；并为该脚本补 stdout UTF-8 重配置。

## [1.0.0] - 2026-06-10

首个正式版本。包含 6 个公开专利技能（google-patent-search、global-dossier、invention-point-extraction、claims-feature-decomposition、disclosure-review、patent-formality-review），并完成一轮全面审计与跨平台修复。

### Fixed
- 修复 GBK 控制台编码崩溃：`dossier_download.py`、`xhr_search.py`、`docx_parser.py`、`formality_scanner.py` 在打印非 ASCII 字符（✓/emoji）时于 Windows GBK 控制台抛 `UnicodeEncodeError`，统一在脚本入口加 `sys.stdout.reconfigure(encoding='utf-8')` 保护。

### Changed
- 交付方式通用化：移除写死的微信 `send_message`+`MEDIA:` 交付指令，改为不绑定特定通道的"生成后交付/输出文件给用户"（`global-dossier`、`patent-formality-review`）。

[1.4.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.4.0
[1.3.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.3.0
[1.2.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.2.0
[1.0.1]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.0.0
