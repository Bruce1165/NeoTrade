"""
Strategy Backtest - 主运行脚本
运行策略回测，支持训练/验证模式
"""
import argparse
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo')

from strategy_config import CURRENT_CONFIG, StrategyConfig
from backtest_engine import BacktestEngine


def run_training_backtest(config: StrategyConfig, save_results: bool = True) -> dict:
    """运行训练集回测"""
    print("=" * 60)
    print("NeoTrade 策略回测系统")
    print("=" * 60)
    print(f"模式: 训练集回测")
    print(f"数据范围: 2024-09-02 到 2025-08-31 (T-18到T-7个月)")
    print(f"数据屏蔽: 2025-09-01 之后完全不可见")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestEngine(config, train_end_date="2025-08-31")
    
    # 运行回测
    metrics = engine.run_backtest(
        start_date="2024-09-02",
        end_date="2025-08-31"
    )
    
    # 打印结果
    print_results(metrics)
    
    # 保存结果
    if save_results:
        result = engine.save_results("backtest_result.json")
        
        # 同时更新 Dashboard
        try:
            from dashboard_tracker import DashboardTracker
            tracker = DashboardTracker()
            tracker.record_backtest_result(result)
            print("结果已同步到 Dashboard")
        except Exception as e:
            print(f"Dashboard 同步失败: {e}")
    
    return metrics


def run_validation_backtest(config: StrategyConfig) -> dict:
    """运行验证集回测（仅在最终验证时使用）"""
    print("=" * 60)
    print("NeoTrade 策略回测系统")
    print("=" * 60)
    print(f"模式: 验证集回测")
    print(f"⚠️  警告: 验证集仅在最终评估时使用")
    print(f"数据范围: 2025-09-01 到 2026-02-28 (T-6到T-0个月)")
    print("=" * 60)
    
    # 创建回测引擎
    engine = BacktestEngine(config, train_end_date="2026-02-28")
    
    # 运行回测
    metrics = engine.run_backtest(
        start_date="2025-09-01",
        end_date="2026-02-28"
    )
    
    # 打印结果
    print_results(metrics)
    
    return metrics


def print_results(metrics: dict):
    """打印回测结果"""
    print("\n" + "=" * 60)
    print("回测结果")
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


def main():
    parser = argparse.ArgumentParser(description='NeoTrade 策略回测系统')
    parser.add_argument('--mode', choices=['train', 'validate'], default='train',
                        help='回测模式: train=训练集, validate=验证集')
    parser.add_argument('--config', default='strategy_config.py',
                        help='配置文件路径')
    parser.add_argument('--save', action='store_true', default=True,
                        help='保存回测结果')
    
    args = parser.parse_args()
    
    # 加载配置
    if args.config != 'strategy_config.py':
        # 动态加载其他配置文件
        import importlib.util
        spec = importlib.util.spec_from_file_location("custom_config", args.config)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        config = config_module.CURRENT_CONFIG
    else:
        config = CURRENT_CONFIG
    
    # 运行回测
    if args.mode == 'train':
        metrics = run_training_backtest(config, save_results=args.save)
    else:
        metrics = run_validation_backtest(config)
    
    # 输出关键指标（供autoresearch提取）
    if 'sharpe_ratio' in metrics:
        print(f"\n[METRIC] sharpe_ratio={metrics['sharpe_ratio']:.6f}")
        print(f"[METRIC] total_return={metrics['total_return']:.6f}")
        print(f"[METRIC] max_drawdown={metrics['max_drawdown']:.6f}")
    
    return metrics


if __name__ == "__main__":
    main()
