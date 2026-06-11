# MinerU 接入笔记

更新时间：2026-06-12

## 资料来源

- MinerU API 文档：https://mineru.net/apiManage/docs
- MinerU CLI 文档：https://opendatalab.github.io/MinerU/usage/cli_tools/
- MinerU 输出格式：https://opendatalab.github.io/MinerU/reference/output_files/

## 三条接入路径

### 1. 精准解析 API

适用正式专利解析、长文件、需要 JSON/zip 证据链的场景。

关键点：

- token 必须放在 `Authorization: Bearer <token>`；
- URL 批量接口：`POST https://mineru.net/api/v4/extract/task/batch`；
- 本地文件上传接口：`POST https://mineru.net/api/v4/file-urls/batch`，先拿签名上传 URL，再 `PUT` 上传；
- 批量结果查询：`GET https://mineru.net/api/v4/extract-results/batch/{batch_id}`；
- 完成后返回 `full_zip_url`；
- zip 内通常包含 `full.md`、`*_content_list.json`、`*_middle.json`、`*_model.json` 等文件；
- 常用参数：`model_version`、`language`、`enable_table`、`enable_formula`、`file.is_ocr`、`file.page_ranges`、`extra_formats`。

专利默认建议：

- 普通电子 PDF：`model_version=pipeline`，`is_ocr=false`；
- 扫描件、附图页、复杂图文混排：`model_version=vlm`，`is_ocr=true`；
- HTML 来源：`model_version=MinerU-HTML`；
- 材料/胶底资料：开启 table，避免配方表丢失。

### 2. Agent 轻量解析 API

适用小文件预览、无 token 的快速处理。

关键点：

- URL 接口：`POST https://mineru.net/api/v1/agent/parse/url`；
- 文件接口：`POST https://mineru.net/api/v1/agent/parse/file`；
- 查询接口：`GET https://mineru.net/api/v1/agent/parse/{task_id}`；
- 无需 Authorization；
- 只返回 Markdown 下载链接；
- 官方限制为较小文件和较少页数，且有 IP 限频。

专利使用限制：

- 不适合作为正式证据链，因为没有完整 JSON/zip；
- 不适合长说明书、案卷批量文件、附图多页扫描件；
- 适合先判断文件是否可读、章节是否大致完整。

### 3. 本地 MinerU CLI

适用涉密交底书、不可上传资料、本地批量预处理。

关键点：

- 快速命令：`mineru -p <input_path> -o <output_path>`；
- 支持 `--api-url` 连接已有 MinerU FastAPI；
- 解析方法可选 `auto`、`txt`、`ocr`；
- 可通过 `-f` 控制公式，`-t` 控制表格；
- 本地 `mineru-api` 支持 `/health`、`/tasks`、`/file_parse`、`/tasks/{task_id}` 等接口。

专利使用限制：

- 本地模型和依赖较重；
- Windows GPU 加速需要额外安装匹配的 PyTorch；
- 首次模型下载和渲染可能很慢。

## 推荐决策表

| 输入 | 推荐 |
|---|---|
| 公开专利 PDF、需要后续拆权利要求 | 精准 API `pipeline`，保留 zip |
| 扫描版授权文本 | 精准 API `vlm + is_ocr=true` |
| 只有 5-10 页交底书草稿 | Agent API 预览，正式处理再走精准或本地 |
| 涉密技术交底书 | 本地 MinerU CLI |
| 胶底/材料配方 | 精准 API，表格开启，后处理材料线索 |
| 附图页/标号页 | 精准 API `vlm + is_ocr=true`，重点查图号和标号 |

## 实践风险

1. **缓存问题**：精准 API 对 URL 内容可能有缓存参数。若远程文件刚更新，应使用 `no_cache` 或换 URL。本 skill 当前脚本未默认开放该参数，避免复杂化，后续可扩展。
2. **页码范围差异**：精准 API 支持 `2,4-6`、`2--2` 等复杂范围；Agent 轻量 API 只支持简单范围。
3. **Agent 输出不足**：Agent 只给 Markdown，不适合做表格/坐标/版面证据链。
4. **表格识别误差**：材料配方表一旦错列，会直接影响技术方案理解，必须人工对照原图。
5. **页眉页脚混入**：MinerU 会处理 headers/footers/page numbers，但正式专利文本仍需确认这些内容未混入正文。
6. **权利要求断行**：OCR 可能把单条权利要求拆成多段；后处理只做保守合并，不应自动重写技术特征。
