# Change Log

所有重要的项目变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.1.7] - 2026-04-23

### Added

- **独立服务守护进程 (`service_daemon.py`)**:
  - 新增独立进程监控器，定期检查各子服务健康状态
  - 使用推理检测验证服务真正可用，而非仅 HTTP 端点响应
  - 检测连续失败超过阈值（默认 3 次）后自动重启服务
  - 最大重启限制（默认 3 次），达到上限后停止自动重启等待人工干预
  - 重启计数和状态持久化保存，防止重启循环

- **推理健康检测**:
  - Embedding: 使用测试文本 `"健康检测测试"` 调用实际 API
  - ASR: 生成 1 秒测试音频（16kHz, mono, 16bit WAV）调用转写 API
  - Reranker: 使用测试查询和文档调用重排序 API
  - MinerU: 生成测试图片（200x50 PNG）调用解析 API

- **服务级冷却期配置**:
  - 防止服务启动期间被误判为失败而触发重启
  - 各服务独立配置冷却时间：
    - Embedding/Reranker: 60 秒（模型加载快）
    - ASR: 180 秒（GPU 模型加载慢）
    - MinerU: 120 秒（PDF 解析服务启动需要时间）

- **守护进程配置项** (`config.yaml` 新增 `daemon` 配置节):
  - `check_interval`: 健康检查间隔（默认 30 秒）
  - `http_timeout`: HTTP 检查超时（默认 10 秒）
  - `inference_timeout`: 推理检测超时（默认 5 秒）
  - `unhealthy_threshold`: 连续失败判定阈值（默认 3 次）
  - `restart_cooldown`: 重启后冷却时间（默认 120 秒）
  - `max_restart_attempts`: 单次最多重启尝试（默认 3 次）
  - `services`: 服务级别配置覆盖

### Changed

- **`pi_llm_server/launcher/service_manager.py`**:
  - 新增 'daemon' 到 SERVICE_CONFIG
  - 修改 `is_service_running()`, `start_service()`, `stop_service()`, `show_status()` 支持守护进程
  - `start_all()` 最后启动守护进程（在其他服务之后）
  - `stop_all()` 首先停止守护进程（在其他服务之前）

- **`pi_llm_server/config.py`**:
  - 新增 `DaemonServiceConfig` 类（服务级别守护进程配置）
  - 新增 `DaemonConfig` 类（守护进程全局配置）
  - 新增 `inference_timeout` 配置项

- **`pi_llm_server/cli.py`**:
  - 更新 `show_full_status()` 显示守护进程状态

- **`pi_llm_server/examples/config.example.yaml`**:
  - 新增完整的 `daemon` 配置节示例

### Technical Details

- **检测流程**:
  1. 首先进行 HTTP 健康检查（调用 `/health` 端点）
  2. HTTP 成功后进行推理检测（调用实际 API）
  3. 连续失败计数达到阈值触发重启
  4. 重启后进入冷却期，期间不进行检测

- **测试数据生成**:
  - WAV 音频: 使用 `struct.pack` 手动构造，32044 字节（1 秒，16kHz, mono, 16bit）
  - PNG 图片: 使用 PIL 生成，510 字节（200x50 像素）

- **状态持久化**:
  - 状态文件: `~/.cache/pi-llm-server/daemon_state.json`
  - 记录各服务重启次数、最后重启时间、冷却期状态

---

## [1.1.6] - 2026-04-09

### Added

- **MinerU OCR 服务多格式文档支持**:
  - 新增支持文件类型：`.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`, `.jpg`, `.jpeg`, `.png`
  - Office 文档自动使用 libreoffice 转换为 PDF 后解析
  - 图片文件自动转换为 PDF 后解析
  - 文件类型检测和验证功能
  - 转换失败错误处理和超时保护（2 分钟超时）

- **依赖检测**:
  - 自动检测 libreoffice 是否安装
  - 未安装时返回友好的错误提示

### Changed

