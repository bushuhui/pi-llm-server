# PI-LLM-Server Python 标准化改造方案

## 1. 当前项目结构分析

### 1.1 现有目录结构

```
pi-llm-server/
├── pi-llm-server.py              # 主程序入口
├── pi_llm_server/                # 已有包结构（部分规范）
│   ├── __init__.py
│   ├── config.py
│   ├── auth.py
│   ├── queue_manager.py
│   ├── health_monitor.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── embedding.py
│   │   ├── asr.py
│   │   ├── reranker.py
│   │   └── mineru.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── exceptions.py
├── embedding_server.py           # 独立服务脚本
├── embedding_client.py
├── asr_server.py
├── asr_client.py
├── reranker_server.py
├── reranker_client.py
├── mineru_client.py
├── mineru_server.sh
├── config.yaml
├── config.example.yaml
├── requirements.txt
├── README.md
├── backup/                       # 备份文件（应移除或归档）
├── data/                         # 测试数据
├── logs/                         # 日志目录
├── results/                      # 运行结果
└── doc/                          # 文档
```

### 1.2 当前问题分析

| 问题类别 | 具体问题 | 影响 |
|----------|----------|------|
| **包结构** | 缺少 `pyproject.toml`，无法通过 pip 安装 | 用户需手动配置 Python 路径 |
| **入口点** | 主程序 `pi-llm-server.py` 在根目录，不是包内模块 | 无法使用 `pi-llm-server` 命令启动 |
| **子服务定位** | `embedding_server.py` 等独立脚本与包代码并存 | 代码分散，维护困难 |
| **备份文件** | `backup/` 目录包含旧代码 | 干扰开发，应归档 |
| **测试缺失** | 无 `tests/` 目录 | 无法保证代码质量 |
| **数据文件** | `data/`、`results/` 混在项目根目录 | 不符合 Python 项目规范 |

---

## 2. 标准 Python 项目结构目标

### 2.1 推荐目录结构（根目录布局）

```
pi-llm-server/
├── pyproject.toml                # 【新增】项目配置和构建元数据
├── README.md                     # 项目说明
├── LICENSE                       # 【新增】许可证文件
├── CHANGELOG.md                  # 【新增】变更日志（可选）
├── requirements-dev.txt          # 【新增】开发依赖（可选）
│
├── pi_llm_server/                # 主包（保留在根目录）
│   ├── __init__.py               # 导出 __version__ 等
│   ├── __main__.py               # 【新增】python -m 入口
│   ├── cli.py                    # 【新增】命令行入口
│   ├── server.py                 # 【新增】FastAPI app 定义
│   ├── config.py
│   ├── auth.py
│   ├── queue_manager.py
│   ├── health_monitor.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py               # 【新增】服务基类（可选）
│   │   ├── embedding.py
│   │   ├── asr.py
│   │   ├── reranker.py
│   │   └── mineru.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── exceptions.py
│
├── scripts/                      # 【新增】辅助脚本（保持原有命名）
│   ├── embedding_server.py       # 原 embedding_server.py 迁移
│   ├── embedding_client.py       # 原 embedding_client.py 迁移
│   ├── asr_server.py             # 原 asr_server.py 迁移
│   ├── asr_client.py             # 原 asr_client.py 迁移
│   ├── reranker_server.py        # 原 reranker_server.py 迁移
│   ├── reranker_client.py        # 原 reranker_client.py 迁移
│   ├── mineru_server.sh          # 原 mineru_server.sh 迁移
│   ├── mineru_client.py          # 原 mineru_client.py 迁移
│   └── service_manager.py        # 【新增】CLI 服务管理工具
│
├── tests/                        # 【新增】测试目录
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_queue.py
│   └── test_services.py
│
├── examples/                     # 【新增】使用示例
│   ├── basic_usage.py
│   └── config.yaml.example
│
├── data/                         # 测试数据（保留，加入 .gitignore）
│   └── ...
│
├── doc/                          # 文档（保留）
│   └── ...
│
└── .gitignore                    # 更新以排除构建产物
```

### 2.1.1 系统目录结构（运行时）

