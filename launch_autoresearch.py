#!/usr/bin/env python3
"""
Autoresearch Launcher - 启动策略迭代优化

使用方法:
1. 直接运行: python launch_autoresearch.py
2. 指定代数: python launch_autoresearch.py --generations 10
"""
import argparse
import json
import subprocess
import sys
import os
from datetime import datetime

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo')

from strategy_config import CURRENT_CONFIG, StrategyConfig, CONFIG_HISTORY
from backtest_engine import BacktestEngine
from dashboard_tracker import DashboardTracker


class StrategyOptimizer:
    """策略优化器 - Autoresearch 核心"""
    
    def __init__(self):
        self.config = CURRENT_CONFIG
        self.best_sharpe = float('-inf')
        self.best_config = None
        self.generation = 0
        self.tracker = DashboardTracker()
    
    def run_experiment(self, config: StrategyConfig, hypothesis: str) -> dict:
        """运行一次策略实验"""
        print(f"\n{'='*60}")
        print(f"实验 #{self.generation}")
        print(f"假设: {hypothesis}")
        print(f"{'='*60}")
        
        # 运行回测
        engine = BacktestEngine(config, train_end_date="2025-08-31")
        metrics = engine.run_backtest(
            start_date="2024-09-02",
            end_date="2025-08-31"
        )
        
        # 保存结果
        result = engine.save_results(f"backtest_gen_{self.generation}.json")
        
        # 记录到 Dashboard
        try:
            self.tracker.record_backtest_result(
                result, 
                strategy_version=f"gen_{self.generation}"
            )
        except Exception as e:
            print(f"Dashboard 记录失败: {e}")
        
        return metrics
    
    def mutate_config(self, base_config: StrategyConfig) -> tuple:
        """
        基于启发式规则生成新配置
        返回: (新配置, 变更说明, 假设)
        """
        import copy
        new_config = copy.deepcopy(base_config)
        
        # 策略变异规则
        import random
        mutation_type = random.choice([
            'stop_loss', 'trailing', 'momentum', 'volume', 'ma_period',
            'position_size', 'hold_days', 'signal_threshold'
        ])
        
        changes = {}
        hypothesis = ""
        
        if mutation_type == 'stop_loss':
            # 调整止损
            old_val = new_config.hard_stop_loss
            new_val = random.choice([-0.05, -0.06, -0.07, -0.08, -0.10])
            new_config.hard_stop_loss = new_val
            changes['hard_stop_loss'] = (old_val, new_val)
            hypothesis = f"调整硬性止损从{old_val:.0%}到{new_val:.0%}，测试对回撤控制的影响"
            
        elif mutation_type == 'trailing':
            # 调整移动止盈
            old_val = new_config.trailing_stop_pct
            new_val = random.choice([0.10, 0.12, 0.15, 0.18, 0.20])
            new_config.trailing_stop_pct = new_val
            changes['trailing_stop_pct'] = (old_val, new_val)
            hypothesis = f"调整移动止盈从{old_val:.0%}到{new_val:.0%}，测试锁定收益能力"
            
        elif mutation_type == 'momentum':
            # 调整动量参数
            old_min = new_config.momentum_min
            old_max = new_config.momentum_max
            new_config.momentum_min = random.uniform(0.05, 0.15)
            new_config.momentum_max = random.uniform(0.20, 0.40)
            changes['momentum_range'] = ((old_min, old_max), (new_config.momentum_min, new_config.momentum_max))
            hypothesis = "优化动量筛选范围，寻找最佳收益风险比"
            
        elif mutation_type == 'volume':
            # 调整量能因子
            old_val = new_config.volume_surge_ratio
            new_val = random.uniform(1.2, 2.0)
            new_config.volume_surge_ratio = new_val
            changes['volume_surge_ratio'] = (old_val, new_val)
            hypothesis = f"调整放量倍数从{old_val:.1f}到{new_val:.1f}，测试量能确认效果"
            
        elif mutation_type == 'ma_period':
            # 调整均线周期
            old_short = new_config.ma_short
            old_medium = new_config.ma_medium
            new_config.ma_short = random.choice([10, 15, 20, 25, 30])
            new_config.ma_medium = random.choice([40, 50, 60, 70])
            changes['ma_periods'] = ((old_short, old_medium), (new_config.ma_short, new_config.ma_medium))
            hypothesis = "优化均线周期，寻找更适合当前市场的趋势判断参数"
            
        elif mutation_type == 'position_size':
            # 调整仓位上限
            old_val = new_config.max_position_per_stock
            new_val = random.choice([0.20, 0.25, 0.30, 0.35, 0.40])
            new_config.max_position_per_stock = new_val
            changes['max_position_per_stock'] = (old_val, new_val)
            hypothesis = f"调整单股仓位上限从{old_val:.0%}到{new_val:.0%}，平衡集中与分散"
            
        elif mutation_type == 'hold_days':
            # 调整持仓周期
            old_short = new_config.max_hold_days_short
            old_medium = new_config.max_hold_days_medium
            new_config.max_hold_days_short = random.choice([3, 5, 7, 10])
            new_config.max_hold_days_medium = random.choice([15, 20, 25, 30])
            changes['hold_days'] = ((old_short, old_medium), (new_config.max_hold_days_short, new_config.max_hold_days_medium))
            hypothesis = "优化持仓周期，适应不同市场环境"
            
        elif mutation_type == 'signal_threshold':
            # 调整信号阈值
            old_val = new_config.min_signal_score
            new_val = random.uniform(0.5, 0.8)
            new_config.min_signal_score = new_val
            changes['min_signal_score'] = (old_val, new_val)
            hypothesis = f"调整信号阈值从{old_val:.2f}到{new_val:.2f}，平衡交易频率与质量"
        
        return new_config, changes, hypothesis
    
    def optimize(self, generations: int = 20):
        """运行优化循环"""
        print("=" * 60)
        print("NeoTrade Autoresearch - 策略迭代优化")
        print("=" * 60)
        print(f"目标: 最大化夏普比率")
        print(f"代数: {generations}")
        print(f"约束: 严格屏蔽2025-09-01之后数据")
        print("=" * 60)
        
        # 首先运行基线
        print("\n>>> 运行基线策略...")
        baseline_metrics = self.run_experiment(self.config, "种子策略基线")
        baseline_sharpe = baseline_metrics.get('sharpe_ratio', 0)
        
        self.best_sharpe = baseline_sharpe
        self.best_config = self.config
        
        print(f"\n基线夏普比率: {baseline_sharpe:.3f}")
        
        # 迭代优化
        for gen in range(1, generations + 1):
            self.generation = gen
            
            # 生成变异配置
            new_config, changes, hypothesis = self.mutate_config(self.best_config)
            
            # 运行实验
            metrics_before = {
                'sharpe_ratio': self.best_sharpe,
                'total_return': baseline_metrics.get('total_return', 0),
                'max_drawdown': baseline_metrics.get('max_drawdown', 0)
            }
            
            metrics = self.run_experiment(new_config, hypothesis)
            
            metrics_after = {
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'total_return': metrics.get('total_return', 0),
                'max_drawdown': metrics.get('max_drawdown', 0)
            }
            
            # 记录实验
            try:
                self.tracker.record_experiment(
                    hypothesis=hypothesis,
                    config_changes=changes,
                    metrics_before=metrics_before,
                    metrics_after=metrics_after
                )
            except Exception as e:
                print(f"实验记录失败: {e}")
            
            # 评估结果
            new_sharpe = metrics.get('sharpe_ratio', 0)
            
            if new_sharpe > self.best_sharpe:
                print(f"✓ 发现更优配置! Sharpe: {self.best_sharpe:.3f} -> {new_sharpe:.3f}")
                self.best_sharpe = new_sharpe
                self.best_config = new_config
                
                # 保存最佳配置
                self.save_best_config()
            else:
                print(f"✗ 未改善 Sharpe: {new_sharpe:.3f} (当前最佳: {self.best_sharpe:.3f})")
        
        # 输出最终结果
        print("\n" + "=" * 60)
        print("优化完成")
        print("=" * 60)
        print(f"最佳夏普比率: {self.best_sharpe:.3f}")
        print(f"相对基线提升: {(self.best_sharpe - baseline_sharpe):.3f}")
        
        # 获取最佳结果摘要
        try:
            best_results = self.tracker.get_best_result(5)
            print("\n【Top 5 配置】")
            for i, r in enumerate(best_results, 1):
                print(f"  {i}. {r['version']}: Sharpe={r['sharpe_ratio']:.3f}, Return={r['total_return']:.2%}")
        except Exception as e:
            print(f"获取最佳结果失败: {e}")
        
        return self.best_config
    
    def save_best_config(self):
        """保存最佳配置"""
        config_code = f'''"""
Optimized Strategy Configuration - 优化后的策略配置
Generated by Autoresearch at {datetime.now().isoformat()}
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class StrategyConfig:
    """优化后的策略配置"""
    
    # === 基础参数 ===
    initial_capital: float = 10000.0
    max_position_per_stock: float = {self.best_config.max_position_per_stock}
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    
    # === 持仓周期 ===
    min_hold_days: int = 1
    max_hold_days_short: int = {self.best_config.max_hold_days_short}
    max_hold_days_medium: int = {self.best_config.max_hold_days_medium}
    
    # === 止损止盈 ===
    hard_stop_loss: float = {self.best_config.hard_stop_loss}
    trailing_stop: bool = {self.best_config.trailing_stop}
    trailing_stop_pct: float = {self.best_config.trailing_stop_pct}
    profit_target: Optional[float] = 0.20
    
    # === 趋势因子 ===
    use_ma_trend: bool = {self.best_config.use_ma_trend}
    ma_short: int = {self.best_config.ma_short}
    ma_medium: int = {self.best_config.ma_medium}
    require_ma_bullish: bool = {self.best_config.require_ma_bullish}
    
    # === 动量因子 ===
    use_momentum: bool = {self.best_config.use_momentum}
    momentum_lookback: int = 20
    momentum_min: float = {self.best_config.momentum_min}
    momentum_max: float = {self.best_config.momentum_max}
    
    # === 量能因子 ===
    use_volume: bool = {self.best_config.use_volume}
    volume_ma_period: int = 5
    volume_surge_ratio: float = {self.best_config.volume_surge_ratio}
    
    # === 波动因子 ===
    use_volatility: bool = {self.best_config.use_volatility}
    atr_period: int = 14
    max_atr_pct: float = {self.best_config.max_atr_pct}
    
    # === 风控参数 ===
    max_positions: int = {self.best_config.max_positions}
    max_daily_trades: int = {self.best_config.max_daily_trades}
    max_drawdown_limit: float = -0.15
    
    # === 信号强度 ===
    min_signal_score: float = {self.best_config.min_signal_score}

CURRENT_CONFIG = StrategyConfig()
'''
        
        with open('optimized_strategy_config.py', 'w') as f:
            f.write(config_code)
        
        print(f"  最佳配置已保存: optimized_strategy_config.py")


def main():
    parser = argparse.ArgumentParser(description='启动策略自动优化')
    parser.add_argument('--generations', type=int, default=20,
                        help='优化代数 (默认: 20)')
    parser.add_argument('--baseline-only', action='store_true',
                        help='仅运行基线回测')
    
    args = parser.parse_args()
    
    if args.baseline_only:
        # 仅运行基线
        print("仅运行基线回测...")
        from run_baseline import main as baseline_main
        baseline_main()
    else:
        # 运行完整优化
        optimizer = StrategyOptimizer()
        optimizer.optimize(generations=args.generations)


if __name__ == "__main__":
    main()
