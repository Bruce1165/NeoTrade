"""
Strategy Configuration - 策略参数配置
每次实验调整这些参数
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class StrategyConfig:
    """策略配置类 - Autoresearch 将迭代优化这些参数"""
    
    # === 基础参数 ===
    initial_capital: float = 10000.0  # 初始资金：固定1万元
    max_position_per_stock: float = 0.30  # 单股最大仓位：30%
    commission_rate: float = 0.0003  # 佣金：0.03%
    stamp_duty_rate: float = 0.001  # 印花税：0.1%（仅卖出）
    
    # === A股特色：T+1制度 ===
    # T+1意味着今日买入无法卖出，必须承受次日低开风险
    # 策略必须在买入时预判次日走势，避免追高被套
    t1_aware_entry: bool = True  # 启用T+1感知入场
    max_gap_up_entry: float = 0.03  # 买入当日涨幅上限（防追高）
    
    # === 持仓周期（适配A股波动） ===
    min_hold_days: int = 2  # T+1最小持有2天（含买入日无法卖出）
    max_hold_days_short: int = 3  # 短线：3天（A股波动快）
    max_hold_days_medium: int = 10  # 中线：10天（避免长期被套）
    
    # === 止损止盈（A股涨跌停限制） ===
    # 主板10%，科创/创业板20%，但连板后风险极高
    hard_stop_loss: float = -0.05  # A股波动大，收紧止损至-5%
    limit_up_exit: bool = True  # 涨停后次日高开即止盈（T+1锁定利润）
    trailing_stop: bool = True
    trailing_stop_pct: float = 0.10  # 移动止盈降至10%（A股回撤快）
    profit_target: Optional[float] = 0.15  # 目标收益15%（现实化）
    
    # === 趋势因子 ===
    use_ma_trend: bool = True  # 是否使用均线趋势
    ma_short: int = 20  # 短期均线
    ma_medium: int = 50  # 中期均线
    require_ma_bullish: bool = True  # 要求多头排列
    
    # === 动量因子 ===
    use_momentum: bool = True  # 是否使用动量筛选
    momentum_lookback: int = 20  # 动量观察期（日）
    momentum_min: float = 0.05  # 降低动量要求，避免追高风险  # 最小涨幅：10%
    momentum_max: float = 0.15  # 严格限制涨幅，防止买在短期高点  # 最大涨幅：30%（防追高）
    
    # === 量能因子 ===
    use_volume: bool = True  # 是否使用量能筛选
    volume_ma_period: int = 5  # 成交量均线周期
    volume_surge_ratio: float = 1.5  # 放量倍数：1.5倍
    
    # === 波动因子 ===
    use_volatility: bool = True  # 是否使用波动率筛选
    atr_period: int = 14  # ATR周期
    max_atr_pct: float = 0.05  # 最大ATR/股价比：5%
    
    # === 风控参数 ===
    max_positions: int = 3  # 减少持仓数，集中火力  # 最大同时持仓数
    max_daily_trades: int = 1  # 每日最多1笔交易，减少摩擦成本  # 每日最大交易次数
    max_drawdown_limit: float = -0.15  # 策略最大回撤限制：-15%
    
    # === 信号强度 ===
    min_signal_score: float = 0.75  # 提高门槛，减少交易  # 最小信号分数（0-1）
    
    def __post_init__(self):
        """参数验证"""
        assert self.initial_capital == 10000.0, "初始资金必须固定为1万元"
        assert 0 < self.max_position_per_stock <= 1.0, "仓位比例必须在0-1之间"
        assert self.hard_stop_loss < 0, "止损必须是负数"
        assert self.min_hold_days >= 1, "最短持有至少1天"

# 当前实验配置（将被autoresearch迭代修改）
CURRENT_CONFIG = StrategyConfig()

# 配置版本历史（手动记录重要变更）
CONFIG_HISTORY = [
    {"version": "v0.1", "date": "2026-03-23", "change": "初始种子策略", "sharpe": None},
    {"version": "v0.2", "date": "2026-03-23", "change": "完成策略回测框架搭建", "sharpe": None},
]
