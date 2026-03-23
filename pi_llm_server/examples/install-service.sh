#!/bin/bash
# PI-LLM-Server systemd 服务安装脚本
# 自动检测当前环境并生成合适的 service 文件

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_TEMPLATE="${SCRIPT_DIR}/pi-llm-server.service.template"
SERVICE_NAME="pi-llm-server"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================"
echo "PI-LLM-Server systemd 服务安装脚本"
echo "============================================"
echo

# 检测当前用户
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
echo "✓ 检测到用户：${CURRENT_USER}/${CURRENT_GROUP}"

# 检测 Python 路径
PYTHON_PATH=$(which python)
echo "✓ 检测到 Python: ${PYTHON_PATH}"

# 检测是否在 conda 环境中
if [[ -n "${CONDA_DEFAULT_ENV}" ]]; then
    CONDA_ENV="${CONDA_DEFAULT_ENV}"
    CONDA_PREFIX="${CONDA_PREFIX}"
    echo "✓ 检测到 Conda 环境：${CONDA_ENV}"
    echo "  Conda 路径：${CONDA_PREFIX}"
fi

# 检测项目目录（如果使用源码安装）
PROJECT_DIR=""
if [[ -f "${SCRIPT_DIR}/../pyproject.toml" ]]; then
    PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
    echo "✓ 检测到项目目录：${PROJECT_DIR}"
fi

# 检测 pip 安装的包路径
PACKAGE_PATH=$(python -c "import pi_llm_server; from pathlib import Path; print(Path(pi_llm_server.__file__).parent)" 2>/dev/null || echo "")
if [[ -n "${PACKAGE_PATH}" ]]; then
    echo "✓ 检测到已安装包路径：${PACKAGE_PATH}"
fi

echo
echo "请选择安装模式:"
echo "  1) 使用 pip 安装的包（推荐，适合生产环境）"
echo "  2) 使用源码目录（适合开发调试）"
echo

if [[ -n "${PROJECT_DIR}" ]]; then
    echo "当前检测到项目目录：${PROJECT_DIR}"
fi
echo

# 默认选择模式 1（pip 安装）
INSTALL_MODE="${INSTALL_MODE:-1}"
read -p "请选择模式 (1/2) [默认：1]: " INPUT_MODE
if [[ -n "${INPUT_MODE}" ]]; then
    INSTALL_MODE="${INPUT_MODE}"
fi

# 生成 service 文件
echo
echo "生成 systemd 服务文件..."

cat > "${SERVICE_FILE}.tmp" << EOF
[Unit]
Description=PI-LLM Unified Server
Documentation=https://github.com/bushuhui/pi-llm-server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_GROUP}
EOF

if [[ "${INSTALL_MODE}" == "2" && -n "${PROJECT_DIR}" ]]; then
    # 源码模式
    cat >> "${SERVICE_FILE}.tmp" << EOF
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${CONDA_PREFIX:-/usr/local}/bin:%PATH%"
ExecStart=${PYTHON_PATH} -m pi_llm_server
EOF
    echo "✓ 已配置为源码模式：${PROJECT_DIR}"
else
    # pip 安装模式 - 不设置 WorkingDirectory，使用默认值
    cat >> "${SERVICE_FILE}.tmp" << EOF
# WorkingDirectory 可选，pip 安装时不需要
ExecStart=${PYTHON_PATH} -m pi_llm_server
EOF
    echo "✓ 已配置为 pip 安装模式"
fi

# 添加通用配置
cat >> "${SERVICE_FILE}.tmp" << EOF
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-llm-server

# 资源限制
LimitNOFILE=65535
LimitNPROC=4096

# 安全选项
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 移动到正式位置
sudo mv "${SERVICE_FILE}.tmp" "${SERVICE_FILE}"
echo "✓ 服务文件已生成：${SERVICE_FILE}"

echo
echo "预览生成的服务文件内容:"
echo "----------------------------------------"
cat "${SERVICE_FILE}"
echo "----------------------------------------"
echo

# 重新加载 systemd
echo "重新加载 systemd 配置..."
sudo systemctl daemon-reload
echo "✓ systemd 配置已重载"

echo
echo "============================================"
echo "安装完成！"
echo "============================================"
echo
echo "使用命令:"
echo "  # 启动服务"
echo "  sudo systemctl start ${SERVICE_NAME}"
echo
echo "  # 设置开机自启"
echo "  sudo systemctl enable ${SERVICE_NAME}"
echo
echo "  # 查看服务状态"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo
echo "  # 查看日志"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo
echo "  # 停止服务"
echo "  sudo systemctl stop ${SERVICE_NAME}"
echo
echo "  # 卸载服务"
echo "  sudo systemctl disable ${SERVICE_NAME}"
echo "  sudo rm ${SERVICE_FILE}"
echo "  sudo systemctl daemon-reload"
echo
