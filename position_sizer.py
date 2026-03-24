"""
Position Sizer - 仓位管理模块
管理资金分配和风险控制
"""
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Position:
    """持仓信息"""
    code: str
    shares: int
    entry_price: float
    entry_date: str
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    highest_price: float
    hold_days: int


class PositionSizer:
    """仓位管理器"""
    
    def __init__(self, config):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.cash: float = config.initial_capital
        self.total_value: float = config.initial_capital
        self.daily_trade_count: int = 0
        self.current_date: Optional[str] = None
        self.trade_history: List[Dict] = []
    
    def reset_day(self, date: str):
        """重置每日计数"""
        if self.current_date != date:
            self.current_date = date
            self.daily_trade_count = 0
    
    def can_open_position(self) -> bool:
        """检查是否可以开新仓"""
        return (
            len(self.positions) < self.config.max_positions and
            self.daily_trade_count < self.config.max_daily_trades
        )
    
    def calculate_position_size(self, price: float, signal_score: float) -> int:
        """计算仓位大小（股数）"""
        # 基于信号强度调整仓位
        position_multiplier = 0.5 + signal_score * 0.5  # 0.5 - 1.0
        
        # 计算目标仓位金额
        max_position_value = self.total_value * self.config.max_position_per_stock
        target_value = max_position_value * position_multiplier
        
        # 考虑剩余现金
        available_cash = self.cash * 0.95  # 保留5%现金缓冲
        target_value = min(target_value, available_cash)
        
        # 计算股数（100股为1手，A股最小交易单位）
        shares = int(target_value / price / 100) * 100
        
        # 至少买入1手
        if shares < 100:
            shares = 100 if price * 100 <= available_cash else 0
        
        return shares
    
    def open_position(self, code: str, price: float, date: str, signal_score: float) -> Optional[Position]:
        """开仓"""
        self.reset_day(date)
        
        if not self.can_open_position():
            return None
        
        if code in self.positions:
            return None  # 已有持仓
        
        shares = self.calculate_position_size(price, signal_score)
        if shares < 100:
            return None
        
        # 计算交易成本
        amount = price * shares
        commission = max(5, amount * self.config.commission_rate)  # 最低5元佣金
        total_cost = amount + commission
        
        if total_cost > self.cash:
            # 重新计算可买入股数
            shares = int((self.cash / (1 + self.config.commission_rate)) / price / 100) * 100
            if shares < 100:
                return None
            amount = price * shares
            commission = max(5, amount * self.config.commission_rate)
            total_cost = amount + commission
        
        # 扣除现金
        self.cash -= total_cost
        self.daily_trade_count += 1
        
        # 创建持仓
        position = Position(
            code=code,
            shares=shares,
            entry_price=price,
            entry_date=date,
            current_price=price,
            market_value=amount,
            cost_basis=total_cost,
            unrealized_pnl=-commission,
            unrealized_pnl_pct=-commission / total_cost,
            highest_price=price,
            hold_days=0
        )
        
        self.positions[code] = position
        
        # 记录交易
        self.trade_history.append({
            'date': date,
            'code': code,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'amount': amount,
            'commission': commission,
            'stamp_duty': 0,
            'total_cost': total_cost,
            'signal_score': signal_score
        })
        
        return position
    
    def close_position(self, code: str, price: float, date: str, reason: str) -> Optional[Dict]:
        """平仓"""
        if code not in self.positions:
            return None
        
        self.reset_day(date)
        position = self.positions[code]
        
        # 计算卖出金额和成本
        amount = price * position.shares
        commission = max(5, amount * self.config.commission_rate)
        stamp_duty = amount * self.config.stamp_duty_rate
        total_cost = commission + stamp_duty
        net_proceeds = amount - total_cost
        
        # 计算盈亏
        realized_pnl = net_proceeds - position.cost_basis
        realized_pnl_pct = realized_pnl / (position.entry_price * position.shares)
        
        # 增加现金
        self.cash += net_proceeds
        
        # 记录交易
        trade_record = {
            'date': date,
            'code': code,
            'action': 'SELL',
            'price': price,
            'shares': position.shares,
            'amount': amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'total_cost': total_cost,
            'realized_pnl': realized_pnl,
            'realized_pnl_pct': realized_pnl_pct,
            'hold_days': position.hold_days,
            'exit_reason': reason
        }
        self.trade_history.append(trade_record)
        
        # 删除持仓
        del self.positions[code]
        
        return trade_record
    
    def update_positions(self, prices: Dict[str, float], date: str):
        """更新持仓市值"""
        self.reset_day(date)
        
        for code, position in self.positions.items():
            if code in prices:
                price = prices[code]
                position.current_price = price
                position.market_value = price * position.shares
                position.unrealized_pnl = position.market_value - position.cost_basis
                position.unrealized_pnl_pct = position.unrealized_pnl / position.cost_basis
                
                # 更新最高价
                if price > position.highest_price:
                    position.highest_price = price
                
                # 增加持仓天数
                position.hold_days += 1
        
        # 更新总资产
        self.total_value = self.cash + sum(p.market_value for p in self.positions.values())
    
    def get_position_info(self, code: str) -> Optional[Dict]:
        """获取持仓信息（用于信号生成）"""
        if code not in self.positions:
            return None
        
        p = self.positions[code]
        return {
            'entry_price': p.entry_price,
            'current_price': p.current_price,
            'hold_days': p.hold_days,
            'highest_price': p.highest_price,
            'current_profit_pct': p.unrealized_pnl_pct * 100  # 转换为百分比
        }
    
    def get_portfolio_stats(self) -> Dict:
        """获取组合统计"""
        total_cost_basis = sum(p.cost_basis for p in self.positions.values())
        total_market_value = sum(p.market_value for p in self.positions.values())
        
        return {
            'cash': self.cash,
            'positions_value': total_market_value,
            'total_value': self.total_value,
            'total_return': (self.total_value - self.config.initial_capital) / self.config.initial_capital,
            'num_positions': len(self.positions),
            'exposure': total_market_value / self.total_value if self.total_value > 0 else 0
        }
    
    def check_risk_limits(self) -> bool:
        """检查是否触发风控限制"""
        total_return = (self.total_value - self.config.initial_capital) / self.config.initial_capital
        
        # 检查最大回撤限制
        if total_return <= self.config.max_drawdown_limit:
            return False
        
        return True
