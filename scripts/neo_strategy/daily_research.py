#!/usr/bin/env python3
"""
NeoTrade Strategy Daily Research Task
Runs parameter evolution and backtest for neo_trend_momentum_v1
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import from auto_research
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "auto_research"))
import backtest_engine
import parameter_evolution
from parameter_evolution import ParameterEvolution, ParameterSpace

# Import neo_strategy backtest
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "neo_strategy"))
import backtest
from backtest import NeoStrategyBacktest, StrategyParams

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs" / "strategy_research"
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = LOG_DIR
REPORT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"daily_research_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define parameter space for neo_trend_momentum_v1
NEO_STRATEGY_PARAM_SPACES = [
    ParameterSpace('trend_ma_long', 'int', 150, 250, default=200),
    ParameterSpace('trend_ma_medium', 'int', 30, 60, default=50),
    ParameterSpace('entry_ma_short', 'int', 5, 20, default=10),
    ParameterSpace('rs_lookback', 'int', 10, 30, default=20),
    ParameterSpace('rs_threshold', 'int', 70, 90, default=75),
    ParameterSpace('pullback_pct', 'float', 3.0, 8.0, step=0.5, default=5.0),
    ParameterSpace('volatility_atr_threshold', 'float', 3.0, 8.0, step=0.5, default=5.0),
    ParameterSpace('stop_loss', 'float', 5.0, 12.0, step=0.5, default=8.0),
    ParameterSpace('take_profit', 'float', 15.0, 30.0, step=1.0, default=20.0),
    ParameterSpace('max_hold_days', 'int', 10, 25, default=15),
    ParameterSpace('max_positions', 'int', 3, 8, default=5),
    ParameterSpace('position_size', 'float', 1500, 2500, step=100, default=2000),
]

# Target metrics
TARGETS = {
    'win_rate': 0.65,  # 65%
    'annual_return': 0.50,  # 50%
    'max_drawdown': 0.10,  # 10%
}


def load_current_config() -> Dict[str, Any]:
    """Load current strategy config"""
    config_path = PROJECT_ROOT / "scripts" / "neo_strategy" / "strategy_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def save_config(config: Dict[str, Any]):
    """Save strategy config"""
    config_path = PROJECT_ROOT / "scripts" / "neo_strategy" / "strategy_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    logger.info(f"Config saved to {config_path}")


def run_parameter_evolution() -> tuple:
    """
    Run genetic algorithm optimization
    Returns: (best_params, best_metrics)
    """
    logger.info("=" * 60)
    logger.info("STARTING PARAMETER EVOLUTION")
    logger.info("=" * 60)
    
    evolution = ParameterEvolution(
        param_spaces=NEO_STRATEGY_PARAM_SPACES,
        population_size=8,  # Smaller for faster daily runs
        elite_ratio=0.25,
        mutation_rate=0.3,
        crossover_rate=0.5,
        max_generations=5,  # Limited generations for daily task
        early_stop_patience=3,
        target_sharpe=1.5
    )
    
    # Initialize population
    population = evolution.initialize_population()
    logger.info(f"Initialized population of {len(population)}")
    
    generation_results = []
    
    for gen in range(evolution.max_generations):
        logger.info(f"\n--- Generation {gen + 1} ---")
        
        fitness_scores = []
        
        for i, params in enumerate(population):
            logger.info(f"Testing individual {i+1}/{len(population)}")
            
            # Create StrategyParams from dict
            valid_fields = {f for f in StrategyParams.__dataclass_fields__}
            filtered_params = {k: v for k, v in params.items() if k in valid_fields}
            strategy_params = StrategyParams(**filtered_params)
            
            # Run backtest
            try:
                backtest = NeoStrategyBacktest(strategy_params)
                with backtest:
                    result, trades = backtest.run_backtest(
                        start_date="2024-09-02",
                        end_date="2025-08-31",
                        initial_capital=10000.0
                    )
                
                # Fitness = Sharpe ratio (can be customized)
                fitness = result.sharpe_ratio
                fitness_scores.append(fitness)
                
                logger.info(f"  Sharpe: {result.sharpe_ratio:.3f}, Win Rate: {result.win_rate*100:.1f}%, Return: {result.total_return*100:.2f}%")
                
            except Exception as e:
                logger.error(f"Backtest failed: {e}")
                fitness_scores.append(-2.0)  # Penalty for failure
        
        # Evolve to next generation
        population, gen_info = evolution.evolve_one_step(population, fitness_scores)
        generation_results.append(gen_info)
        
        logger.info(f"Best Sharpe so far: {evolution.best_sharpe:.3f}")
        
        if gen_info['should_stop']:
            logger.info(f"Stopping early: {evolution.patience_counter} generations without improvement")
            break
    
    logger.info("\n" + "=" * 60)
    logger.info("EVOLUTION COMPLETE")
    logger.info("=" * 60)
    
    return evolution.best_params, {
        'best_sharpe': evolution.best_sharpe,
        'generations': evolution.generation,
        'history': generation_results
    }


def run_optimized_backtest(params: Dict[str, Any]) -> tuple:
    """
    Run backtest with optimized parameters
    Returns: (result, trades)
    """
    logger.info("\n" + "=" * 60)
    logger.info("RUNNING BACKTEST WITH OPTIMIZED PARAMETERS")
    logger.info("=" * 60)
    
    valid_fields = {f for f in StrategyParams.__dataclass_fields__}
    filtered_params = {k: v for k, v in params.items() if k in valid_fields}
    strategy_params = StrategyParams(**filtered_params)
    
    backtest = NeoStrategyBacktest(strategy_params)
    with backtest:
        result, trades = backtest.run_backtest(
            start_date="2024-09-02",
            end_date="2025-08-31",
            initial_capital=10000.0
        )
    
    return result, trades


def analyze_performance(result) -> Dict[str, Any]:
    """
    Analyze backtest performance vs targets
    """
    # Calculate annual return from total return
    trading_days = 252  # Approximate
    years = 1.0  # Simplified for this period
    annual_return = ((1 + result.total_return) ** (1/years) - 1) if result.total_return > -1 else 0
    
    analysis = {
        'total_return': result.total_return * 100,
        'annual_return': annual_return * 100,
        'sharpe_ratio': result.sharpe_ratio,
        'win_rate': result.win_rate * 100,
        'max_drawdown': result.max_drawdown * 100,
        'total_trades': result.total_trades,
        'profit_factor': result.profit_factor,
        'avg_trade_return': result.avg_trade_return,
        'avg_hold_days': result.avg_hold_days,
        'targets': {
            'win_rate_target': TARGETS['win_rate'] * 100,
            'annual_return_target': TARGETS['annual_return'] * 100,
            'max_drawdown_limit': TARGETS['max_drawdown'] * 100,
        },
        'vs_targets': {
            'win_rate_met': result.win_rate >= TARGETS['win_rate'],
            'return_met': annual_return >= TARGETS['annual_return'],
            'drawdown_ok': result.max_drawdown <= TARGETS['max_drawdown'],
        }
    }
    
    return analysis


def generate_report(analysis: Dict[str, Any], params: Dict[str, Any]) -> str:
    """
    Generate daily research report
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_str = datetime.now().strftime('%Y%m%d')
    
    report = f"""
================================================================================
NeoTrade Strategy Research Daily Report
Generated: {timestamp}
Strategy: neo_trend_momentum_v1
================================================================================

PERFORMANCE METRICS
-------------------
Total Return:        {analysis['total_return']:>8.2f}%
Annual Return:       {analysis['annual_return']:>8.2f}%
Sharpe Ratio:        {analysis['sharpe_ratio']:>8.3f}
Win Rate:            {analysis['win_rate']:>8.1f}%
Max Drawdown:        {analysis['max_drawdown']:>8.2f}%
Total Trades:        {analysis['total_trades']:>8}
Profit Factor:       {analysis['profit_factor']:>8.2f}
Avg Trade Return:    {analysis['avg_trade_return']:>8.2f}%
Avg Hold Days:       {analysis['avg_hold_days']:>8.1f}

TARGETS vs ACTUAL
-----------------
Metric          Target      Actual      Status
------          ------      ------      ------
Win Rate        {analysis['targets']['win_rate_target']:>6.1f}%     {analysis['win_rate']:>6.1f}%     {'✓ PASS' if analysis['vs_targets']['win_rate_met'] else '✗ FAIL'}
Annual Return   {analysis['targets']['annual_return_target']:>6.1f}%     {analysis['annual_return']:>6.1f}%     {'✓ PASS' if analysis['vs_targets']['return_met'] else '✗ FAIL'}
Max Drawdown    <{analysis['targets']['max_drawdown_limit']:>6.1f}%     {analysis['max_drawdown']:>6.2f}%     {'✓ PASS' if analysis['vs_targets']['drawdown_ok'] else '✗ FAIL'}

OPTIMIZED PARAMETERS
--------------------
"""
    
    for key, value in sorted(params.items()):
        report += f"{key:.<25} {value}\n"
    
    # Overall assessment
    all_targets_met = all([
        analysis['vs_targets']['win_rate_met'],
        analysis['vs_targets']['return_met'],
        analysis['vs_targets']['drawdown_ok']
    ])
    
    report += f"""
OVERALL ASSESSMENT
------------------
All Targets Met: {'YES - Strategy ready for live trading!' if all_targets_met else 'NO - Further optimization needed'}

"""
    
    if all_targets_met:
        report += "🎉 TARGET METRICS ACHIEVED! Notify main agent for deployment consideration.\n"
    else:
        report += "⚠️  Targets not yet met. Continue parameter evolution in next cycle.\n"
        report += "\nRecommendations:\n"
        if not analysis['vs_targets']['win_rate_met']:
            report += "  - Consider tightening entry criteria to improve win rate\n"
        if not analysis['vs_targets']['return_met']:
            report += "  - May need to increase position size or adjust profit targets\n"
    
    report += "\n" + "=" * 80 + "\n"
    
    # Save report
    report_path = REPORT_DIR / f"daily_report_{date_str}.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    
    logger.info(f"Report saved to {report_path}")
    
    return report