- **`pi_llm_server/services/mineru.py`**:
  - 新增 `SUPPORTED_DOCUMENT_TYPES` 常量定义支持的文档类型
  - 新增 `OFFICE_DOCUMENT_TYPES` 常量定义需要转换的 Office 文档类型
  - 新增 `get_file_extension()`, `is_supported_file()`, `needs_pdf_conversion()` 工具函数
  - 新增 `convert_to_pdf()` 异步函数实现 Office 文档转换
  - 改进 `parse_pdf()` 方法支持文件类型检测和自动转换
  - 更新 API 端点描述说明支持的文件类型

- **`pi_llm_server/clients/mineru_client.py`**:
  - 更新文档字符串说明支持的文件类型
  - 改进 `call_mineru_api()` 方法添加文件类型检测和提示
  - 使用通用的 `application/octet-stream` 内容类型

- **`README.md`**:
  - 更新 PDF 解析部分添加支持的文件类型表格
  - 新增 Office 文档转换依赖安装说明（libreoffice）
  - 更新参数说明表格

### Technical Details

- **文件转换流程**:
  1. 客户端上传任意支持的文档类型
  2. 服务端检测文件扩展名
  3. Office 文档/图片 → 使用 libreoffice 转换为 PDF
  4. PDF → 调用现有 MinerU API 解析
  5. 返回统一的 ZIP 格式结果

- **错误处理**:
  - 不支持的文件类型返回 HTTP 400
  - libreoffice 未安装返回 HTTP 500 和明确错误信息
  - 转换超时返回 HTTP 504
  - 转换失败返回 HTTP 500 和详细错误日志

---

## [1.1.5] - 2026-03-23

### Changed

- **版本号统一管理**:
  - `pi_llm_server/__init__.py` 现在使用 `importlib.metadata.version()` 动态读取版本
  - 所有子服务文件统一使用 `from pi_llm_server import __version__`
  - 移除了所有硬编码的版本号，现在只需在 `pyproject.toml` 中维护版本号
  - 涉及文件：`server.py`, `launcher/asr_server.py`, `launcher/embedding_server.py`, `launcher/reranker_server.py`

- **systemd 服务部署改进**:
  - 删除硬编码路径的 `examples/pi-llm-server.service`
  - 新增 `examples/install-service.sh` 自动配置脚本
  - 新增 `examples/pi-llm-server.service.template` 模板文件
  - 安装脚本自动检测：当前用户、Conda 环境、项目安装模式（pip/源码）
  - 生成合适的 service 文件，无需手动编辑

- **examples 目录重构**:
  - 将 examples 目录从根目录迁移到 `pi_llm_server/examples/`
  - 现在作为包数据打包到 wheel 中
  - 更新 `pyproject.toml` 配置：`package-data` 添加 `examples/**/*`

- **README.md 全面更新**:
  - 新增命令行工具完整说明和命令表格
  - 更新服务启动方式说明（一站式启动、systemd 服务等）
  - 新增项目结构树和示例文件说明
  - 更新 systemd 服务安装指南，推荐使用自动安装脚本
  - 更新 Python 客户端示例代码结构

### Added

- **新增文件**:
  - `pi_llm_server/examples/install-service.sh` - systemd 服务自动安装脚本
  - `pi_llm_server/examples/pi-llm-server.service.template` - systemd 服务模板
  - `pi_llm_server/examples/__init__.py` - 包初始化文件

### Removed

- **删除文件**:
  - `examples/pi-llm-server.service` - 硬编码路径的旧 service 文件
  - `setup.py` - 已废弃，现完全使用 `pyproject.toml`

### Fixed

- 修正 README.md 中 examples 目录路径引用
- 修正队列配置策略表格中的并发数说明

---

## [1.1.4] - 2026-03-20

### Fixed
- **MinerU 服务修复**:
  - 修复网关调用 MinerU 后端的 API 路径错误（从 `/v1/ocr/parser` 改为 `/file_parse`）
  - 修复 MinerU 健康检查端点（从 `/health` 改为 `/openapi.json`）
  - MinerU 服务健康状态现在正确显示为 `healthy`

### Changed
- **文档更新**:
  - 更新 `README.md` 添加完整的 Python 客户端示例 (`examples/basic_usage.py`)
  - 更新 `README.md` 添加详细的 API 请求/响应示例
  - 更新 `README.md` 故障排查部分，增加健康状态说明
  - 修正 MinerU 环境说明：不需要独立 Python 环境，使用同一环境即可

