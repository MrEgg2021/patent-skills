# Changelog

本项目所有重要变更记录于此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-06-10

首个正式版本。包含 6 个公开专利技能（google-patent-search、global-dossier、invention-point-extraction、claims-feature-decomposition、disclosure-review、patent-formality-review），并完成一轮全面审计与跨平台修复。

### Fixed
- 修复 GBK 控制台编码崩溃：`dossier_download.py`、`xhr_search.py`、`docx_parser.py`、`formality_scanner.py` 在打印非 ASCII 字符（✓/emoji）时于 Windows GBK 控制台抛 `UnicodeEncodeError`，统一在脚本入口加 `sys.stdout.reconfigure(encoding='utf-8')` 保护。

### Changed
- 交付方式通用化：移除写死的微信 `send_message`+`MEDIA:` 交付指令，改为不绑定特定通道的"生成后交付/输出文件给用户"（`global-dossier`、`patent-formality-review`）。

[1.0.0]: https://github.com/MrEgg2021/patent-skills/releases/tag/v1.0.0
