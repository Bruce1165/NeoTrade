#!/usr/bin/env python3
"""
Auto Research Lab - Experiment Runner
Orchestrates backtests and parameter evolution
"""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.auto_research.backtest_engine import BacktestEngine, BacktestResult
from scripts.auto_research.parameter_evolution import ParameterEvolution, get_param_space


class ExperimentRunner:
    """
    Main orchestrator for Auto Research experiments
    
    Responsibilities:
    1. Run single backtest with given parameters
    2. Run evolution loop (backtest + evolve + repeat)
    3. Git integration for experiment versioning
    4. Logging and progress tracking
    """
    
    def __init__(self, screener_name: str, experiment_name: Optional[str] = None):
        self.screener_name = screener_name
        self.experiment_name = experiment_name or f"{screener_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Paths
        self.log_dir = PROJECT_ROOT / "logs" / "auto_research"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{self.experiment_name}.log"
        
        # Initialize components
        self.backtest_engine = BacktestEngine()
        
        # Get parameter space
        param_spaces = get_param_space(screener_name)
        if not param_spaces:
            raise ValueError(f"No parameter space defined for {screener_name}")
        
        self.evolution = ParameterEvolution(
            param_spaces=param_spaces,
            population_size=10,
            elite_ratio=0.2,
            mutation_rate=0.3,
            crossover_rate=0.5,
            max_generations=100,
            early_stop_patience=20,
            target_sharpe=1.0
        )
        
        # Training period (fixed for consistency)
        self.train_start = "2024-09-02"
        self.train_end = "2025-08-31"
        
        self._log(f"Experiment initialized: {self.experiment_name}")
        self._log(f"Screener: {screener_name}")
        self._log(f"Training period: {self.train_start} to {self.train_end}")
    
    def _log(self, message: str):
        """Write to log file and stdout"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        with open(self.log_file, 'a') as f:
            f.write(log_line + '\n')
    
    def _git_commit(self, message: str) -> str:
        """Create git commit for experiment state"""
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return ""
            
            # Add all changes
            subprocess.run(['git', 'add', '-A'], cwd=PROJECT_ROOT, check=False)
            
            # Create commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Get commit hash
                result = subprocess.run(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True
                )
                return result.stdout.strip()
            
        except Exception as e:
            self._log(f"Git commit failed: {e}")
        
        return ""
    
    def run_single_backtest(
        self, 
        params: Dict,
        version: str,
        parent_version: str = ""
    ) -> Tuple[float, int]:
        """
        Run single backtest with given parameters
        
        Returns:
            (sharpe_ratio, backtest_id)
        """
        self._log(f"Running backtest: {version}")
        self._log(f"Params: {json.dumps(params)}")
        
        try:
            with self.backtest_engine:
                result, trades = self.backtest_engine.run_backtest(
                    screener_name=self.screener_name,
                    params=params,
                    start_date=self.train_start,
                    end_date=self.train_end,
                    strategy_version=version
                )
                
                # Add git commit and parent version
                result.git_commit = self._git_commit(f"Experiment: {version}")
                result.parent_version = parent_version
                
                # Save to database
                backtest_id = self.backtest_engine.save_backtest(result, trades)
                
                self._log(f"Backtest complete: Sharpe={result.sharpe_ratio:.3f}, Trades={result.total_trades}")
                
                return result.sharpe_ratio, backtest_id
                
        except Exception as e:
            self._log(f"Backtest failed: {e}")
            import traceback
            self._log(traceback.format_exc())
            return -2.0, -1  # Penalty for failed backtest
    
    def run_evolution_loop(self, max_generations: Optional[int] = None):
        """
        Run complete evolution loop
        
        Evolution process:
        1. Initialize random population
        2. For each generation:
           a. Run backtest for each parameter set
           b. Evaluate fitness (Sharpe ratio)
           c. Select elites and create next generation
           d. Check stop conditions
        3. Return best parameters found
        """
        if max_generations:
            self.evolution.max_generations = max_generations
        
        self._log("=" * 60)
        self._log("STARTING EVOLUTION LOOP")
        self._log("=" * 60)
        
        # Initialize population
        population = self.evolution.initialize_population()
        self._log(f"Initialized population of {len(population)}")
        
        generation_history = []
        
        while not self.evolution.should_stop():
            self._log(f"\n{'='*40}")
            self._log(f"GENERATION {self.evolution.generation + 1}")
            self._log(f"{'='*40}")
            
            # Run backtests for entire population
            fitness_scores = []
            backtest_ids = []
            
            for i, params in enumerate(population):
                version = f"gen{self.evolution.generation + 1:03d}_ind{i+1:02d}"
                parent = self.evolution.best_params if self.evolution.best_params else ""
                
                sharpe, backtest_id = self.run_single_backtest(params, version, str(parent))
                fitness_scores.append(sharpe)
                backtest_ids.append(backtest_id)
                
                # Small delay to prevent DB overload
                time.sleep(0.1)
            
            # Log generation stats
            avg_fitness = sum(fitness_scores) / len(fitness_scores)
            max_fitness = max(fitness_scores)
            min_fitness = min(fitness_scores)
            
            self._log(f"\nGeneration Stats:")
            self._log(f"  Avg Sharpe: {avg_fitness:.3f}")
            self._log(f"  Best Sharpe: {max_fitness:.3f}")
            self._log(f"  Worst Sharpe: {min_fitness:.3f}")
            
            # Evolve to next generation
            population, gen_info = self.evolution.evolve_one_step(population, fitness_scores)
            generation_history.append(gen_info)
            
            self._log(f"\nBest so far: Sharpe={gen_info['best_sharpe']:.3f}")
            
            # Save generation history
            self._save_generation_history(generation_history)
            
            # Check stop conditions
            if gen_info['should_stop']:
                reason = self._get_stop_reason()
                self._log(f"\nStopping: {reason}")
                break
        
        # Final summary
        self._log(f"\n{'='*60}")
        self._log("EVOLUTION COMPLETE")
        self._log(f"{'='*60}")
        self._log(f"Total generations: {self.evolution.generation}")
        self._log(f"Best Sharpe: {self.evolution.best_sharpe:.3f}")
        self._log(f"Best params: {json.dumps(self.evolution.best_params, indent=2)}")
        
        return self.evolution.best_params, self.evolution.best_sharpe
    
    def _get_stop_reason(self) -> str:
        """Get reason for stopping evolution"""
        if self.evolution.best_sharpe >= self.evolution.target_sharpe:
            return f"Target Sharpe ({self.evolution.target_sharpe}) reached!"
        if self.evolution.patience_counter >= self.evolution.early_stop_patience:
            return f"No improvement for {self.evolution.early_stop_patience} generations"
        if self.evolution.generation >= self.evolution.max_generations:
            return f"Max generations ({self.evolution.max_generations}) reached"
        return "Unknown"
    
    def _save_generation_history(self, history: List[Dict]):
        """Save evolution history to file"""
        history_file = self.log_dir / f"{self.experiment_name}_history.json"
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2, default=str)
    
    def run_baseline(self) -> Tuple[float, int]:
        """
        Run baseline backtest with default parameters
        
        Returns:
            (sharpe_ratio, backtest_id)
        """
        self._log("Running baseline backtest with default parameters")
        
        # Get default parameters
        default_params = {
            name: space.default 
            for name, space in self.evolution.param_spaces.items()
        }
        
        return self.run_single_backtest(default_params, "baseline_000", "")


def list_experiments() -> List[Dict]:
    """List all experiment logs"""
    log_dir = PROJECT_ROOT / "logs" / "auto_research"
    if not log_dir.exists():
        return []
    
    experiments = []
    for log_file in log_dir.glob("*.log"):
        if "_history" in log_file.name:
            continue
        
        stat = log_file.stat()
        experiments.append({
            'name': log_file.stem,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'size': stat.st_size,
            'path': str(log_file)
        })
    
    return sorted(experiments, key=lambda x: x['created'], reverse=True)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto Research Lab Experiment Runner')
    parser.add_argument('screener', help='Screener name to optimize')
    parser.add_argument('--generations', '-g', type=int, default=10, help='Max generations')
    parser.add_argument('--baseline', '-b', action='store_true', help='Run baseline only')
    parser.add_argument('--list', '-l', action='store_true', help='List experiments')
    
    args = parser.parse_args()
    
    if args.list:
        experiments = list_experiments()
        for exp in experiments:
            print(f"{exp['name']}: {exp['created']}")
    elif args.baseline:
        runner = ExperimentRunner(args.screener)
        sharpe, backtest_id = runner.run_baseline()
        print(f"\nBaseline Sharpe: {sharpe:.3f}")
    else:
        runner = ExperimentRunner(args.screener)
        best_params, best_sharpe = runner.run_evolution_loop(max_generations=args.generations)
        print(f"\nBest parameters found:")
        print(json.dumps(best_params, indent=2))
        print(f"Best Sharpe: {best_sharpe:.3f}")