### Added
- **测试文件**:
  - `examples/basic_usage.py` 现在包含完整的 API 调用示例
  - 支持使用 `data/audio_s.mp3` 和 `data/InfoLOD.pdf` 进行测试

---

## [1.1.3] - 2026-03-20

### Fixed
- **API 路径修复**:
  - 修正 ASR API 路径：从 `/v1/asr/transcribe` 改为 `/v1/audio/transcriptions`
  - 修正 PDF API 路径：从 `/v1/mineru/parse` 改为 `/v1/ocr/parser`
  - 修正 form 字段名：ASR 从 `audio` 改为 `file`，PDF 从 `file` 改为 `files`

- **响应字段修复**:
  - 修正 Rerank 响应字段：从 `score` 改为 `relevance_score`

### Changed
- **示例程序更新**:
  - 更新 `examples/basic_usage.py` 所有 API 调用路径
  - 添加 `transcribe_audio_sample()` 和 `parse_pdf_sample()` 函数
  - 改进错误处理和响应验证

---

## [1.1.2] - 2026-03-20

### Added
- **文档完善**:
  - 新增 `doc/README_services.md` 后台服务详细文档
  - 更新 `README.md` 添加项目目的、模型下载、使用方法、关联项目说明
  - 新增 `doc/note.md` 开发笔记

- **依赖管理**:
  - 新增 `doc/requirements_vllm.txt` vLLM 服务依赖配置
  - 新增 `doc/requirements_mineru.txt` MinerU 服务依赖配置
  - 完善 `pyproject.toml` 依赖分组 (vllm/embedding/reranker/asr/mineru/models/api/monitoring/utils/dev/mcp)

- **测试增强**:
  - 新增 `tests/test_cli_launch.py` CLI 启动测试
  - 新增 `tests/test_full_stack.py` 全栈集成测试

### Changed
- **目录结构重构**:
  - 迁移脚本从 `scripts/` 到 `pi_llm_server/launcher/` (服务器端)
  - 迁移脚本从 `scripts/` 到 `pi_llm_server/clients/` (客户端)
  - 保留 `scripts/` 中的 `service_manager.py` 作为兼容入口

- **启动器模块** (`pi_llm_server/launcher/`):
  - `embedding_server.py` - Embedding 服务启动器
  - `asr_server.py` - ASR 语音识别服务启动器
  - `reranker_server.py` - Reranker 服务启动器
  - `service_manager.py` - 统一服务管理工具

- **客户端模块** (`pi_llm_server/clients/`):
  - `embedding_client.py` - Embedding 客户端工具
  - `asr_client.py` - ASR 客户端工具
  - `reranker_client.py` - Reranker 客户端工具
  - `mineru_client.py` - MinerU 客户端工具

- **核心模块增强**:
  - `pi_llm_server/__main__.py` - 增强命令行参数支持
  - `pi_llm_server/cli.py` - 优化配置加载逻辑
  - `pi_llm_server/config.py` - 改进配置验证

- **配置文件**:
  - 更新 `examples/config.example.yaml` 精简配置项
  - 移除不再需要的 `scripts/start_all_services.sh`

### Removed
- 删除旧的 `scripts/` 目录下冗余脚本
- 移除 `scripts/pi-llm-server.service` systemd 服务文件

### Fixed
- 修正服务启动脚本路径引用
- 修复客户端工具默认 URL 配置

---

## [1.1.0] - 2026-03-20

### Added
- 完整的 Python 包管理结构 (`pyproject.toml`)
- 命令行入口 `pi-llm-server`
- `python -m pi_llm_server` 模块入口
- CLI 服务管理工具 `scripts/service_manager.py`
- 测试套件 (`tests/`)
- 使用示例 (`examples/`)
- 差异化请求队列管理
- 健康监控后台轮询

### Changed
- 重构主程序入口 (`cli.py`, `server.py`, `__main__.py`)
- 迁移子服务脚本到 `scripts/` 目录
- 更新 `.gitignore` 为标准 Python 项目格式
- 更新 `README.md` 添加安装说明和测试章节

