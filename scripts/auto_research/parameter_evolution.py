#!/usr/bin/env python3
"""
Auto Research Lab - Parameter Evolution Engine
Genetic algorithm inspired parameter optimization
"""

import json
import random
import copy
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np

@dataclass
class ParameterSpace:
    """Define the search space for a parameter"""
    name: str
    param_type: str  # float, int, bool, choice
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    step: Optional[float] = None
    default: Any = None


class ParameterEvolution:
    """
    Genetic algorithm inspired parameter evolution
    
    Strategy:
    1. Initialize population with random parameters
    2. Evaluate fitness (Sharpe ratio)
    3. Select elites (top performers)
    4. Crossover and mutate to create next generation
    5. Repeat until convergence or max generations
    """
    
    def __init__(
        self,
        param_spaces: List[ParameterSpace],
        population_size: int = 10,
        elite_ratio: float = 0.2,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.5,
        max_generations: int = 100,
        early_stop_patience: int = 20,
        target_sharpe: float = 1.0
    ):
        self.param_spaces = {p.name: p for p in param_spaces}
        self.population_size = population_size
        self.elite_count = max(1, int(population_size * elite_ratio))
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.max_generations = max_generations
        self.early_stop_patience = early_stop_patience
        self.target_sharpe = target_sharpe
        
        self.generation = 0
        self.best_sharpe = float('-inf')
        self.best_params = None
        self.patience_counter = 0
        self.history = []
    
    def generate_random_params(self) -> Dict[str, Any]:
        """Generate a random parameter set within defined spaces"""
        params = {}
        for name, space in self.param_spaces.items():
            if space.param_type == 'float':
                if space.step:
                    steps = int((space.max_value - space.min_value) / space.step)
                    params[name] = space.min_value + random.randint(0, steps) * space.step
                else:
                    params[name] = random.uniform(space.min_value, space.max_value)
            elif space.param_type == 'int':
                params[name] = random.randint(int(space.min_value), int(space.max_value))
            elif space.param_type == 'bool':
                params[name] = random.choice([True, False])
            elif space.param_type == 'choice':
                params[name] = random.choice(space.choices)
            else:
                params[name] = space.default
        return params
    
    def initialize_population(self) -> List[Dict[str, Any]]:
        """Create initial random population"""
        population = []
        for _ in range(self.population_size):
            population.append(self.generate_random_params())
        return population
    
    def mutate(self, params: Dict[str, Any], strength: float = 1.0) -> Dict[str, Any]:
        """Apply mutation to parameters"""
        mutated = copy.deepcopy(params)
        
        for name, space in self.param_spaces.items():
            if random.random() < self.mutation_rate * strength:
                if space.param_type == 'float':
                    # Gaussian mutation
                    current = mutated[name]
                    std = (space.max_value - space.min_value) * 0.1 * strength
                    new_value = current + random.gauss(0, std)
                    mutated[name] = max(space.min_value, min(space.max_value, new_value))
                    if space.step:
                        mutated[name] = round(mutated[name] / space.step) * space.step
                
                elif space.param_type == 'int':
                    current = mutated[name]
                    delta = random.randint(-2, 2)
                    mutated[name] = max(int(space.min_value), min(int(space.max_value), current + delta))
                
                elif space.param_type == 'bool':
                    mutated[name] = not mutated[name]
                
                elif space.param_type == 'choice':
                    mutated[name] = random.choice(space.choices)
        
        return mutated
    
    def crossover(
        self, 
        parent1: Dict[str, Any], 
        parent2: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Create two children from two parents"""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        
        child1 = {}
        child2 = {}
        
        for name in self.param_spaces.keys():
            if random.random() < 0.5:
                child1[name] = copy.deepcopy(parent1[name])
                child2[name] = copy.deepcopy(parent2[name])
            else:
                child1[name] = copy.deepcopy(parent2[name])
                child2[name] = copy.deepcopy(parent1[name])
        
        return child1, child2
    
    def select_elites(
        self, 
        population: List[Dict[str, Any]], 
        fitness_scores: List[float]
    ) -> List[Dict[str, Any]]:
        """Select top performers as elites"""
        # Sort by fitness (Sharpe ratio)
        sorted_pairs = sorted(
            zip(population, fitness_scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        elites = [p for p, _ in sorted_pairs[:self.elite_count]]
        
        # Update best
        if sorted_pairs and sorted_pairs[0][1] > self.best_sharpe:
            self.best_sharpe = sorted_pairs[0][1]
            self.best_params = copy.deepcopy(sorted_pairs[0][0])
            self.patience_counter = 0
        else:
            self.patience_counter += 1
        
        return elites
    
    def create_next_generation(
        self, 
        elites: List[Dict[str, Any]],
        population: List[Dict[str, Any]],
        fitness_scores: List[float]
    ) -> List[Dict[str, Any]]:
        """Create next generation through crossover and mutation"""
        new_population = copy.deepcopy(elites)  # Keep elites
        
        # Create rest of population
        while len(new_population) < self.population_size:
            # Tournament selection
            parent1 = self._tournament_select(population, fitness_scores)
            parent2 = self._tournament_select(population, fitness_scores)
            
            # Crossover
            child1, child2 = self.crossover(parent1, parent2)
            
            # Mutation with adaptive strength
            mutation_strength = 1.0 + (self.patience_counter / self.early_stop_patience)
            child1 = self.mutate(child1, mutation_strength)
            child2 = self.mutate(child2, mutation_strength)
            
            new_population.append(child1)
            if len(new_population) < self.population_size:
                new_population.append(child2)
        
        return new_population
    
    def _tournament_select(
        self, 
        population: List[Dict[str, Any]], 
        fitness_scores: List[float],
        tournament_size: int = 3
    ) -> Dict[str, Any]:
        """Select parent using tournament selection"""
        tournament_indices = random.sample(range(len(population)), min(tournament_size, len(population)))
        winner_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
        return copy.deepcopy(population[winner_idx])
    
    def should_stop(self) -> bool:
        """Check if evolution should stop"""
        if self.generation >= self.max_generations:
            return True
        if self.best_sharpe >= self.target_sharpe:
            return True
        if self.patience_counter >= self.early_stop_patience:
            return True
        return False
    
    def get_generation_version(self) -> str:
        """Generate version string for current generation"""
        return f"gen{self.generation:03d}_{datetime.now().strftime('%m%d_%H%M')}"
    
    def evolve_one_step(
        self, 
        population: List[Dict[str, Any]], 
        fitness_scores: List[float]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute one generation of evolution
        
        Returns:
            (new_population, generation_info)
        """
        self.generation += 1
        
        # Select elites
        elites = self.select_elites(population, fitness_scores)
        
        # Create next generation
        new_population = self.create_next_generation(elites, population, fitness_scores)
        
        # Record history
        generation_info = {
            'generation': self.generation,
            'best_sharpe': self.best_sharpe,
            'best_params': self.best_params,
            'avg_fitness': sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0,
            'should_stop': self.should_stop()
        }
        self.history.append(generation_info)
        
        return new_population, generation_info


# Predefined parameter spaces for screeners
SCRRENER_PARAM_SPACES = {
    'coffee_cup_screener': [
        ParameterSpace('cup_depth_max', 'float', 0.20, 0.50, step=0.05, default=0.35),
        ParameterSpace('handle_retrace_max', 'float', 0.05, 0.15, step=0.01, default=0.10),
        ParameterSpace('volume_surge', 'float', 1.5, 3.0, step=0.1, default=2.0),
        ParameterSpace('min_turnover', 'float', 0.03, 0.10, step=0.01, default=0.05),
        ParameterSpace('min_pct_change', 'float', 0.01, 0.05, step=0.01, default=0.02),
    ],
    'er_ban_hui_tiao_screener': [
        ParameterSpace('max_pullback', 'float', 0.03, 0.10, step=0.01, default=0.05),
        ParameterSpace('min_limit_up_days', 'int', 1, 3, default=2),
        ParameterSpace('volume_contraction', 'float', 0.5, 0.9, step=0.1, default=0.7),
        ParameterSpace('ma_support', 'choice', choices=['MA10', 'MA20', 'MA30'], default='MA20'),
    ],
    'zhang_ting_bei_liang_yin_screener': [
        ParameterSpace('volume_threshold', 'float', 1.5, 3.0, step=0.1, default=2.0),
        ParameterSpace('shadow_ratio_max', 'float', 0.3, 0.7, step=0.1, default=0.5),
        ParameterSpace('body_ratio_min', 'float', 0.01, 0.05, step=0.01, default=0.02),
    ],
    'jin_feng_huang_screener': [
        ParameterSpace('ma_alignment_strict', 'bool', default=True),
        ParameterSpace('rs_threshold', 'int', 70, 95, default=85),
        ParameterSpace('volume_expansion', 'float', 1.2, 2.5, step=0.1, default=1.5),
    ],
}


def get_param_space(screener_name: str) -> List[ParameterSpace]:
    """Get parameter space for a screener"""
    return SCRRENER_PARAM_SPACES.get(screener_name, [])


if __name__ == '__main__':
    # Test parameter evolution
    spaces = SCRRENER_PARAM_SPACES['coffee_cup_screener']
    evo = ParameterEvolution(spaces, population_size=5)
    
    # Simulate evolution
    population = evo.initialize_population()
    for gen in range(3):
        # Mock fitness scores (in real use, these come from backtest)
        fitness = [random.uniform(-1, 1) for _ in population]
        population, info = evo.evolve_one_step(population, fitness)
        print(f"Gen {gen+1}: Best Sharpe = {info['best_sharpe']:.3f}")
