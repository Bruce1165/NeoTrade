#!/usr/bin/env python3
"""
Auto Research Lab - Backtest Engine
Historical simulation engine for strategy validation
"""

import sqlite3
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Callable
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard2.frontend.api.models import get_db_connection

@dataclass
class Trade:
    """Single trade record"""
    trade_date: str
    code: str
    name: str
    action: str  # BUY, SELL
    price: float
    shares: int = 0
    position_value: float = 0.0
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    hold_days: int = 0
    exit_reason: str = ""

@dataclass
class BacktestResult:
    """Backtest performance metrics"""
    strategy_version: str
    screener_name: str
    params: Dict
    train_start: str
    train_end: str
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    avg_trade_return: float = 0.0
    avg_hold_days: float = 0.0
    git_commit: str = ""
    parent_version: str = ""


class BacktestEngine:
    """
    Historical backtest engine for strategy validation
    
    Simulates trades over historical data with realistic assumptions:
    - Entry: Next day open after signal
    - Exit: Target hit, stop loss, or timeout
    - Commission: 0.025% per trade
    - Slippage: 0.1% on entry/exit
    """
    
    COMMISSION_RATE = 0.00025  # 0.025%
    SLIPPAGE_RATE = 0.001      # 0.1%
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(PROJECT_ROOT / "data" / "stock_data.db")
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, *args):
        self.close()
    
    def get_stock_data(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """Get historical price data for a stock"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dp.*, s.name
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE dp.code = ? AND dp.trade_date >= ? AND dp.trade_date <= ?
            ORDER BY dp.trade_date ASC
        ''', (code, start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_screener_signals(self, screener_name: str, date: str) -> List[Dict]:
        """Get stocks that passed screener on specific date"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT sr.stock_code as code, sr.stock_name as name, 
                   sr.close_price as signal_price, sr.extra_data
            FROM screener_runs scr
            JOIN screener_results sr ON sr.run_id = scr.id
            WHERE scr.screener_name = ? AND scr.run_date = ?
            AND scr.status = 'completed'
        ''', (screener_name, date))
        return [dict(row) for row in cursor.fetchall()]
    
    def run_backtest(
        self,
        screener_name: str,
        params: Dict,
        start_date: str,
        end_date: str,
        position_size: float = 0.1,  # 10% per position
        max_positions: int = 5,
        stop_loss: float = 0.08,      # 8% stop loss
        take_profit: float = 0.20,    # 20% take profit
        max_hold_days: int = 20,      # Max holding period
        strategy_version: str = "v1.0"
    ) -> Tuple[BacktestResult, List[Trade]]:
        """
        Run complete backtest simulation
        
        Strategy logic:
        1. Each day, check screener signals
        2. Enter at next day's open (with slippage)
        3. Exit on: stop loss, take profit, max hold days, or end of period
        4. Position sizing: equal weight among open positions
        """
        trades = []
        
        # Get all trading days in range
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT trade_date 
            FROM daily_prices 
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
        ''', (start_date, end_date))
        trading_days = [row[0] for row in cursor.fetchall()]
        
        if len(trading_days) < 2:
            return self._empty_result(screener_name, params, start_date, end_date, strategy_version), []
        
        # Portfolio state
        positions = {}  # code -> {entry_date, entry_price, shares, hold_days}
        cash = 100000.0  # Start with 100k
        initial_capital = cash
        equity_curve = []
        
        for i, current_date in enumerate(trading_days[:-1]):  # Exclude last day
            next_date = trading_days[i + 1]
            
            # Check exits for existing positions
            exits = []
            for code, pos in list(positions.items()):
                pos_data = self.get_stock_data(code, current_date, current_date)
                if not pos_data:
                    continue
                
                current_price = pos_data[0]['close']
                pos['hold_days'] += 1
                
                # Calculate returns
                unrealized_return = (current_price - pos['entry_price']) / pos['entry_price']
                
                # Exit conditions
                exit_triggered = False
                exit_reason = ""
                exit_price = current_price
                
                if unrealized_return <= -stop_loss:
                    exit_triggered = True
                    exit_reason = "stop_loss"
                    exit_price = pos['entry_price'] * (1 - stop_loss)
                elif unrealized_return >= take_profit:
                    exit_triggered = True
                    exit_reason = "take_profit"
                    exit_price = pos['entry_price'] * (1 + take_profit)
                elif pos['hold_days'] >= max_hold_days:
                    exit_triggered = True
                    exit_reason = "timeout"
                elif next_date == trading_days[-1]:  # End of backtest
                    exit_triggered = True
                    exit_reason = "end_of_data"
                
                if exit_triggered:
                    # Apply slippage
                    exit_price = exit_price * (1 - self.SLIPPAGE_RATE)
                    
                    # Calculate P&L
                    gross_proceeds = exit_price * pos['shares']
                    commission = gross_proceeds * self.COMMISSION_RATE
                    net_proceeds = gross_proceeds - commission
                    
                    cost_basis = pos['entry_price'] * pos['shares']
                    realized_pnl = net_proceeds - cost_basis
                    realized_pnl_pct = realized_pnl / cost_basis
                    
                    cash += net_proceeds
                    
                    trade = Trade(
                        trade_date=current_date,
                        code=code,
                        name=pos.get('name', code),
                        action="SELL",
                        price=exit_price,
                        shares=pos['shares'],
                        position_value=gross_proceeds,
                        realized_pnl=realized_pnl,
                        realized_pnl_pct=realized_pnl_pct,
                        hold_days=pos['hold_days'],
                        exit_reason=exit_reason
                    )
                    trades.append(trade)
                    exits.append(code)
            
            # Remove exited positions
            for code in exits:
                if code in positions:
                    del positions[code]
            
            # Check for new entries (if we have capacity)
            available_slots = max_positions - len(positions)
            if available_slots > 0 and cash > initial_capital * position_size:
                signals = self.get_screener_signals(screener_name, current_date)
                
                for signal in signals:
                    code = signal['code']
                    if code in positions:
                        continue
                    
                    # Get next day open price
                    next_day_data = self.get_stock_data(code, next_date, next_date)
                    if not next_day_data:
                        continue
                    
                    entry_price = next_day_data[0]['open'] * (1 + self.SLIPPAGE_RATE)
                    
                    # Position sizing
                    position_value = min(cash * position_size, cash * 0.95 / available_slots)
                    shares = int(position_value / entry_price)
                    
                    if shares < 100:  # Minimum 1 hand (100 shares)
                        continue
                    
                    gross_cost = entry_price * shares
                    commission = gross_cost * self.COMMISSION_RATE
                    total_cost = gross_cost + commission
                    
                    if total_cost > cash:
                        continue
                    
                    cash -= total_cost
                    
                    positions[code] = {
                        'entry_date': next_date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'hold_days': 0,
                        'name': signal.get('name', code)
                    }
                    
                    trade = Trade(
                        trade_date=next_date,
                        code=code,
                        name=signal.get('name', code),
                        action="BUY",
                        price=entry_price,
                        shares=shares,
                        position_value=gross_cost
                    )
                    trades.append(trade)
                    available_slots -= 1
                    
                    if available_slots <= 0:
                        break
            
            # Calculate daily equity
            position_value = 0
            for code, pos in positions.items():
                pos_data = self.get_stock_data(code, current_date, current_date)
                if pos_data:
                    position_value += pos_data[0]['close'] * pos['shares']
            
            total_equity = cash + position_value
            equity_curve.append({
                'date': current_date,
                'equity': total_equity,
                'cash': cash,
                'positions': len(positions)
            })
        
        # Calculate final metrics
        return self._calculate_metrics(
            trades, equity_curve, initial_capital,
            screener_name, params, start_date, end_date, strategy_version
        )
    
    def _calculate_metrics(
        self, trades: List[Trade], equity_curve: List[Dict],
        initial_capital: float, screener_name: str, params: Dict,
        start_date: str, end_date: str, strategy_version: str
    ) -> Tuple[BacktestResult, List[Trade]]:
        """Calculate performance metrics from trades and equity curve"""
        
        if not equity_curve:
            return self._empty_result(screener_name, params, start_date, end_date, strategy_version), trades
        
        # Basic returns
        final_equity = equity_curve[-1]['equity']
        total_return = (final_equity - initial_capital) / initial_capital
        
        # Daily returns for Sharpe calculation
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]['equity']
            curr = equity_curve[i]['equity']
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
        
        # Sharpe ratio (annualized, assuming 252 trading days)
        if len(daily_returns) > 1:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = math.sqrt(variance) if variance > 0 else 0
            sharpe_ratio = (avg_return / std_dev * math.sqrt(252)) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        peak = initial_capital
        max_drawdown = 0
        for point in equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # Trade statistics
        closed_trades = [t for t in trades if t.action == "SELL"]
        total_trades = len(closed_trades)
        
        if total_trades > 0:
            winning_trades = [t for t in closed_trades if t.realized_pnl > 0]
            win_rate = len(winning_trades) / total_trades
            
            gross_profit = sum(t.realized_pnl for t in winning_trades)
            gross_loss = abs(sum(t.realized_pnl for t in closed_trades if t.realized_pnl <= 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            avg_trade_return = sum(t.realized_pnl_pct for t in closed_trades) / total_trades
            avg_hold_days = sum(t.hold_days for t in closed_trades) / total_trades
        else:
            win_rate = 0
            profit_factor = 0
            avg_trade_return = 0
            avg_hold_days = 0
        
        # Calmar ratio (annualized return / max drawdown)
        years = len(equity_curve) / 252
        annualized_return = ((1 + total_return) ** (1/years) - 1) if years > 0 and total_return > -1 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Volatility (annualized)
        if len(daily_returns) > 1:
            volatility = std_dev * math.sqrt(252) if 'std_dev' in dir() else 0
        else:
            volatility = 0
        
        result = BacktestResult(
            strategy_version=strategy_version,
            screener_name=screener_name,
            params=params,
            train_start=start_date,
            train_end=end_date,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
            profit_factor=profit_factor,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
            avg_trade_return=avg_trade_return,
            avg_hold_days=avg_hold_days
        )
        
        return result, trades
    
    def _empty_result(
        self, screener_name: str, params: Dict,
        start_date: str, end_date: str, strategy_version: str
    ) -> BacktestResult:
        """Return empty result when no trades"""
        return BacktestResult(
            strategy_version=strategy_version,
            screener_name=screener_name,
            params=params,
            train_start=start_date,
            train_end=end_date
        )
    
    def save_backtest(self, result: BacktestResult, trades: List[Trade]) -> int:
        """Save backtest results to database"""
        db_path = str(PROJECT_ROOT / "dashboard2" / "frontend" / "api" / "data" / "dashboard.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert backtest result
        cursor.execute('''
            INSERT INTO strategy_backtest_results
            (strategy_version, screener_name, params, train_start, train_end,
             total_return, sharpe_ratio, max_drawdown, win_rate, total_trades,
             profit_factor, calmar_ratio, volatility, avg_trade_return, avg_hold_days,
             git_commit, parent_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.strategy_version, result.screener_name, json.dumps(result.params),
            result.train_start, result.train_end, result.total_return, result.sharpe_ratio,
            result.max_drawdown, result.win_rate, result.total_trades, result.profit_factor,
            result.calmar_ratio, result.volatility, result.avg_trade_return, result.avg_hold_days,
            result.git_commit, result.parent_version
        ))
        
        backtest_id = cursor.lastrowid
        
        # Insert trades
        for trade in trades:
            cursor.execute('''
                INSERT INTO strategy_trades
                (backtest_id, trade_date, code, name, action, price, shares,
                 position_value, realized_pnl, realized_pnl_pct, hold_days, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id, trade.trade_date, trade.code, trade.name, trade.action,
                trade.price, trade.shares, trade.position_value, trade.realized_pnl,
                trade.realized_pnl_pct, trade.hold_days, trade.exit_reason
            ))
        
        conn.commit()
        conn.close()
        
        return backtest_id


if __name__ == '__main__':
    # Test the backtest engine
    engine = BacktestEngine()
    with engine:
        result, trades = engine.run_backtest(
            screener_name="coffee_cup_screener",
            params={"cup_depth_max": 0.35, "handle_retrace_max": 0.10},
            start_date="2024-09-02",
            end_date="2025-08-31",
            strategy_version="test_v1"
        )
        print(f"Backtest Result: {result}")
        print(f"Total trades: {len([t for t in trades if t.action == 'SELL'])}")