```
/var/log/pi-llm-server/           # 日志目录（需要 root 权限创建）
├── embedding.log
├── asr.log
├── reranker.log
├── mineru.log
└── pi-llm-server.log

/run/pi-llm-server/               # PID 文件目录（需要 root 权限创建）
├── embedding.pid
├── asr.pid
├── reranker.pid
├── mineru.pid
└── pi-llm-server.pid

~/.config/pi-llm-server/          # 用户配置目录（首次运行自动创建）
└── config.yaml                   # 用户配置文件
```

### 2.2 为什么选择根目录布局而非 src/ 布局

| 考量 | src/ 布局 | 根目录布局 | 本项目选择 |
|------|----------|-----------|-----------|
| 目录深度 | 较深 (`src/pi_llm_server/`) | 较浅 (`pi_llm_server/`) | ✅ 根目录 |
| 导航便利 | 多一层 | 更直接 | ✅ 根目录 |
| 测试安全性 | 强制使用安装的包 | 可能混用 | ⚠️ 但本地开发影响小 |
| 项目类型 | 大型库 | 应用/中型项目 | ✅ 本项目是服务端应用 |
| 改造成本 | 需移动现有包 | 保持现有结构 | ✅ 成本更低 |

**结论**: 本项目是服务端应用而非分发的库，根目录布局更简洁实用。

---

## 3. 核心改造步骤

### 3.1 步骤 1: 创建 `pyproject.toml`

这是标准 Python 项目的核心配置文件，定义项目元数据、依赖、入口点等。

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pi-llm-server"
version = "1.0.0"
description = "统一 LLM 服务网关 - 集成 Embedding、ASR、Reranker、MinerU 服务"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "PI-Lab Team", email = "bushuhui@foxmail.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: FastAPI",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
requires-python = ">=3.8"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "httpx>=0.24.0",
    "pyyaml>=6.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.6",
]

[project.optional-dependencies]
# Embedding 服务依赖
embedding = [
    "sentence-transformers>=2.2.0",
    "torch>=2.0.0",
]
# Reranker 服务依赖
reranker = [
    "transformers>=4.30.0",
    "torch>=2.0.0",
]
# ASR 服务依赖
asr = [
    "qwen-asr[vllm]>=0.1.0",
    "silero-vad>=0.4.0",
    "onnxruntime>=1.15.0",
    "soundfile>=0.12.0",
    "librosa>=0.10.0",
]
# MinerU 服务依赖（通常单独 conda 环境）
mineru = [
    # MinerU 需手动安装
]
# 开发依赖
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
# 全部依赖
all = [
    "pi-llm-server[embedding,reranker,asr,dev]",
]

[project.urls]
Homepage = "https://github.com/bushuhui/pi-llm-server"
Documentation = "https://pi-llm-server.readthedocs.io"
Repository = "https://github.com/bushuhui/pi-llm-server"
Changelog = "https://github.com/bushuhui/pi-llm-server/blob/main/CHANGELOG.md"

[project.scripts]
# 命令行入口点
pi-llm-server = "pi_llm_server.cli:main"
pi-llm-embedding = "pi_llm_server.services.embedding:main"
pi-llm-asr = "pi_llm_server.services.asr:main"
pi-llm-reranker = "pi_llm_server.services.reranker:main"
pi-llm-mineru = "pi_llm_server.services.mineru:main"

[tool.setuptools.package-data]
pi_llm_server = ["*.yaml", "*.yaml.example"]
```

**关键说明**:
- `[project.scripts]`: 定义 pip 安装后可用的命令
- `[project.optional-dependencies]`: 允许用户按需安装依赖

---

### 3.2 步骤 2: 重构主程序入口

#### 2.1 创建 `pi_llm_server/__main__.py`

支持 `python -m pi_llm_server` 运行：

```python
"""
允许通过 python -m pi_llm_server 启动服务
"""
from pi_llm_server.cli import main

if __name__ == "__main__":
    main()
