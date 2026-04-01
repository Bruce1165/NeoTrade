#!/usr/bin/env python3
"""
运行基线回测 - 种子策略
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo')

from strategy_config import CURRENT_CONFIG
from backtest_engine import BacktestEngine

def main():
    print("=" * 60)
    print("NeoTrade 基线回测 - 种子策略")
    print("=" * 60)
    
    # 使用种子配置运行
    config = CURRENT_CONFIG
    engine = BacktestEngine(config, train_end_date="2025-08-31")
    
    # 运行训练集回测
    metrics = engine.run_backtest(
        start_date="2024-09-02",
        end_date="2025-08-31"
    )
    
    # 打印结果
    print("\n" + "=" * 60)
    print("基线回测结果")
    print("=" * 60)
    
    if 'error' in metrics:
        print(f"错误: {metrics['error']}")
        return
    
    print(f"\n【收益指标】")
    print(f"  初始资金:     ¥{metrics['initial_value']:,.2f}")
    print(f"  最终资金:     ¥{metrics['final_value']:,.2f}")
    print(f"  总收益率:     {metrics['total_return']:.2%}")
    print(f"  年化收益率:   {metrics['annualized_return']:.2%}")
    
    print(f"\n【风险指标】")
    print(f"  年化波动率:   {metrics['volatility']:.2%}")
    print(f"  最大回撤:     {metrics['max_drawdown']:.2%}")
    
    print(f"\n【综合评价】")
    print(f"  夏普比率:     {metrics['sharpe_ratio']:.3f}")
    
    print(f"\n【交易统计】")
    print(f"  总交易次数:   {metrics['total_trades']}")
    print(f"  胜率:         {metrics['win_rate']:.1%}")
    print(f"  盈亏比:       {metrics['profit_loss_ratio']:.2f}")
    print(f"  盈亏因子:     {metrics['profit_factor']:.2f}")
    print(f"  止损触发率:   {metrics['stop_loss_rate']:.1%}")
    
    if metrics['total_trades'] > 0:
        print(f"\n【单笔统计】")
        print(f"  平均盈利:     {metrics['avg_win']:.2%}")
        print(f"  平均亏损:     {metrics['avg_loss']:.2%}")
    
    print(f"\n【时间统计】")
    print(f"  交易日:       {metrics['trading_days']}天")
    print(f"  回测年数:     {metrics['years']:.2f}年")
    
    print("=" * 60)
    
    # 保存结果
    result = engine.save_results("backtest_result.json")
    
    # 输出关键指标（供autoresearch提取）
    print(f"\n[METRIC] sharpe_ratio={metrics['sharpe_ratio']:.6f}")
    print(f"[METRIC] total_return={metrics['total_return']:.6f}")
    print(f"[METRIC] max_drawdown={metrics['max_drawdown']:.6f}")
    
    # 尝试同步到 Dashboard
    try:
        from dashboard_tracker import DashboardTracker
        tracker = DashboardTracker()
        tracker.record_backtest_result(result, strategy_version="baseline_v0.1")
        print("\n✓ 结果已同步到 Dashboard")
    except Exception as e:
        print(f"\n! Dashboard 同步失败: {e}")
    
    return metrics

if __name__ == "__main__":
    main()
