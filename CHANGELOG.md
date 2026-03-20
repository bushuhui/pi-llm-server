# Change Log

所有重要的项目变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

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
| 1.1.0 | 2026-03-20 | 目录结构重构，服务脚本迁移到 launcher/clients |
| 1.0.0 | 2026-03-19 | 标准 Python 包结构重构完成 |
| 0.1.0 | 2026-03-17 | 初始版本发布 |

---

## 提交统计

```
Author: bushuhui

Commit 日期              信息
------ ----------------- ------------------------------------------
5cabba9  2026-03-20      Update pyproject.toml with comprehensive dependency groups
b890704  2026-03-20      update prompt
2b34e96  2026-03-20      Improve scripts
540fc68  2026-03-20      Update scripts/service_manager.py
5877b7d  2026-03-20      Merge branch 'master' of gitee.com:pi-lab/pi-llm-server
c490522  2026-03-20      Improve requirements_mineru.txt requirements_vllm.txt
e293ea1  2026-03-20      add LICENSE.
031effa  2026-03-19      First project refresh
f23bf93  2026-03-19      Finish project structure design
2168e3a  2026-03-18      Improve project design doc
6e94761  2026-03-17      update doc
e189aab  2026-03-17      First version
```

---

*最后更新：2026-03-20*
