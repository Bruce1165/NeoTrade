#!/bin/bash
# Neo量化研究体系 - Cron定时任务安装脚本（正确版）
# 创建5个循环任务，周一到周五执行

PLIST_DIR="$HOME/Library/LaunchAgents"
SCRIPT_DIR="/Users/mac/.openclaw/workspace-neo/scripts/cron"

# 创建单个Plist文件（使用数组指定多个weekday）
create_plist() {
    local name=$1
    local hour=$2
    local minute=$3
    local type=$4
    local label="${name}_${hour}${minute}"
    
    # 构建参数
    if [ -n "$type" ]; then
        args_str="
        <string>--type</string>
        <string>$type</string>"
    else
        args_str=""
    fi
    
    # 使用数组指定周一到周五
    cat > "$PLIST_DIR/com.neo.${label}.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>${SCRIPT_DIR}/${name}_task.py</string>${args_str}
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>${hour}</integer>
            <key>Minute</key>
            <integer>${minute}</integer>
            <key>Weekday</key>
            <integer>1</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>${hour}</integer>
            <key>Minute</key>
            <integer>${minute}</integer>
            <key>Weekday</key>
            <integer>2</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>${hour}</integer>
            <key>Minute</key>
            <integer>${minute}</integer>
            <key>Weekday</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>${hour}</integer>
            <key>Minute</key>
            <integer>${minute}</integer>
            <key>Weekday</key>
            <integer>4</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>${hour}</integer>
            <key>Minute</key>
            <integer>${minute}</integer>
            <key>Weekday</key>
            <integer>5</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_${label}.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_${label}_error.log</string>
</dict>
</plist>
EOF
    echo "创建: com.neo.${label}.plist"
}

# 创建目录
mkdir -p "$PLIST_DIR"
mkdir -p "/Users/mac/.openclaw/workspace-neo/logs"

echo "创建5个定时任务（周一到周五循环执行）..."
echo ""

# 创建5个任务
# 1. 9:35 指数观测
create_plist "intraday" 9 35 "index"

# 2. 9:45 指数观测
create_plist "intraday" 9 45 "index"

# 3. 10:00 涨跌分析
create_plist "intraday" 10 00 "analysis"

# 4. 15:00 收盘分析
create_plist "intraday" 15 00 "analysis"

# 5. 15:30 盘后深度复盘
create_plist "postmarket" 15 30 ""

echo ""
echo "===================================="
echo "任务文件已创建到: $PLIST_DIR"
echo "总共创建: $(ls $PLIST_DIR/com.neo.*.plist 2>/dev/null | wc -l) 个任务"
echo "===================================="
echo ""
echo "加载任务:"
echo "  launchctl load $PLIST_DIR/com.neo.*.plist"
