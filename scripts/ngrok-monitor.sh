#!/bin/bash
# Ngrok Monitor 启动脚本
# 用于后台运行监控服务

WORKSPACE="/Users/mac/.openclaw/workspace-neo"
SCRIPT="$WORKSPACE/scripts/monitor_ngrok.py"
PIDFILE="/tmp/ngrok-monitor.pid"
LOGFILE="$WORKSPACE/logs/ngrok_monitor_nohup.log"

case "$1" in
    start)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "Ngrok 监控服务已在运行 (PID: $(cat "$PIDFILE"))"
            exit 1
        fi
        
        echo "🚀 启动 Ngrok 监控服务..."
        cd "$WORKSPACE"
        
        # 使用 nohup 启动
        nohup python3 "$SCRIPT" > "$LOGFILE" 2>&1 &
        echo $! > "$PIDFILE"
        
        sleep 2
        
        if kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "✅ 监控服务已启动 (PID: $(cat "$PIDFILE"))"
            echo "📋 日志: $WORKSPACE/logs/ngrok_monitor.log"
            echo "📝 nohup日志: $LOGFILE"
        else
            echo "❌ 启动失败，请检查日志"
            rm -f "$PIDFILE"
            exit 1
        fi
        ;;
        
    stop)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "🛑 停止 Ngrok 监控服务 (PID: $PID)..."
                kill "$PID"
                rm -f "$PIDFILE"
                echo "✅ 已停止"
            else
                echo "服务未运行"
                rm -f "$PIDFILE"
            fi
        else
            echo "服务未运行"
        fi
        ;;
        
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            echo "✅ Ngrok 监控服务运行中 (PID: $(cat "$PIDFILE"))"
            python3 "$SCRIPT" --status
        else
            echo "❌ Ngrok 监控服务未运行"
            rm -f "$PIDFILE" 2>/dev/null
        fi
        ;;
        
    check)
        # 执行一次检查
        python3 "$SCRIPT" --once
        ;;
        
    log)
        # 查看日志
        tail -f "$WORKSPACE/logs/ngrok_monitor.log"
        ;;
        
    *)
        echo "用法: $0 {start|stop|restart|status|check|log}"
        echo ""
        echo "命令:"
        echo "  start    - 启动监控服务"
        echo "  stop     - 停止监控服务"
        echo "  restart  - 重启监控服务"
        echo "  status   - 查看服务状态"
        echo "  check    - 执行一次检查"
        echo "  log      - 查看实时日志"
        exit 1
        ;;
esac
