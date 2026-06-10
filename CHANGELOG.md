# Changelog

本项目所有重要变更记录于此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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

[1.0.1]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.0.0
