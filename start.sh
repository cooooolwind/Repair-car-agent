#!/bin/bash

echo "🚀 启动 CarRepair Agent..."

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查并创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖包..."
pip install -r requirements.txt

# 确保必要的目录存在
mkdir -p image
mkdir -p uploads
mkdir -p static

# 设置环境变量（可选）
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 启动后端 API 服务
echo ""
echo "✅ 服务启动成功！"
echo "🌐 请在浏览器中访问: http://127.0.0.1:8000/static/index.html"
echo "📡 API 服务地址: http://127.0.0.1:8000"
echo "⏹️  按 Ctrl+C 停止服务"
echo ""

python3 api_server.py
