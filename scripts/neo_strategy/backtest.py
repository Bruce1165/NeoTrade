#!/usr/bin/env python3
"""
NeoTrade Strategy Backtest Engine
High-performance backtesting for neo_trend_momentum_v1
"""

import os
import sys
import json
import sqlite3
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "auto_research"))

from backtest_engine import BacktestEngine, BacktestResult, Trade

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs" / "strategy_research"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"backtest_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class StrategyParams:
    """Strategy parameters"""
    trend_ma_long: int = 200
    trend_ma_medium: int = 50
    entry_ma_short: int = 10
    rs_lookback: int = 20
    rs_threshold: int = 80
    pullback_pct: float = 5.0
    volatility_atr_threshold: float = 5.0
    stop_loss: float = 8.0
    take_profit: float = 20.0
    max_hold_days: int = 15
    max_positions: int = 5
    position_size: float = 2000.0


class NeoStrategyBacktest:
    """
    Neo Trend Momentum Strategy Backtest Engine
    
    Targets:
    - Win rate > 65%
    - Annual return > 50%
    - Stop loss < 10%
    """
    
    def __init__(self, params: Optional[StrategyParams] = None):
        self.params = params or StrategyParams()
        self.db_path = PROJECT_ROOT / "data" / "stock_data.db"
        self.conn = None
        
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, *args):
        self.close()
    
    def calculate_ma(self, code: str, date: str, period: int) -> Optional[float]:
        """Calculate moving average for a stock up to a date"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT close FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        ''', (code, date, period))
        rows = cursor.fetchall()
        if len(rows) < period:
            return None
        prices = [r['close'] for r in rows]
        return sum(prices) / len(prices)
    
    def calculate_atr(self, code: str, date: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT high, low, close FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        ''', (code, date, period + 1))
        rows = cursor.fetchall()
        if len(rows) < period + 1:
            return None
        
        tr_values = []
        for i in range(len(rows) - 1):
            high = rows[i]['high']
            low = rows[i]['low']
            prev_close = rows[i + 1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        
        return sum(tr_values) / len(tr_values) if tr_values else None
    
    def calculate_rs(self, code: str, date: str, lookback: int) -> Optional[float]:
        """Calculate relative strength (percentile rank) - simplified fast version"""
        cursor = self.conn.cursor()
        
        # Get stock price change over lookback period
        cursor.execute('''
            SELECT close FROM daily_prices
            WHERE code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        ''', (code, date, lookback + 1))
        rows = cursor.fetchall()
        if len(rows) < lookback + 1:
            return None
        
        current_price = rows[0]['close']
        past_price = rows[-1]['close']
        price_change = (current_price - past_price) / past_price * 100
        
        # Simple momentum score: map price change to 0-100 scale
        # Assume -50% to +50% range maps to 0-100
        rs_score = max(0, min(100, 50 + price_change))
        
        return rs_score
    
    def get_stock_data(self, code: str, date: str) -> Optional[Dict]:
        """Get stock data for a specific date"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dp.*, s.name
            FROM daily_prices dp
            JOIN stocks s ON dp.code = s.code
            WHERE dp.code = ? AND dp.trade_date = ?
        ''', (code, date))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """Get all trading days in range"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT trade_date FROM daily_prices
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
        ''', (start_date, end_date))
        return [r[0] for r in cursor.fetchall()]
    
    def scan_signals(self, date: str) -> List[Dict]:
        """Scan for entry signals on a given date"""
        cursor = self.conn.cursor()
        
        # Get all active stocks for the date
        cursor.execute('''
            SELECT DISTINCT code FROM daily_prices
            WHERE trade_date = ?
        ''', (date,))
        codes = [r[0] for r in cursor.fetchall()]
        
        signals = []
        p = self.params
        
        for code in codes:
            # Calculate indicators
            ma200 = self.calculate_ma(code, date, p.trend_ma_long)
            ma50 = self.calculate_ma(code, date, p.trend_ma_medium)
            ma10 = self.calculate_ma(code, date, p.entry_ma_short)
            
            if not all([ma200, ma50, ma10]):
                continue
            
            # Get current price
            data = self.get_stock_data(code, date)
            if not data:
                continue
            
            close = data['close']
            
            # Trend filters
            if close <= ma200 or close <= ma50:
                continue
            
            # Pullback filter
            distance_from_ma10 = abs(close - ma10) / ma10 * 100
            if distance_from_ma10 > p.pullback_pct:
                continue
            
            # Volatility filter
            atr = self.calculate_atr(code, date, 14)
            if atr:
                atr_pct = atr / close * 100
                if atr_pct > p.volatility_atr_threshold:
                    continue
            
            # Relative strength filter
            rs = self.calculate_rs(code, date, p.rs_lookback)
            if not rs or rs < p.rs_threshold:
                continue
            
            signals.append({
                'code': code,
                'name': data['name'],
                'price': close,
                'ma200': ma200,
                'ma50': ma50,
                'ma10': ma10,
                'rs': rs,
                'atr': atr,
                'date': date
            })
        
        # Sort by RS (highest first)
        signals.sort(key=lambda x: x['rs'], reverse=True)
        return signals
    
    def run_backtest(
        self,
        start_date: str = "2024-09-02",
        end_date: str = "2025-08-31",
        initial_capital: float = 10000.0
    ) -> Tuple[BacktestResult, List[Trade]]:
        """
        Run complete backtest
        """
        logger.info("=" * 60)
        logger.info(f"STARTING BACKTEST: {start_date} to {end_date}")
        logger.info("=" * 60)
        
        trading_days = self.get_trading_days(start_date, end_date)
        if len(trading_days) < 50:
            logger.error("Insufficient trading days")
            return self._empty_result(), []
        
        # Portfolio state
        positions = {}  # code -> {entry_date, entry_price, shares, hold_days, highest_price}
        cash = initial_capital
        trades = []
        equity_curve = []
        p = self.params
        
        for i, current_date in enumerate(trading_days[:-1]):
            next_date = trading_days[i + 1]
            
            # Check exits for existing positions
            exits = []
            for code, pos in list(positions.items()):
                data = self.get_stock_data(code, current_date)
                if not data:
                    continue
                
                current_price = data['close']
                pos['hold_days'] += 1
                
                # Update highest price for trailing stop
                if current_price > pos.get('highest_price', 0):
                    pos['highest_price'] = current_price
                
                # Calculate returns
                unrealized_return = (current_price - pos['entry_price']) / pos['entry_price'] * 100
                
                # Exit conditions
                exit_triggered = False
                exit_reason = ""
                exit_price = current_price
                
                if unrealized_return <= -p.stop_loss:
                    exit_triggered = True
                    exit_reason = "stop_loss"
                    exit_price = pos['entry_price'] * (1 - p.stop_loss / 100)
                elif unrealized_return >= p.take_profit:
                    exit_triggered = True
                    exit_reason = "take_profit"
                    exit_price = pos['entry_price'] * (1 + p.take_profit / 100)
                elif pos['hold_days'] >= p.max_hold_days:
                    exit_triggered = True
                    exit_reason = "timeout"
                elif next_date == trading_days[-1]:
                    exit_triggered = True
                    exit_reason = "end_of_data"
                
                if exit_triggered:
                    # Calculate P&L
                    gross_proceeds = exit_price * pos['shares']
                    commission = gross_proceeds * 0.00025
                    net_proceeds = gross_proceeds - commission
                    
                    cost_basis = pos['entry_price'] * pos['shares']
                    realized_pnl = net_proceeds - cost_basis
                    realized_pnl_pct = realized_pnl / cost_basis * 100
                    
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
                    
                    logger.info(f"EXIT: {code} @ {exit_price:.2f} ({exit_reason}) P&L: {realized_pnl_pct:.2f}%")
            
            # Remove exited positions
            for code in exits:
                if code in positions:
                    del positions[code]
            
            # Check for new entries
            available_slots = p.max_positions - len(positions)
            if available_slots > 0 and cash >= p.position_size:
                signals = self.scan_signals(current_date)
                
                for signal in signals:
                    code = signal['code']
                    if code in positions:
                        continue
                    
                    # Get next day open price
                    next_day_data = self.get_stock_data(code, next_date)
                    if not next_day_data:
                        continue
                    
                    entry_price = next_day_data['open'] * 1.001  # 0.1% slippage
                    shares = int(p.position_size / entry_price / 100) * 100  # Round to 100s
                    
                    if shares < 100:
                        continue
                    
                    gross_cost = entry_price * shares
                    commission = gross_cost * 0.00025
                    total_cost = gross_cost + commission
                    
                    if total_cost > cash:
                        continue
                    
                    cash -= total_cost
                    
                    positions[code] = {
                        'entry_date': next_date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'hold_days': 0,
                        'name': signal['name'],
                        'highest_price': entry_price
                    }
                    
                    trade = Trade(
                        trade_date=next_date,
                        code=code,
                        name=signal['name'],
                        action="BUY",
                        price=entry_price,
                        shares=shares,
                        position_value=gross_cost
                    )
                    trades.append(trade)
                    available_slots -= 1
                    
                    logger.info(f"ENTRY: {code} @ {entry_price:.2f} ({signal['rs']:.1f} RS)")
                    
                    if available_slots <= 0:
                        break
            
            # Calculate daily equity
            position_value = 0
            for code, pos in positions.items():
                data = self.get_stock_data(code, current_date)
                if data:
                    position_value += data['close'] * pos['shares']
            
            total_equity = cash + position_value
            equity_curve.append({
                'date': current_date,
                'equity': total_equity,
                'cash': cash,
                'positions': len(positions)
            })
        
        # Calculate metrics
        result = self._calculate_metrics(
            trades, equity_curve, initial_capital
        )
        
        logger.info("=" * 60)
        logger.info("BACKTEST COMPLETE")
        logger.info(f"Total Return: {result.total_return*100:.2f}%")
        logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.3f}")
        logger.info(f"Win Rate: {result.win_rate*100:.1f}%")
        logger.info(f"Max Drawdown: {result.max_drawdown*100:.2f}%")
        logger.info(f"Total Trades: {result.total_trades}")
        logger.info("=" * 60)
        
        return result, trades
    
    def _calculate_metrics(
        self, trades: List[Trade], equity_curve: List[Dict], initial_capital: float
    ) -> BacktestResult:
        """Calculate performance metrics"""
        
        if not equity_curve:
            return self._empty_result()
        
        final_equity = equity_curve[-1]['equity']
        total_return = (final_equity - initial_capital) / initial_capital
        
        # Daily returns for Sharpe
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]['equity']
            curr = equity_curve[i]['equity']
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
        
        # Sharpe ratio
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
        
        # Trade stats
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
        
        # Calmar ratio
        years = len(equity_curve) / 252
        annualized_return = ((1 + total_return) ** (1/years) - 1) if years > 0 and total_return > -1 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Volatility
        volatility = std_dev * math.sqrt(252) if len(daily_returns) > 1 else 0
        
        return BacktestResult(
            strategy_version="neo_trend_momentum_v1",
            screener_name="neo_strategy",
            params=asdict(self.params),
            train_start=equity_curve[0]['date'] if equity_curve else "",
            train_end=equity_curve[-1]['date'] if equity_curve else "",
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
    
    def _empty_result(self) -> BacktestResult:
        """Return empty result"""
        return BacktestResult(
            strategy_version="neo_trend_momentum_v1",
            screener_name="neo_strategy",
            params=asdict(self.params),
            train_start="",
            train_end=""
        )
    
    def save_results(self, result: BacktestResult, trades: List[Trade]):
        """Save results to database"""
        from backtest_engine import BacktestEngine
        
        engine = BacktestEngine()
        backtest_id = engine.save_backtest(result, trades)
        logger.info(f"Results saved to database (ID: {backtest_id})")
        return backtest_id


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2024-09-02')
    parser.add_argument('--end', default='2025-08-31')
    parser.add_argument('--capital', type=float, default=10000)
    args = parser.parse_args()
    
    # Load strategy config
    config_file = PROJECT_ROOT / "scripts" / "neo_strategy" / "strategy_config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        param_dict = config.get('parameters', {})
        # Filter only valid StrategyParams fields
        valid_fields = {f for f in StrategyParams.__dataclass_fields__}
        filtered_params = {k: v for k, v in param_dict.items() if k in valid_fields}
        params = StrategyParams(**filtered_params)
    else:
        params = StrategyParams()
    
    # Run backtest
    backtest = NeoStrategyBacktest(params)
    with backtest:
        result, trades = backtest.run_backtest(args.start, args.end, args.capital)
        backtest.save_results(result, trades)
        
        # Print summary
        print("\n" + "=" * 60)
        print("BACKTEST SUMMARY")
        print("=" * 60)
        print(f"Total Return:     {result.total_return*100:>8.2f}%")
        print(f"Annualized:       {((1+result.total_return)**(252/len(backtest.get_trading_days(args.start, args.end)))-1)*100:>8.2f}%")
        print(f"Sharpe Ratio:     {result.sharpe_ratio:>8.3f}")
        print(f"Max Drawdown:     {result.max_drawdown*100:>8.2f}%")
        print(f"Win Rate:         {result.win_rate*100:>8.1f}%")
        print(f"Profit Factor:    {result.profit_factor:>8.2f}")
        print(f"Total Trades:     {result.total_trades:>8}")
        print(f"Avg Hold Days:    {result.avg_hold_days:>8.1f}")
        print("=" * 60)
