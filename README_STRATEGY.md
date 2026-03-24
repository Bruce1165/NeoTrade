# NeoTrade 自主交易策略研究项目

## 项目结构

```
autoresearch/
├── strategy_config.py          # 策略参数配置（种子策略）
├── signal_generator.py         # 信号生成逻辑
├── backtest_engine.py          # 回测引擎核心
├── position_sizer.py           # 仓位管理模块
├── strategy_backtest.py        # 主运行脚本（CLI）
├── dashboard_tracker.py        # Dashboard 结果追踪
├── run_baseline.py             # 基线回测脚本
├── launch_autoresearch.py      # Autoresearch 启动器
└── autoresearch.config.md      # Autoresearch 配置文件
```

## 核心约束

1. **数据分割**（严格屏蔽未来数据）
   - 训练集: 2024-09-02 到 2025-08-31 (T-18到T-7个月)
   - 验证集: 2025-09-01 之后完全屏蔽

2. **资金管理**
   - 初始资金: 10,000元（固定）
   - 单股最大仓位: 30%
   - 最大持仓数: 5只
   - 每日最大交易: 3次

3. **风控规则**
   - 硬性止损: -7%（可优化）
   - 移动止盈: 15%（可优化）
   - 最大回撤限制: -15%

4. **交易费用**
   - 佣金: 0.03%（最低5元）
   - 印花税: 0.1%（卖出时）

## 种子策略（多因子动量）

1. **趋势因子**: 股价 > MA20 > MA50（多头排列）
2. **动量因子**: 20日涨幅在10%-30%之间
3. **量能因子**: 当日成交量 > 5日均量1.5倍
4. **波动因子**: ATR(14) < 股价5%

## 使用方法

### 1. 运行基线回测
```bash
python run_baseline.py
```

### 2. 运行策略回测（训练模式）
```bash
python strategy_backtest.py --mode train
```

### 3. 启动 Autoresearch 优化
```bash
# 运行20代优化
python launch_autoresearch.py --generations 20

# 仅运行基线
python launch_autoresearch.py --baseline-only
```

## 性能指标

- **主要指标**: 夏普比率 (Sharpe Ratio)
- **次要指标**: 
  - 总收益率 (Total Return)
  - 最大回撤 (Max Drawdown)
  - 胜率 (Win Rate)
  - 盈亏比 (Profit Factor)
  - 止损触发率

## 实验追踪

所有回测结果自动记录到 Dashboard 数据库:
- `strategy_backtest_results` - 回测结果主表
- `strategy_trades` - 交易记录
- `strategy_daily_values` - 每日净值
- `strategy_experiments` - 实验追踪

## 注意事项

1. **严格禁止查看验证集数据** (2025-09-01之后)
2. **不允许修改历史价格数据**
3. **每次实验只调整一个参数**
4. **优先简化策略，去除无效因子**
5. **止损纪律 > 收益追求**

## 文件说明

### signal_generator.py
- `SignalGenerator` 类：基于多因子生成买卖信号
- 支持趋势、动量、量能、波动四个因子
- 自动计算MA、ATR、动量等技术指标

### backtest_engine.py
- `BacktestEngine` 类：核心回测引擎
- 严格屏蔽2025-09-01之后数据
- 逐日模拟交易执行
- 计算夏普比率等性能指标

### position_sizer.py
- `PositionSizer` 类：仓位管理
- 基于信号强度调整仓位
- 支持A股100股最小交易单位
- 自动计算交易费用

### dashboard_tracker.py
- `DashboardTracker` 类：结果记录
- 自动创建必要的表结构
- 记录回测结果和交易明细
- 追踪实验历史

## 下一步

1. ✓ 完成策略回测框架搭建
2. ✓ 创建所有核心模块
3. ✓ 配置 autoresearch
4. ⏳ 运行基线回测
5. ⏳ 启动 autoresearch 迭代优化