### Fixed
- 修复 `server.py` 中 `QueueManager` 和 `HealthMonitor` 初始化调用
- 修复测试文件中 `AuthManager` 和 `Service` 类的 API 调用

---

## [1.0.0] - 2026-03-19

### Added
- **项目结构重构**: 完成标准 Python 包结构设计
  - 根目录布局 (root package layout)
  - `pyproject.toml` 构建系统配置
  - 支持 pip 可编辑安装模式

- **多种启动方式**:
  - `pi-llm-server` 命令行入口
  - `python -m pi_llm_server` 模块运行
  - `python scripts/service_manager.py` 服务管理工具
  - 保留原 `pi-llm-server.py` 兼容旧版

- **测试框架**:
  - pytest + pytest-asyncio 异步测试支持
  - 配置模块测试 (`test_config.py`)
  - 认证模块测试 (`test_auth.py`)
  - 队列管理器测试 (`test_queue.py`)
  - 服务模块测试 (`test_services.py`)
  - 26 个测试用例全部通过

- **服务管理工具**:
  - `start` - 启动服务（支持 `--all`, `--with-gateway`, 单服务）
  - `stop` - 停止服务
  - `restart` - 重启服务
  - `status` - 查看服务状态

- **示例文档**:
  - `examples/basic_usage.py` - Python 客户端调用示例
  - `examples/config.example.yaml` - 配置文件示例

### Changed
- **目录结构**:
  ```
  pi-llm-server/
  ├── pyproject.toml                # 项目配置文件
  ├── pi_llm_server/                # 主包
  │   ├── __init__.py
  │   ├── __main__.py               # python -m 入口
  │   ├── cli.py                    # 命令行入口
  │   ├── server.py                 # FastAPI 应用
  │   ├── config.py
  │   ├── auth.py
  │   ├── queue_manager.py
  │   ├── health_monitor.py
  │   ├── services/
  │   └── utils/
  ├── scripts/                      # 子服务脚本
  ├── tests/                        # 测试目录
  └── examples/                     # 使用示例
  ```

- **配置文件位置**: 默认 `~/.config/pi-llm-server/config.yaml`
- **日志目录**: 使用用户目录 `~/.cache/pi-llm-server/logs/`
- **PID 目录**: 使用用户目录 `~/.cache/pi-llm-server/pids/`

---

## [0.1.0] - 2026-03-17

### Added
- **初始版本**: 第一版项目代码
  - 主程序 `pi-llm-server.py`
  - 配置文件 `config.example.yaml`
  - 基础 README 文档

- **子服务**:
  - Embedding 服务 (`embedding_server.py`, `embedding_client.py`)
  - ASR 语音识别服务 (`asr_server.py`, `asr_client.py`)
  - Reranker 服务 (`reranker_server.py`, `reranker_client.py`)
  - MinerU PDF 解析服务 (`mineru_server.sh`, `mineru_client.py`)

- **辅助脚本**:
  - `start_all_services.sh` - 一键启动所有服务

---

## 版本说明

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.1.7 | 2026-04-23 | 独立服务守护进程、推理健康检测、服务级冷却期配置 |
| 1.1.6 | 2026-04-09 | MinerU OCR 多格式文档支持、libreoffice 文档转换 |
| 1.1.5 | 2026-03-23 | 版本号统一管理、systemd 服务自动部署、examples 目录重构、README 全面更新 |
| 1.1.4 | 2026-03-20 | MinerU API 路径修复，README 文档完善 |
| 1.1.3 | 2026-03-20 | API 路径修复，示例程序更新 |
| 1.1.2 | 2026-03-20 | 目录结构重构，服务脚本迁移到 launcher/clients |
| 1.1.0 | 2026-03-20 | 目录结构重构，服务脚本迁移到 launcher/clients |
| 1.0.0 | 2026-03-19 | 标准 Python 包结构重构完成 |
| 0.1.0 | 2026-03-17 | 初始版本发布 |

---


*最后更新：2026-04-23 (v1.1.7)*
