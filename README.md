# Neo量化研究体系 - AKShare数据抓取框架

## 项目结构

```
workspace-neo/
├── config/
│   └── .env                    # 配置文件
├── data/
│   ├── raw/                    # 原始数据
│   ├── processed/              # 处理后数据
│   ├── emotion/                # 情绪分析结果
│   └── reports/                # 每日复盘报告
├── scripts/
│   ├── akshare_fetcher.py      # 基础数据获取 (AKShare)
│   ├── emotion_analyzer.py     # 情绪周期分析
│   ├── sector_analyzer.py      # 板块分析
│   └── daily_review.py         # 每日复盘主程序
├── logs/
│   └── *.log                   # 日志文件
└── README.md                   # 本文件
```

## 安装依赖

```bash
pip install akshare pandas numpy python-dotenv
```

## 特点

- ✅ **完全免费** - 无需注册，无需积分
- ✅ **数据实时** - 东方财富实时行情
- ✅ **A股全覆盖** - 全部A股数据
- ⚠️ **部分限制** - 历史数据获取有限，部分指标需计算

## 快速开始

### 1. 安装依赖

```bash
pip install akshare pandas numpy
```

### 2. 测试连接

```bash
cd /Users/mac/.openclaw/workspace-neo/scripts
python akshare_fetcher.py
```

### 3. 运行每日复盘

```bash
# 运行最新交易日的复盘
python daily_review.py

# 运行指定日期的复盘（仅支持当日）
python daily_review.py 20250311
```

## 数据说明

### 情绪四要素

| 要素 | 说明 | 数据来源 | 备注 |
|------|------|----------|------|
| 涨停数量 | 当日涨停股票数 | `stock_zt_pool_em()` | ✅ 直接获取 |
| 溢价率 | 昨日涨停股今日收益 | 计算得出 | ⚠️ 简化处理 |
| 连板数 | 2板及以上股票数 | `stock_zt_pool_em()` | ✅ 直接获取 |
| 空间高度 | 最高连板数 | `stock_zt_pool_em()` | ✅ 直接获取 |

### 板块分析

| 分析项 | 说明 | 数据来源 | 备注 |
|--------|------|----------|------|
| 涨幅分布 | 涨幅前400的分布统计 | `stock_zh_a_spot_em()` | ✅ 支持 |
| 板块表现 | 指定板块的成分股表现 | `stock_board_industry_cons_em()` | ✅ 支持 |
| 板块拥挤度 | 成交额集中度 | `stock_zh_a_spot_em()` | ⚠️ 按市值区间 |
| 放量个股 | 量比>3的个股 | `stock_zh_a_spot_em()` | ✅ 支持 |

## AKShare vs Tushare 对比

| 功能 | AKShare | Tushare |
|------|---------|---------|
| 费用 | 免费 | 积分制 |
| 注册 | 不需要 | 需要 |
| 实时行情 | ✅ | ✅ |
| 历史数据 | ⚠️ 有限 | ✅ 完整 |
| 涨停数据 | ✅ | ✅ |
| 板块数据 | ✅ | ✅ |
| 稳定性 | ⚠️ 一般 | ✅ 稳定 |
| 文档 | 中文 | 中文 |

## 使用说明

### 单独运行模块

```bash
# 情绪分析
python emotion_analyzer.py

# 板块分析
python sector_analyzer.py

# 基础数据获取测试
python akshare_fetcher.py
```

### 获取板块数据

```python
from akshare_fetcher import AKShareDataFetcher

fetcher = AKShareDataFetcher()

# 获取行业板块成分股
stocks = fetcher.get_sector_stocks('半导体', sector_type='industry')

# 获取概念板块成分股
stocks = fetcher.get_sector_stocks('人工智能', sector_type='concept')
```

## 定时任务设置

### 使用 cron（Mac/Linux）

```bash
# 编辑 crontab
crontab -e

# 添加每日15:30自动运行复盘（收盘后）
30 15 * * 1-5 cd /Users/mac/.openclaw/workspace-neo/scripts && python daily_review.py >> /Users/mac/.openclaw/workspace-neo/logs/cron.log 2>&1
```

### 使用 launchd（Mac推荐）

创建 `~/Library/LaunchAgents/com.neo.dailyreview.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo.dailyreview</string>
    <key>ProgramArguments</key>
    <array>
        <string>python</string>
        <string>/Users/mac/.openclaw/workspace-neo/scripts/daily_review.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>15</integer>
        <key>Minute</key>
        <integer>30</integer>
        <key>Weekday</key>
        <integer>1</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/mac/.openclaw/workspace-neo/logs/cron_error.log</string>
</dict>
</plist>
```

加载任务：
```bash
launchctl load ~/Library/LaunchAgents/com.neo.dailyreview.plist
```

## 常见问题

### Q: AKShare 安装失败
A: 尝试使用 `pip install akshare --upgrade` 更新到最新版本。

### Q: 数据获取超时
A: AKShare 偶尔会有网络延迟，可以重试或检查网络连接。

### Q: 历史数据如何获取
A: AKShare 的实时接口不支持历史日期查询。如需历史数据，需要使用 `stock_zh_a_hist()` 接口获取单只股票历史。

### Q: 板块数据不准确
A: AKShare 的板块分类来自东方财富/同花顺，可能与你的分类标准有差异，建议自行维护板块映射表。

## 后续优化

- [ ] 添加更多技术指标计算
- [ ] 实现历史数据回测（使用 stock_zh_a_hist）
- [ ] 添加可视化图表
- [ ] 实现板块映射表自定义
- [ ] 添加数据缓存机制
- [ ] 添加邮件/微信通知

---

*框架版本：v1.0 (AKShare版)*  
*创建日期：2026-03-11*
