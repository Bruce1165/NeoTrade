#!/bin/bash
# Trading Screener Dashboard 启动脚本

echo "🚀 启动 Trading Screener Dashboard..."
echo ""

# 切换到工作目录
cd "$(dirname "$0")/../.."

# 启动 Flask 后端（后台运行）
cd dashboard
python3 app.py &
APP_PID=$!

# 等待服务启动
sleep 2

# 自动打开浏览器
open "http://localhost:5003/static/index.html"

echo ""
echo "✅ Dashboard 已启动"
echo "🌐 访问地址: http://localhost:5003/static/index.html"
echo "📝 按 Ctrl+C 停止服务"
echo ""

# 等待进程
wait $APP_PID
