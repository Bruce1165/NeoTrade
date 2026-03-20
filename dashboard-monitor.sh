# Dashboard URL 监控脚本
# 当 URL 变更时发送通知

WORKSPACE="/Users/mac/.openclaw/workspace-neo"
PIDFILE="/tmp/dashboard-ngrok.pid"
URL_FILE="/tmp/dashboard-url.txt"
LOG_FILE="$WORKSPACE/data/dashboard-urls.log"

# 检查服务是否运行
if [ ! -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    # 服务未运行，尝试启动
    echo "$(date): 服务未运行，正在启动..." >> "$LOG_FILE"
    "$WORKSPACE/dashboard-service.sh" start
    exit 0
fi

# 获取当前 URL
CURRENT_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

if [ -z "$CURRENT_URL" ]; then
    echo "$(date): 无法获取当前 URL" >> "$LOG_FILE"
    exit 1
fi

# 检查是否有历史 URL
if [ -f "$URL_FILE" ]; then
    OLD_URL=$(cat "$URL_FILE")
else
    OLD_URL=""
fi

# 如果 URL 变更，记录并通知
if [ "$CURRENT_URL" != "$OLD_URL" ]; then
    echo "$CURRENT_URL" > "$URL_FILE"
    echo "$(date): URL 变更 $OLD_URL -> $CURRENT_URL" >> "$LOG_FILE"
    
    # 发送通知（如果有通知渠道配置）
    # 可以在这里添加发送邮件、Telegram、Slack 等通知
    
    # 示例：写入到显眼的位置
    echo "============================================" >> "$LOG_FILE"
    echo "🔔 Dashboard URL 已变更!" >> "$LOG_FILE"
    echo "📍 新地址: $CURRENT_URL" >> "$LOG_FILE"
    echo "🔐 登录信息: admin / bruce2024" >> "$LOG_FILE"
    echo "============================================" >> "$LOG_FILE"
fi
