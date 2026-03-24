# Autoresearch Configuration - NeoTrade Strategy Evolution

## Goal
构建并优化短线+中线交易策略，在12个月历史数据上训练，追求：
1. 最大化风险调整后收益（夏普比率）
2. 增强止损能力（控制最大回撤）
3. 提升胜率与盈亏比

## Metric
- **Primary Metric**: Sharpe Ratio (年化收益率 / 年化波动率)
- **Secondary Metrics**: 
  - 总收益率 (Total Return %)
  - 最大回撤 (Max Drawdown %, 越低越好)
  - 胜率 (Win Rate %)
  - 盈亏比 (Profit Factor)
  - 止损触发率 (Stop Loss Rate, 反映纪律性)
- **Direction**: higher Sharpe is better
- **Baseline**: 买入持有基准 (Buy & Hold Benchmark)

## Target Files
- strategy_config.py - 策略参数配置（入场条件、止损止盈、持仓周期）
- signal_generator.py - 信号生成逻辑
- backtest_engine.py - 回测引擎核心
- position_sizer.py - 仓位管理模块
- dashboard_updater.py - 结果记录到 Dashboard

## Read-Only Files
- data/stock_data.db - 数据库（严格禁止修改）
- scripts/base_screener.py - 基础筛选器框架（参考用）

## Run Command
```
python strategy_backtest.py --mode train --config strategy_config.py
```

## Extract Command
```
python -c "import json; d=json.load(open('backtest_result.json')); print(d['sharpe_ratio'])"
```

## Time Budget
- **Per experiment**: 2 minutes（单策略回测）
- **Kill timeout**: 5 minutes

## Constraints
1. **NO FUTURE DATA**: 严格使用T-18到T-7月数据，T-6月之后数据完全屏蔽
2. **初始资金**: 固定10,000元，不得更改
3. **单股最大仓位**: 不超过总资金30%
4. **强制止损**: 必须设置硬性止损（初始-7%，可优化）
5. **持仓周期**: 短线1-5天，中线最多20天，超时强制平仓
6. **交易费用**: 佣金0.03%，印花税0.1%（卖出），必须计入
7. **不允许修改**: 数据库、历史价格数据、交易日期

## Branch
autoresearch/strategy-v1

## Data Split
- **Training**: 2024-09-02 to 2025-08-31 (T-18 to T-7 months)
- **Validation**: 2025-09-01 to 2026-02-28 (T-6 to T-0, LOCKED - do not peek)
- **Test**: 2026-03-01 onwards (for future paper trading)

## Strategy Seed (Initial Hypothesis)
多因子动量策略：
1. 趋势因子：股价 > MA20 > MA50（多头排列）
2. 动量因子：20日涨幅在10%-30%之间（避免追高风险）
3. 量能因子：当日成交量 > 5日均量1.5倍（放量确认）
4. 波动因子：ATR(14) < 股价5%（控制波动）
5. 止损：-7%硬性止损，+15%移动止盈

## Experiment Notes
- 每次只调整一个参数或一个因子
- 记录每次实验的假设、结果、教训
- 优先简化策略，去除无效因子
- 止损纪律 > 收益追求
