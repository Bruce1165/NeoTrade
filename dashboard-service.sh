#!/bin/bash
# Dashboard 服务管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="/Users/mac/.openclaw/workspace-neo"
PIDFILE="/tmp/dashboard-ngrok.pid"
LOGFILE="/tmp/dashboard-ngrok.log"

case "$1" in
    start)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "Dashboard 服务已在运行"
            exit 1
        fi
        
        echo "启动 Dashboard 服务..."
        cd "$WORKSPACE"
        
        # 启动 ngrok
        nohup ngrok http 5003 --basic-auth="admin:bruce2024" > "$LOGFILE" 2>&1 &
        echo $! > "$PIDFILE"
        
        sleep 3
        
        # 获取公网 URL
        URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
        
        if [ -n "$URL" ]; then
            echo "✅ Dashboard 已启动"
            echo "📍 访问地址: $URL"
            echo "🔐 登录信息: admin / bruce2024"
            
            # 保存 URL 到文件
            echo "$URL" > /tmp/dashboard-url.txt
            echo "$(date): $URL" >> "$WORKSPACE/data/dashboard-urls.log"
        else
            echo "⚠️  服务启动中，请稍后检查日志"
        fi
        ;;
        
    stop)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                rm -f "$PIDFILE"
                echo "✅ Dashboard 服务已停止"
            else
                echo "服务未运行"
                rm -f "$PIDFILE"
            fi
        else
            echo "服务未运行"
        fi
        ;;
        
    status)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
            echo "✅ Dashboard 运行中"
            if [ -n "$URL" ]; then
                echo "📍 访问地址: $URL"
                echo "🔐 登录信息: admin / bruce2024"
            fi
        else
            echo "❌ Dashboard 未运行"
        fi
        ;;
        
    url)
        URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
        if [ -n "$URL" ]; then
            echo "$URL"
        else
            echo "无法获取 URL，请检查服务状态"
        fi
        ;;
        
    notify)
        # 发送 URL 变更通知（需要配合 cron 使用）
        if [ -f /tmp/dashboard-url.txt ]; then
            OLD_URL=$(cat /tmp/dashboard-url.txt)
        else
            OLD_URL=""
        fi
        
        NEW_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)
        
        if [ -n "$NEW_URL" ] && [ "$NEW_URL" != "$OLD_URL" ]; then
            echo "$NEW_URL" > /tmp/dashboard-url.txt
            echo "$(date): URL 变更 $OLD_URL -> $NEW_URL" >> "$WORKSPACE/data/dashboard-urls.log"
            echo "🔔 Dashboard URL 已变更: $NEW_URL"
            # 这里可以添加发送通知的逻辑
        fi
        ;;
        
    *)
        echo "用法: $0 {start|stop|status|url|notify}"
        echo ""
        echo "命令:"
        echo "  start   - 启动 Dashboard 服务"
        echo "  stop    - 停止 Dashboard 服务"
        echo "  status  - 查看服务状态"
        echo "  url     - 获取当前访问地址"
        echo "  notify  - 检查 URL 变更（用于 cron）"
        exit 1
        ;;
esac
