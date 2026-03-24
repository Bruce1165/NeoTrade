"""
Signal Generator - 针对A股市场特征的信号生成

A股独特特征：
1. T+1制度 - 今日买明日才能卖，必须预判次日走势
2. 涨跌停限制(10%/20%) - 连板后风险极高，需避免追高
3. 散户主导 - 换手率高，情绪化交易多，波动大
4. 政策敏感 - 板块轮动快，题材炒作盛行
5. 高波动性 - 需要更严格的止损和更短的持仓周期
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from strategy_config import StrategyConfig, CURRENT_CONFIG
from enum import Enum


# 旧版兼容接口
class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    AVOID = "avoid"


@dataclass
class Signal:
    """交易信号对象 - 兼容backtest_engine"""
    code: str
    signal_type: SignalType
    score: float
    date: str = ""
    reason: str = ""


class SignalGenerator:
    """旧版信号生成器接口 - 为兼容backtest_engine提供"""
    def __init__(self, config):
        self.config = config
        self.a_share_gen = AShareSignalGenerator(config)

    def generate(self, code: str, df: pd.DataFrame, date: str):
        """生成信号 - 兼容旧接口"""
        score = self.a_share_gen.generate_signal(code, df, date)

        # 转换为旧版信号格式
        if score.recommendation == "buy":
            return Signal(code, SignalType.BUY, score.score, date)
        elif score.recommendation == "avoid":
            return Signal(code, SignalType.AVOID, score.score, date)
        else:
            return Signal(code, SignalType.HOLD, score.score, date)

    def scan_buy_signals(self, universe: List[str], date: str) -> List[Signal]:
        """扫描买入信号 - 兼容backtest_engine"""
        import sqlite3

        buy_signals = []
        conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')

        for code in universe[:30]:  # 限制扫描数量加速回测
            try:
                # 获取最近60天数据
                query = """
                    SELECT * FROM daily_prices
                    WHERE code = ? AND trade_date <= ?
                    ORDER BY trade_date DESC
                    LIMIT 60
                """
                df = pd.read_sql_query(query, conn, params=(code, date))

                if len(df) < 60:
                    continue

                df = df.sort_values('trade_date')
                signal = self.a_share_gen.generate_signal(code, df, date)

                if signal.recommendation == "buy" and signal.score >= 0.6:
                    buy_signals.append(Signal(code, SignalType.BUY, signal.score, date))

            except Exception as e:
                continue

        conn.close()

        # 按信号强度排序，只取前N个
        buy_signals.sort(key=lambda x: x.score, reverse=True)
        max_positions = self.config.max_positions if self.config else 5
        return buy_signals[:max_positions]

    def generate_sell_signal(self, code: str, date: str, position_info: dict) -> Signal:
        """生成卖出信号 - 兼容backtest_engine

        position_info包含:
        - entry_price: 买入价格
        - entry_date: 买入日期
        - current_price: 当前价格
        - current_profit_pct: 当前盈亏百分比
        - days_held: 持有天数
        """
        # A股特色卖出逻辑
        current_profit = position_info.get('current_profit_pct', 0)
        days_held = position_info.get('days_held', 0)
        highest_price = position_info.get('highest_price', position_info.get('entry_price', 0))
        current_price = position_info.get('current_price', 0)

        # 硬性止损 -5%
        if current_profit <= -5:
            return Signal(code, SignalType.SELL, 1.0, date, f"stop_loss_{current_profit:.1f}%")

        # 止盈 - 10%收益
        if current_profit >= 10:
            return Signal(code, SignalType.SELL, 1.0, date, f"profit_target_{current_profit:.1f}%")

        # 移动止盈 - 回撤5%从最高点
        if current_price < highest_price * 0.95 and current_profit > 5:
            return Signal(code, SignalType.SELL, 0.8, date, f"trailing_stop_{current_profit:.1f}%")

        # 超时平仓 - 短线3天，中线10天
        if days_held >= 10:  # 中线最长10天
            return Signal(code, SignalType.SELL, 0.6, date, f"time_exit_{days_held}days")
        elif days_held >= 3 and current_profit > 0:  # 短线3天有盈利就走
            return Signal(code, SignalType.SELL, 0.5, date, f"short_term_exit_{days_held}days")

        return Signal(code, SignalType.HOLD, 0.0, date, "hold")


@dataclass
class SignalScore:
    """信号评分结果"""
    code: str
    date: str
    score: float  # 0-1 综合评分
    factors: Dict[str, float]  # 各因子得分
    recommendation: str  # buy/hold/sell
    risk_level: str  # low/medium/high


class AShareSignalGenerator:
    """A股专用信号生成器"""
    
    def __init__(self, config: StrategyConfig = None):
        self.config = config or CURRENT_CONFIG
        self.board_limits = {
            'main': 0.10,  # 主板 10%
            'chinext': 0.20,  # 创业板/科创板 20%
        }
    
    def get_board_type(self, code: str) -> str:
        """判断板块类型"""
        if code.startswith('688') or code.startswith('300'):
            return 'chinext'  # 科创板/创业板 20%涨跌停
        elif code.startswith('8') or code.startswith('4'):
            return '北交所'  # 北交所 30%
        else:
            return 'main'  # 主板 10%涨跌停
    
    def check_limit_up_risk(self, df: pd.DataFrame, lookback: int = 5) -> Tuple[bool, str]:
        """
        检查连板风险 - A股特色
        连板后追高风险极大，T+1无法止损
        """
        if len(df) < lookback + 1:
            return False, "数据不足"
        
        recent = df.tail(lookback)
        limit_up_count = (recent['pct_change'] > 9.5).sum()
        
        # 近5天内2次或以上涨停 = 高风险
        if limit_up_count >= 2:
            return True, f"近{lookback}日{limit_up_count}次涨停，追高风险极高"
        
        # 昨日涨停 + 今日高开 = T+1买入风险
        if len(df) >= 2:
            if df.iloc[-2]['pct_change'] > 9.5 and df.iloc[-1]['pct_change'] > 0:
                return True, "昨日涨停今日高开，T+1无法止损风险"
        
        return False, "连板风险可控"
    
    def calculate_turnover_quality(self, df: pd.DataFrame) -> Tuple[float, str]:
        """
        A股特色：换手率质量评估
        散户市场，换手率过高可能是出货信号
        """
        if len(df) < 20 or 'turnover' not in df.columns:
            return 0.0, "无换手率数据"
        
        turnover = df.iloc[-1]['turnover']
        turnover_ma5 = df.tail(5)['turnover'].mean()
        turnover_ma20 = df.tail(20)['turnover'].mean()
        
        # 换手率在 5-15% 最佳（A股散户活跃区间）
        if 5 <= turnover <= 15:
            if turnover > turnover_ma5 * 1.2:
                return 0.9, f"放量换手{turnover:.1f}%，资金活跃"
            else:
                return 0.7, f"健康换手{turnover:.1f}%"
        elif turnover > 20:
            return 0.3, f"过高换手{turnover:.1f}%，警惕出货"  # 散户踩踏风险
        elif turnover < 2:
            return 0.2, f"流动性不足{turnover:.1f}%"
        else:
            return 0.5, f"换手率{turnover:.1f}%"
    
    def calculate_momentum_a_share(self, df: pd.DataFrame) -> Tuple[float, str]:
        """
        A股特色动量计算
        避免追高（A股T+1追高风险极大）
        """
        if len(df) < 20:
            return 0.0, "数据不足"
        
        # 20日涨幅
        price_20d_ago = df.iloc[-20]['close']
        price_now = df.iloc[-1]['close']
        momentum_20d = (price_now - price_20d_ago) / price_20d_ago
        
        # 近5日涨幅（短期过热检测）
        price_5d_ago = df.iloc[-5]['close']
        momentum_5d = (price_now - price_5d_ago) / price_5d_ago
        
        # A股策略：中期温和上涨(10-25%) + 短期不过分热(避免>15%)
        # 这样避免追在短期高点，T+1次日低开被套
        
        score = 0.0
        reason_parts = []
        
        # 中期动量评估
        if 0.10 <= momentum_20d <= 0.25:
            score += 0.4
            reason_parts.append(f"20日涨{momentum_20d*100:.1f}%健康")
        elif momentum_20d > 0.30:
            score += 0.1
            reason_parts.append(f"20日涨{momentum_20d*100:.1f}%已高")
        elif momentum_20d < 0.05:
            score += 0.1
            reason_parts.append(f"20日涨{momentum_20d*100:.1f}%太弱")
        else:
            score += 0.2
            reason_parts.append(f"20日涨{momentum_20d*100:.1f}%")
        
        # 短期过热检测 - A股T+1特有风险
        if momentum_5d > 0.15:
            score -= 0.3  # 近5日涨超15%，追高风险
            reason_parts.append(f"近5日{momentum_5d*100:.1f}%过热⚠️")
        elif momentum_5d > 0.05:
            score += 0.3
            reason_parts.append(f"近5日{momentum_5d*100:.1f}%温和")
        else:
            score += 0.1
            reason_parts.append(f"近5日{momentum_5d*100:.1f}%蓄势")
        
        # 今日涨幅检查 - T+1必须控制买入当日涨幅
        today_change = df.iloc[-1]['pct_change'] / 100
        if today_change > 0.06:  # 今日已涨超6%
            score -= 0.3
            reason_parts.append(f"今日已涨{today_change*100:.1f}%追高风险")
        elif today_change > 0.03:
            score += 0.1
            reason_parts.append(f"今日涨{today_change*100:.1f}%可接受")
        
        final_score = max(0.0, min(1.0, score))
        return final_score, "; ".join(reason_parts)
    
    def check_policy_theme_risk(self, df: pd.DataFrame, sector: str = None) -> Tuple[float, str]:
        """
        A股政策敏感风险 - 简单版本
        连续大涨后政策打压风险
        """
        if len(df) < 10:
            return 0.5, "数据不足"
        
        recent_10d = df.tail(10)
        avg_gain = recent_10d['pct_change'].mean()
        
        # 10日平均涨幅过大 = 政策关注风险
        if avg_gain > 5:
            return 0.2, f"10日平均涨{avg_gain:.1f}%，政策打压风险高"
        elif avg_gain > 3:
            return 0.5, f"10日平均涨{avg_gain:.1f}%，关注政策风险"
        else:
            return 0.8, "政策风险可控"
    
    def generate_signal(self, code: str, df: pd.DataFrame, date: str) -> SignalScore:
        """
        生成交易信号 - A股专用
        """
        if len(df) < 60:  # A股需要更长期数据判断趋势
            return SignalScore(code, date, 0.0, {}, "数据不足", "high")
        
        factors = {}
        warnings = []
        
        # 1. 连板风险检查（A股特色）
        limit_risk, limit_msg = self.check_limit_up_risk(df)
        factors['limit_risk'] = 0.0 if limit_risk else 1.0
        if limit_risk:
            warnings.append(limit_msg)
        
        # 2. 换手率质量（A股散户市场）
        turnover_score, turnover_msg = self.calculate_turnover_quality(df)
        factors['turnover'] = turnover_score
        
        # 3. A股特色动量（防追高）
        momentum_score, momentum_msg = self.calculate_momentum_a_share(df)
        factors['momentum'] = momentum_score
        
        # 4. 均线趋势（A股趋势一旦形成较持续）
        ma_score, ma_msg = self._calculate_ma_trend(df)
        factors['ma_trend'] = ma_score
        
        # 5. 波动率（A股高波动需要控制）
        vol_score, vol_msg = self._calculate_volatility_score(df)
        factors['volatility'] = vol_score
        
        # 6. 政策风险
        policy_score, policy_msg = self.check_policy_theme_risk(df)
        factors['policy_risk'] = policy_score
        
        # 综合评分 - A股权重调整
        weights = {
            'limit_risk': 0.20,    # 连板风险权重高（T+1无法止损）
            'momentum': 0.25,      # 动量重要但防追高
            'turnover': 0.15,      # 换手率（散户指标）
            'ma_trend': 0.20,      # 趋势
            'volatility': 0.10,    # 波动
            'policy_risk': 0.10,   # 政策
        }
        
        total_score = sum(factors[k] * weights[k] for k in weights)
        
        # 风险评级
        if len(warnings) >= 2 or factors['limit_risk'] == 0:
            risk_level = "high"
            recommendation = "avoid"
        elif total_score >= 0.7 and not warnings:
            risk_level = "low"
            recommendation = "buy"
        elif total_score >= 0.5:
            risk_level = "medium"
            recommendation = "watch"
        else:
            risk_level = "high"
            recommendation = "avoid"
        
        return SignalScore(
            code=code,
            date=date,
            score=total_score,
            factors=factors,
            recommendation=recommendation,
            risk_level=risk_level
        )
    
    def _calculate_ma_trend(self, df: pd.DataFrame) -> Tuple[float, str]:
        """均线趋势评分"""
        if len(df) < 60:
            return 0.0, "数据不足"
        
        close = df['close']
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        price = close.iloc[-1]
        
        score = 0.0
        if price > ma20 > ma50:
            score = 1.0
            return score, f"多头排列 P>{ma20:.2f}>{ma50:.2f}"
        elif price > ma20:
            score = 0.6
            return score, f"短期突破 P>{ma20:.2f}"
        elif price > ma50:
            score = 0.3
            return score, f"中期支撑 P>{ma50:.2f}"
        else:
            score = 0.0
            return score, "均线下方"
    
    def _calculate_volatility_score(self, df: pd.DataFrame) -> Tuple[float, str]:
        """波动率评分 - A股高波动需要控制"""
        if len(df) < 20:
            return 0.0, "数据不足"
        
        # ATR计算
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        atr_pct = atr / close.iloc[-1]
        
        # A股：ATR < 3% 低波动，3-6%正常，>6%高波动风险
        if atr_pct < 0.03:
            return 0.9, f"低波动 ATR={atr_pct*100:.1f}%"
        elif atr_pct < 0.06:
            return 0.6, f"正常波动 ATR={atr_pct*100:.1f}%"
        else:
            return 0.2, f"高波动 ATR={atr_pct*100:.1f}%⚠️"


# 全局信号生成器实例
signal_generator = AShareSignalGenerator()
