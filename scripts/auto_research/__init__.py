"""
Auto Research Lab - AI-Driven Strategy Evolution

Components:
- backtest_engine: Historical simulation engine
- parameter_evolution: Genetic algorithm parameter optimization
- experiment_runner: Main orchestrator

Usage:
    from scripts.auto_research import ExperimentRunner
    
    runner = ExperimentRunner('coffee_cup_screener')
    best_params, best_sharpe = runner.run_evolution_loop(max_generations=10)
"""

from .backtest_engine import BacktestEngine, BacktestResult, Trade
from .parameter_evolution import ParameterEvolution, ParameterSpace, get_param_space
from .experiment_runner import ExperimentRunner, list_experiments

__all__ = [
    'BacktestEngine',
    'BacktestResult', 
    'Trade',
    'ParameterEvolution',
    'ParameterSpace',
    'get_param_space',
    'ExperimentRunner',
    'list_experiments',
]