def update_strategy_config(params: Dict[str, Any]):
    """
    Update strategy_config.json with optimized parameters
    """
    config = load_current_config()
    config['parameters'] = params
    config['last_optimized'] = datetime.now().isoformat()
    save_config(config)


def main():
    """
    Main daily research task
    """
    logger.info("=" * 60)
    logger.info("NeoTrade Daily Strategy Research Task")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Step 1 & 2: Run parameter evolution (includes backtesting)
    best_params, evolution_metrics = run_parameter_evolution()
    
    if not best_params:
        logger.error("Parameter evolution failed to produce valid parameters")
        return
    
    # Step 3: Run final backtest with best parameters
    result, trades = run_optimized_backtest(best_params)
    
    # Step 4: Analyze performance
    analysis = analyze_performance(result)
    
    # Step 5: Update config
    update_strategy_config(best_params)
    
    # Step 6: Generate report
    report = generate_report(analysis, best_params)
    
    # Step 7: Print report to stdout
    print("\n" + report)
    
    # Check if targets met for notification
    all_targets_met = all([
        analysis['vs_targets']['win_rate_met'],
        analysis['vs_targets']['return_met'],
        analysis['vs_targets']['drawdown_ok']
    ])
    
    if all_targets_met:
        print("\n" + "=" * 60)
        print("🎉 NOTIFICATION: TARGET METRICS ACHIEVED!")
        print("=" * 60)
        print(f"Win Rate: {analysis['win_rate']:.1f}% (target: {TARGETS['win_rate']*100:.0f}%)")
        print(f"Annual Return: {analysis['annual_return']:.1f}% (target: {TARGETS['annual_return']*100:.0f}%)")
        print(f"Max Drawdown: {analysis['max_drawdown']:.2f}% (limit: {TARGETS['max_drawdown']*100:.0f}%)")
        print("\nRecommend reviewing strategy for live deployment.")
        print("=" * 60)
    
    logger.info("Daily research task complete")
    return analysis, best_params


if __name__ == '__main__':
    main()