```

#### 2.2 创建 `pi_llm_server/cli.py`

命令行入口：

```python
#!/usr/bin/env python3
"""
PI-LLM-Server 命令行入口
"""
import argparse
import sys
from pi_llm_server.server import app
from pi_llm_server.config import init_config
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="PI-LLM Server - 统一 LLM 服务网关")
    parser.add_argument("--config", "-c", default=None, help="配置文件路径（默认：~/.config/pi-llm-server/config.yaml）")
    parser.add_argument("--host", default=None, help="服务主机地址")
    parser.add_argument("--port", "-p", type=int, default=None, help="服务端口")
    parser.add_argument("--log-level", default=None, choices=["debug", "info", "warning", "error"])

    args = parser.parse_args()

    # 加载配置并启动 (逻辑从原 pi-llm-server.py 迁移)
    config = init_config(args.config)
    host = args.host or config.server.host
    port = args.port or config.server.port

    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
```

#### 2.3 创建 `pi_llm_server/server.py`

FastAPI 应用定义（从原 `pi-llm-server.py` 迁移）：

```python
"""
PI-LLM-Server FastAPI 应用定义
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动逻辑
    yield
    # 关闭逻辑

app = FastAPI(
    title="PI-LLM Server",
    description="统一 LLM 服务网关",
    version="1.0.0",
    lifespan=lifespan,
)

# 路由注册逻辑...
```

---

### 3.3 步骤 3: 迁移子服务脚本到 `scripts/`

**设计变更**：子服务脚本和客户端脚本都迁移到 `scripts/`，保持原有命名不变，新增 CLI 服务管理工具

```
scripts/
├── embedding_server.py       # 原 embedding_server.py 迁移（名称不变）
├── embedding_client.py       # 原 embedding_client.py 迁移（名称不变）
├── asr_server.py             # 原 asr_server.py 迁移（名称不变）
├── asr_client.py             # 原 asr_client.py 迁移（名称不变）
├── reranker_server.py        # 原 reranker_server.py 迁移（名称不变）
├── reranker_client.py        # 原 reranker_client.py 迁移（名称不变）
├── mineru_server.sh          # 原 mineru_server.sh 迁移（名称不变）
├── mineru_client.py          # 原 mineru_client.py 迁移（名称不变）
├── service_manager.py        # 【新增】CLI 服务管理工具
└── start_all_services.sh     # 可选：保留原 bash 脚本作为兼容
```

**迁移方式**:

1. 将原脚本复制到 `scripts/`
2. 修改路径引用（如日志目录、数据目录需要调整为相对路径或绝对路径）
3. 添加 shebang 并设置可执行权限

#### 3.3.1 CLI 服务管理工具设计

**文件**: `scripts/service_manager.py`

**功能需求**:
1. 服务启动：支持启动单个服务或所有服务
2. 服务检查：通过健康检查端口检测服务是否运行
3. 日志管理：使用 Linux 标准日志目录 `/var/log/pi-llm-server/`
4. 进程管理：使用 Linux 标准 PID 目录 `/run/pi-llm-server/`
5. 状态显示：显示所有服务的运行状态

**命令设计**:
```bash
# 启动所有子服务
python scripts/service_manager.py start --all

# 启动单个服务
python scripts/service_manager.py start embedding
python scripts/service_manager.py start asr

# 启动子服务 + 统一网关
python scripts/service_manager.py start --with-gateway

# 停止所有服务
python scripts/service_manager.py stop --all

# 查看服务状态
python scripts/service_manager.py status

# 重启服务
python scripts/service_manager.py restart embedding
```

**服务配置**:
```python
SERVICE_CONFIG = {
    'embedding': {'script': 'embedding_server.py', 'port': 8091},
    'asr': {'script': 'asr_server.py', 'port': 8092},
    'reranker': {'script': 'reranker_server.py', 'port': 8093},
    'mineru': {'script': 'mineru_server.sh', 'port': 8094},
    'gateway': {'script': '../pi-llm-server.py', 'port': 8090},
}
```

**实现要点**:
- 使用 `subprocess.Popen` 启动服务
- PID 文件：`/run/pi-llm-server/{service}.pid`（遵循 Linux 标准）
- 健康检查：`curl http://127.0.0.1:{port}/health`
- 日志文件：`/var/log/pi-llm-server/{service}.log`（遵循 Linux 标准）

---

#### 3.3.2 配置文件管理

**配置目录**: `~/.config/pi-llm-server/`

**配置文件**: `~/.config/pi-llm-server/config.yaml`

**初始化逻辑**:
1. 程序启动时检查配置目录是否存在
2. 如果不存在，自动创建 `~/.config/pi-llm-server/`
3. 将项目中的 `config.example.yaml` 复制到配置目录作为初始配置
4. 提示用户修改配置文件

**实现示例**:
```python
import os
import shutil
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "pi-llm-server"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

def init_config():
    """初始化配置文件"""
    if not DEFAULT_CONFIG_DIR.exists():
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"创建配置目录：{DEFAULT_CONFIG_DIR}")

    if not DEFAULT_CONFIG_FILE.exists():
        # 从项目目录复制示例配置
        script_dir = Path(__file__).parent
        example_config = script_dir.parent / "config.example.yaml"
        if example_config.exists():
            shutil.copy2(example_config, DEFAULT_CONFIG_FILE)
            print(f"创建默认配置文件：{DEFAULT_CONFIG_FILE}")
            print("请修改配置文件后重新启动")
            sys.exit(1)

    return load_config(DEFAULT_CONFIG_FILE)
```

---

### 3.4 步骤 4: 添加测试目录

创建基础测试框架：

```python
# tests/test_config.py
import pytest
from pi_llm_server.config import ConfigManager

def test_config_load():
    """测试配置文件加载"""
    config = ConfigManager("config.example.yaml")
    assert config.server.port == 8090

def test_token_validation():
    """测试 Token 验证"""
    config = ConfigManager("config.example.yaml")
    assert config.validate_token("sk-admin-token-001", "/v1/embeddings")
```

---

### 3.5 步骤 5: 清理和归档

| 操作 | 目标 | 说明 |
|------|------|------|
| **移除** | `backup/` | 移入 git 归档分支或删除 |
| **清理** | `__pycache__/` | 加入 `.gitignore` |
| **归档** | `results/` | 移出主目录或加入 `.gitignore` |
| **废弃** | `logs/` | 日志改用系统目录 `/var/log/pi-llm-server/`，本地 `logs/` 目录移除或加入 `.gitignore` |
| **归档** | `data/` | 加入 `.gitignore`（测试数据保留） |
| **归档** | `output/` | 加入 `.gitignore` |

更新 `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs (项目本地 logs/ 已废弃，日志使用系统目录 /var/log/pi-llm-server/)
logs/
*.log

# Results and output
results/
output/
.asr_tmp/

# Config files (keep example)
config.yaml
!config.example.yaml

# Test data (optional)
data/*.mp3
data/*.pdf
```

---

## 4. 安装和使用方式

### 4.1 开发安装

```bash
# 进入项目目录
cd pi-llm-server

# 可编辑模式安装（开发推荐）
pip install -e ".[all]"

# 或只安装核心依赖
pip install -e .

# 或安装核心 + Embedding
pip install -e ".[embedding]"
```

### 4.2 生产安装

```bash
# 从 PyPI 安装（发布后）
pip install pi-llm-server

# 或从 GitHub 安装
pip install git+https://github.com/bushuhui/pi-llm-server.git

# 或从源码安装
pip install .
```

### 4.3 使用方式

```bash
# 方式 1: 使用命令行入口（推荐）
pi-llm-server

# 方式 2: 使用 python -m
python -m pi_llm_server

# 方式 3: 直接导入
from pi_llm_server import app
```

---

## 5. 改造检查清单

### 阶段 1: 基础结构
- [ ] 创建 `pyproject.toml`
- [ ] 创建 `pi_llm_server/__main__.py`
- [ ] 创建 `pi_llm_server/cli.py`
- [ ] 创建 `pi_llm_server/server.py`
- [ ] 更新 `pi_llm_server/__init__.py` 导出 `__version__`

### 阶段 2: 子服务迁移
- [ ] 创建 `scripts/` 目录
- [ ] 迁移 `embedding_server.py` → `scripts/embedding_server.py`
- [ ] 迁移 `embedding_client.py` → `scripts/embedding_client.py`
- [ ] 迁移 `asr_server.py` → `scripts/asr_server.py`
- [ ] 迁移 `asr_client.py` → `scripts/asr_client.py`
- [ ] 迁移 `reranker_server.py` → `scripts/reranker_server.py`
- [ ] 迁移 `reranker_client.py` → `scripts/reranker_client.py`
- [ ] 迁移 `mineru_server.sh` → `scripts/mineru_server.sh`
- [ ] 迁移 `mineru_client.py` → `scripts/mineru_client.py`
- [ ] 创建 `scripts/service_manager.py` CLI 工具

### 阶段 3: 测试和文档
- [ ] 创建 `tests/` 目录和基础测试
- [ ] 创建 `examples/` 目录
- [ ] 更新 `README.md` 添加安装说明
- [ ] 创建 `CHANGELOG.md`

### 阶段 4: 清理
- [ ] 更新 `.gitignore`
- [ ] 归档 `backup/` 目录
- [ ] 清理 `__pycache__/`
- [ ] 归档 `results/`、`data/`（测试数据）
- [ ] 移除项目本地 `logs/` 目录（日志改用系统目录 `/var/log/pi-llm-server/`）

### 阶段 4.5: 系统目录配置（需要 root 权限）
- [ ] 创建系统日志目录 `/var/log/pi-llm-server/`
- [ ] 创建系统 PID 目录 `/run/pi-llm-server/`
- [ ] 设置适当的权限（允许非 root 用户写入）

### 阶段 5: 验证
- [ ] 测试 `pip install -e .`
- [ ] 测试 `pi-llm-server` 命令
- [ ] 测试 `python -m pi_llm_server`
- [ ] 运行测试套件

---

## 6. 额外建议

### 6.1 版本管理

- 使用语义化版本 (SemVer): `主版本。次版本.修订版本`
- 在 `pi_llm_server/__init__.py` 中定义 `__version__`
- 使用 `CHANGELOG.md` 跟踪变更

### 6.2 持续集成

建议添加 GitHub Actions 工作流：

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.8", "3.9", "3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/ -v --cov=pi_llm_server
```

### 6.3 发布到 PyPI

```bash
# 安装构建工具
pip install build twine

# 构建分发包
python -m build

# 上传到 PyPI
twine upload dist/*
```

### 6.4 文档站点

使用 MkDocs 或 Sphinx 生成文档：

```bash
# MkDocs
pip install mkdocs mkdocs-material
mkdocs new docs-site
```

---

## 7. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| **路径变更** | 配置文件、日志路径需更新 | 在文档中明确说明 |
| **导入路径** | 原有 `from pi_llm_server` 需调整 | 保持包内导入不变 |
| **客户端脚本** | `embedding_client.py` 等需迁移到 `scripts/` | 更新文档说明新位置 |
| **MinerU 依赖** | 需单独 conda 环境 | 在文档中说明 |
| **系统目录权限** | `/var/log/pi-llm-server/` 和 `/run/pi-llm-server/` 需要 root 权限创建 | 提供安装脚本自动创建，或使用用户目录作为备选 |
| **配置初始化** | 首次运行时需自动创建配置 | 程序启动时检测并初始化 |

---

## 8. 总结

### 改造收益

1. **标准化**: 符合 Python 打包规范，支持 pip 安装
2. **易用性**: 用户可通过 `pi-llm-server` 命令直接启动
3. **可维护性**: 代码组织清晰，便于扩展
4. **可测试性**: 添加测试框架，保证质量
5. **可扩展性**: 便于添加新功能模块

### 优先级

1. **高优先级**: `pyproject.toml` + 入口点配置
2. **中优先级**: 子服务迁移、测试框架
3. **低优先级**: CI/CD、文档站点

---

**文档版本**: 1.0
**创建日期**: 2026-03-17
**作者**: AI Assistant
