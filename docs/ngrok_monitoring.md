# Ngrok 监控配置文档

## 概述

本文档描述 Neo 股票数据分析系统的 Ngrok 隧道和 Flask 服务监控配置。

监控系统负责：
- 每 60 秒检查 ngrok 隧道状态
- 监控 Flask 服务健康状态
- 自动重启故障服务
- 记录告警事件

---

## 错误代码

| 错误代码 | 描述 | 处理方式 |
|---------|------|---------|
| `ERR_NGROK_3200` | ngrok 离线/隧道过期 | 自动重启 ngrok |
| `ERR_NGROK_334` | 会话冲突 | 自动重启 ngrok |
| `ERR_NGROK_502` | 后端服务不可达 | 重启 Flask + ngrok |
| `Connection refused` | Flask 未运行 | 自动重启 Flask |

---

## 安装

### 1. 依赖安装

```bash
# 确保已安装 Python 依赖
pip3 install psutil requests
```

### 2. 配置文件权限

```bash
chmod +x /Users/mac/.openclaw/workspace-neo/scripts/monitor_ngrok.py
chmod +x /Users/mac/.openclaw/workspace-neo/scripts/ngrok-monitor.sh
```

### 3. 配置 launchd 自动启动 (macOS)

```bash
# 复制 plist 文件
sudo cp /Users/mac/.openclaw/workspace-neo/scripts/com.neo.ngrok-monitor.plist \
        /Library/LaunchDaemons/

# 加载服务
sudo launchctl load /Library/LaunchDaemons/com.neo.ngrok-monitor.plist

# 启动服务
sudo launchctl start com.neo.ngrok-monitor

# 查看状态
sudo launchctl list | grep ngrok-monitor
```

---

## 使用方法

### 使用启动脚本 (推荐)

```bash
cd /Users/mac/.openclaw/workspace-neo

# 启动监控
./scripts/ngrok-monitor.sh start

# 停止监控
./scripts/ngrok-monitor.sh stop

# 重启监控
./scripts/ngrok-monitor.sh restart

# 查看状态
./scripts/ngrok-monitor.sh status

# 查看实时日志
./scripts/ngrok-monitor.sh log

# 执行一次检查
./scripts/ngrok-monitor.sh check
```

### 直接使用 Python 脚本

```bash
cd /Users/mac/.openclaw/workspace-neo

# 启动监控
python3 scripts/monitor_ngrok.py

# 查看状态
python3 scripts/monitor_ngrok.py --status

# 重启所有服务
python3 scripts/monitor_ngrok.py --restart

# 执行一次检查
python3 scripts/monitor_ngrok.py --once
```

### 使用 nohup 后台运行

```bash
cd /Users/mac/.openclaw/workspace-neo
nohup python3 scripts/monitor_ngrok.py > logs/ngrok_monitor_nohup.log 2>&1 &
echo $! > /tmp/ngrok-monitor.pid
```

---

## 环境变量配置

可以在启动前设置环境变量来自定义配置：

```bash
export FLASK_PORT=5004              # Flask 端口
export NGROK_DOMAIN=chariest-nancy-nonincidentally.ngrok-free.dev  # ngrok 域名
export CHECK_INTERVAL=60            # 检查间隔(秒)
export MAX_RETRIES=3                # 最大重试次数
export FLASK_STARTUP_WAIT=5         # Flask 启动等待时间
export NGROK_STARTUP_WAIT=3         # ngrok 启动等待时间
```

---

## 日志文件

### 监控日志
- **位置**: `logs/ngrok_monitor.log`
- **内容**: 详细运行日志，包含每次检查结果和自动恢复操作

### 告警事件
- **位置**: `alerts/ngrok_YYYY-MM-DD.json`
- **格式**: JSON 数组，每个元素是一个告警事件
- **示例**:
```json
[
  {
    "timestamp": "2026-03-19T10:30:00",
    "level": "ERROR",
    "error_code": "ERR_NGROK_3200",
    "message": "ngrok 离线",
    "service": "ngrok",
    "action_taken": "重启 ngrok",
    "resolved": false
  }
]
```

### launchd 日志
- **位置**: `logs/ngrok_monitor_launchd.log` 和 `logs/ngrok_monitor_launchd_error.log`
- **内容**: launchd 启动和错误输出

---

## 监控指标

### 服务状态检查

1. **ngrok 进程检查** - 确认 ngrok 进程存在
2. **ngrok API 检查** - 调用 `localhost:4040/api/tunnels`
3. **隧道激活检查** - 确认隧道已建立
4. **Flask 进程检查** - 确认 Flask 进程存在
5. **Flask 端口检查** - 确认端口 5004 开放
6. **Flask 健康检查** - 调用 `/api/health` 端点

### 自动恢复策略

| 检测问题 | 恢复动作 | 延迟 |
|---------|---------|------|
| Flask 健康检查失败 | 重启 Flask → 如 ngrok 也失败则重启 ngrok | 2s |
| ngrok ERR_NGROK_3200/334 | 重启 ngrok | 2s |
| ngrok 进程不存在 | 重启 ngrok | 0s |
| 多个问题同时存在 | 重启所有服务 (Flask + ngrok) | 3s |

---

## 故障排查

### 检查服务状态

```bash
./scripts/ngrok-monitor.sh status
```

### 查看详细日志

```bash
# 查看最后 100 行日志
tail -n 100 logs/ngrok_monitor.log

# 实时查看日志
./scripts/ngrok-monitor.sh log
```

### 手动重启服务

```bash
# 停止当前监控
./scripts/ngrok-monitor.sh stop

# 手动重启 Flask 和 ngrok
python3 scripts/monitor_ngrok.py --restart

# 重新启动监控
./scripts/ngrok-monitor.sh start
```

### 常见问题

#### Q: ngrok 启动失败，提示端口被占
**A**: 检查是否有其他 ngrok 实例在运行：
```bash
ps aux | grep ngrok
killall ngrok
```

#### Q: Flask 启动失败
**A**: 检查 Flask 端口是否被占：
```bash
lsof -i :5004
```

#### Q: 告警文件过大
**A**: 清理旧告警文件：
```bash
find alerts -name "ngrok_*.json" -mtime +7 -delete
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    监控系统                          │
│  ┌──────────────┐  ┌──────────────┐               │
│  │  状态检查     │  │  自动恢复     │               │
│  │  • ngrok     │  │  • 重启服务   │               │
│  │  • Flask     │  │  • 记录告警   │               │
│  └──────────────┘  └──────────────┘               │
│           │                 │                       │
│           ▼                 ▼                       │
│  ┌─────────────────────────────────┐              │
│  │         日志 & 告警              │              │
│  │  logs/ngrok_monitor.log         │              │
│  │  alerts/ngrok_YYYY-MM-DD.json   │              │
│  └─────────────────────────────────┘              │
└─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
   │   ngrok     │ │    Flask    │ │   Dashboard  │
   │   :4040     │ │   :5004     │ │   Web UI     │
   └─────────────┘ └─────────────┘ └──────────────┘
```

---

## 维护检查清单

- [ ] 每周检查 `logs/ngrok_monitor.log` 是否有异常
- [ ] 每周清理 `alerts/` 目录中过期的 JSON 文件
- [ ] 每月验证自动恢复功能（手动停止服务测试）
- [ ] 监控磁盘空间，避免日志过大

---

## 联系

如有问题，请联系 SRE 团队或查看 AGENTS.md 中的值班信息。

---

*文档版本: 1.0*  
*最后更新: 2026-03-19*  
*作者: SRE Agent*
