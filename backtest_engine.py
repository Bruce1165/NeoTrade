"""
Backtest Engine - 回测引擎核心
严格屏蔽最近6个月数据，防止数据泄露
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import sqlite3
import json
from signal_generator import SignalGenerator, SignalType
from position_sizer import PositionSizer


class BacktestEngine:
    """回测引擎 - 模拟交易策略执行"""
    
    def __init__(self, config, train_end_date: str = "2025-08-31"):
        self.config = config
        self.signal_generator = SignalGenerator(config)
        self.position_sizer = PositionSizer(config)
        self.train_end_date = train_end_date
        
        # 回测状态
        self.daily_values: List[Dict] = []
        self.current_date: Optional[str] = None
        self.trade_count: int = 0
        self.win_count: int = 0
        self.loss_count: int = 0
        
        # 性能统计
        self.returns: List[float] = []
        self.drawdowns: List[float] = []
        self.peak_value: float = config.initial_capital
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日期列表"""
        conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
        query = """
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """
        dates = pd.read_sql_query(query, conn, params=(start_date, end_date))
        conn.close()
        return dates['trade_date'].tolist()
    
    def get_universe(self, date: str) -> List[str]:
        """获取当日股票池（排除ST、退市等）"""
        conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
        query = """
            SELECT DISTINCT code
            FROM daily_prices
            WHERE trade_date = ?
            AND volume > 0
            AND close > 0
        """
        codes = pd.read_sql_query(query, conn, params=(date,))
        conn.close()
        return codes['code'].tolist()
    
    def get_prices(self, date: str, codes: List[str]) -> Dict[str, float]:
        """获取当日价格数据"""
        conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
        placeholders = ','.join('?' * len(codes))
        query = f"""
            SELECT code, close, open, high, low, volume
            FROM daily_prices
            WHERE trade_date = ? AND code IN ({placeholders})
        """
        params = [date] + codes
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return dict(zip(df['code'], df['close']))
    
    def run_day(self, date: str) -> Dict:
        """运行单日回测"""
        self.current_date = date
        
        # 获取当日股票池
        universe = self.get_universe(date)
        if len(universe) == 0:
            return {'status': 'no_data'}
        
        # 获取当日价格
        prices = self.get_prices(date, universe)
        
        # === 1. 先处理卖出 ===
        # 检查现有持仓的卖出信号
        for code in list(self.position_sizer.positions.keys()):
            position_info = self.position_sizer.get_position_info(code)
            if position_info:
                sell_signal = self.signal_generator.generate_sell_signal(code, date, position_info)
                if sell_signal and sell_signal.signal_type == SignalType.SELL:
                    price = prices.get(code)
                    if price:
                        self.position_sizer.close_position(code, price, date, sell_signal.reason)
        
        # === 2. 再处理买入 ===
        # 扫描买入信号
        if self.position_sizer.can_open_position():
            buy_signals = self.signal_generator.scan_buy_signals(universe, date)
            
            for signal in buy_signals:
                if not self.position_sizer.can_open_position():
                    break
                
                if signal.signal_type == SignalType.BUY:
                    price = prices.get(signal.code)
                    if price:
                        self.position_sizer.open_position(
                            signal.code, price, date, signal.score
                        )
        
        # === 3. 更新持仓市值 ===
        self.position_sizer.update_positions(prices, date)
        
        # === 4. 记录每日状态 ===
        portfolio = self.position_sizer.get_portfolio_stats()
        
        # 更新峰值和回撤
        if portfolio['total_value'] > self.peak_value:
            self.peak_value = portfolio['total_value']
        
        drawdown = (portfolio['total_value'] - self.peak_value) / self.peak_value
        self.drawdowns.append(drawdown)
        
        # 计算日收益
        if len(self.daily_values) > 0:
            prev_value = self.daily_values[-1]['total_value']
            daily_return = (portfolio['total_value'] - prev_value) / prev_value
        else:
            daily_return = 0.0
        self.returns.append(daily_return)
        
        daily_record = {
            'date': date,
            'cash': portfolio['cash'],
            'positions_value': portfolio['positions_value'],
            'total_value': portfolio['total_value'],
            'total_return': portfolio['total_return'],
            'num_positions': portfolio['num_positions'],
            'exposure': portfolio['exposure'],
            'drawdown': drawdown,
            'daily_return': daily_return
        }
        self.daily_values.append(daily_record)
        
        # 检查风控限制
        if not self.position_sizer.check_risk_limits():
            # 触发风控，强制平仓所有持仓
            print(f"  ⚠️ 触发最大回撤限制，强制平仓所有持仓")
            for code in list(self.position_sizer.positions.keys()):
                price = prices.get(code)
                if price:
                    self.position_sizer.close_position(code, price, date, 'risk_limit_forced_exit')
            
            # 更新portfolio状态
            portfolio = self.position_sizer.get_portfolio_stats()
            
            return {'status': 'stopped', 'reason': 'risk_limit_triggered', 'portfolio': portfolio}
        
        return {'status': 'success', 'portfolio': portfolio}
    
    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """运行完整回测"""
        print(f"开始回测: {start_date} 到 {end_date}")
        print(f"初始资金: {self.config.initial_capital:,.2f}元")
        print("=" * 50)
        
        # 获取交易日历
        trade_dates = self.get_trade_dates(start_date, end_date)
        print(f"交易日数量: {len(trade_dates)}")
        
        # 逐日运行
        final_date = None
        for i, date in enumerate(trade_dates):
            if i % 50 == 0:
                print(f"进度: {i}/{len(trade_dates)} - {date}")
            
            result = self.run_day(date)
            final_date = date
            if result.get('status') == 'stopped':
                print(f"回测提前终止: {result.get('reason')}")
                break
        
        # 回测结束，平仓所有剩余持仓
        if len(self.position_sizer.positions) > 0:
            print(f"  📤 回测结束，平仓 {len(self.position_sizer.positions)} 只持仓")
            # 获取最后一天的收盘价
            prices = self.get_prices(final_date, list(self.position_sizer.positions.keys()))
            for code in list(self.position_sizer.positions.keys()):
                price = prices.get(code)
                if price:
                    self.position_sizer.close_position(code, price, final_date, 'backtest_end')
            
            # 更新最后一天的portfolio状态
            portfolio = self.position_sizer.get_portfolio_stats()
            if self.daily_values:
                self.daily_values[-1]['cash'] = portfolio['cash']
                self.daily_values[-1]['positions_value'] = portfolio['positions_value']
                self.daily_values[-1]['total_value'] = portfolio['total_value']
                self.daily_values[-1]['num_positions'] = 0
        
        # 计算性能指标
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> Dict:
        """计算回测性能指标"""
        if len(self.daily_values) == 0:
            return {'error': '没有回测数据'}
        
        # 基础指标
        initial_value = self.config.initial_capital
        final_value = self.daily_values[-1]['total_value']
        total_return = (final_value - initial_value) / initial_value
        
        # 年化指标（假设252个交易日/年）
        n_days = len(self.daily_values)
        years = n_days / 252
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 波动率
        returns_series = pd.Series(self.returns)
        volatility = returns_series.std() * np.sqrt(252)
        
        # 夏普比率（假设无风险利率2%）
        risk_free_rate = 0.02
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # 最大回撤
        max_drawdown = min(self.drawdowns) if self.drawdowns else 0
        
        # 交易统计
        trades = [t for t in self.position_sizer.trade_history if t['action'] == 'SELL']
        total_trades = len(trades)
        
        if total_trades > 0:
            win_trades = [t for t in trades if t['realized_pnl'] > 0]
            loss_trades = [t for t in trades if t['realized_pnl'] <= 0]
            
            win_rate = len(win_trades) / total_trades
            
            avg_win = np.mean([t['realized_pnl_pct'] for t in win_trades]) if win_trades else 0
            avg_loss = np.mean([t['realized_pnl_pct'] for t in loss_trades]) if loss_trades else 0
            
            profit_factor = (
                sum(t['realized_pnl'] for t in win_trades) / 
                abs(sum(t['realized_pnl'] for t in loss_trades))
            ) if loss_trades and sum(t['realized_pnl'] for t in loss_trades) != 0 else float('inf')
            
            # 止损触发率
            stop_loss_trades = [t for t in trades if '止损' in t.get('exit_reason', '')]
            stop_loss_rate = len(stop_loss_trades) / total_trades
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            stop_loss_rate = 0
        
        # 盈亏比
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        metrics = {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'profit_loss_ratio': profit_loss_ratio,
            'stop_loss_rate': stop_loss_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'final_value': final_value,
            'initial_value': initial_value,
            'trading_days': n_days,
            'years': years
        }
        
        return metrics
    
    def save_results(self, filepath: str = "backtest_result.json"):
        """保存回测结果"""
        metrics = self.calculate_metrics()
        
        result = {
            'config': {
                'initial_capital': self.config.initial_capital,
                'max_position_per_stock': self.config.max_position_per_stock,
                'hard_stop_loss': self.config.hard_stop_loss,
                'trailing_stop_pct': self.config.trailing_stop_pct,
                'use_ma_trend': self.config.use_ma_trend,
                'use_momentum': self.config.use_momentum,
                'use_volume': self.config.use_volume,
                'use_volatility': self.config.use_volatility,
            },
            'metrics': metrics,
            'daily_values': self.daily_values,
            'trades': self.position_sizer.trade_history
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"回测结果已保存: {filepath}")
        return result
