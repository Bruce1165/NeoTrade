#!/usr/bin/env python3
"""
平底形态筛选器 - Flat Base Screener (欧奈尔 CANSLIM)

形态定义：
- 股价在一段时间内横向整理，波动幅度很小
- 形成水平的底部区域（类似矩形整理）
- 突破时放量上涨

技术参数（欧奈尔标准）：
- 整理周期：5-7周（25-35个交易日）
- 波动幅度：≤15%（最高价-最低价）/ 最低价
- 突破幅度：收盘价突破区间高点3%以上
- 突破成交量：≥1.5倍整理期均量
- 整理期特征：成交量逐渐萎缩

欧奈尔认为平底是杯柄形态的一种变体，出现在杯柄之后或单独出现。
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

from base_screener import BaseScreener
from database import init_db, get_session, Stock

logger = logging.getLogger(__name__)


class FlatBaseScreener(BaseScreener):
    """平底形态筛选器（欧奈尔标准）"""
    
    def __init__(self,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='flat_base',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        # 欧奈尔平底标准参数
        self.min_base_days = 25       # 整理期最小25天（5周）
        self.max_base_days = 35       # 整理期最大35天（7周）
        self.max_range_pct = 0.15     # 波动幅度最大15%
        self.min_breakout_pct = 0.03  # 突破最小3%
        self.min_volume_ratio = 1.5   # 突破成交量1.5倍
    
    def find_flat_base(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找平底形态
        
        Returns:
            平底信息或None
        """
        if len(df) < self.max_base_days + 10:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 从后向前寻找整理区间
        for i in range(len(df) - 1, self.max_base_days, -1):
            # 取可能的整理期
            base_period = df.iloc[i - self.max_base_days:i]
            
            if len(base_period) < self.min_base_days:
                continue
            
            base_high = base_period['high'].max()
            base_low = base_period['low'].min()
            base_close_avg = base_period['close'].mean()
            
            # 检查波动幅度
            range_pct = (base_high - base_low) / base_low
            if range_pct > self.max_range_pct:
                continue
            
            # 检查收盘价是否集中在区间中部（排除趋势形态）
            close_positions = []
            for _, row in base_period.iterrows():
                pos = (row['close'] - base_low) / (base_high - base_low)
                close_positions.append(pos)
            
            avg_position = np.mean(close_positions)
            # 平均位置应在30%-70%之间（不是一直跌或一直涨）
            if not (0.3 <= avg_position <= 0.7):
                continue
            
            # 检查是否有明显的趋势线（排除上升通道或下降通道）
            # 简单线性回归检查斜率
            x = np.arange(len(base_period))
            y = base_period['close'].values
            slope = np.polyfit(x, y, 1)[0]
            
            # 斜率应接近0（水平整理）
            if abs(slope) > (base_high - base_low) / len(base_period) * 0.5:
                continue
            
            # 检查突破
            latest = df.iloc[-1]
            breakout_price = latest['close']
            
            # 收盘价突破区间高点3%以上
            if breakout_price < base_high * (1 + self.min_breakout_pct):
                continue
            
            # 检查突破成交量
            base_volume_avg = base_period['volume'].mean()
            if base_volume_avg > 0 and latest['volume'] < base_volume_avg * self.min_volume_ratio:
                continue
            
            # 检查整理期成交量特征（应逐渐萎缩）
            first_half_vol = base_period.iloc[:len(base_period)//2]['volume'].mean()
            second_half_vol = base_period.iloc[len(base_period)//2:]['volume'].mean()
            
            return {
                'base_high': round(base_high, 2),
                'base_low': round(base_low, 2),
                'base_range_pct': round(range_pct * 100, 2),
                'avg_close': round(base_close_avg, 2),
                'slope': round(slope, 4),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - base_high) / base_high * 100, 2),
                'volume_ratio': round(latest['volume'] / base_volume_avg, 2) if base_volume_avg > 0 else 0,
                'volume_contraction': round(second_half_vol / first_half_vol * 100, 1) if first_half_vol > 0 else 100,
                'base_days': len(base_period)
            }
        
        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=60)
        if df is None or len(df) < 40:
            return None
        
        yesterday = df.iloc[-1]
        
        # 基础条件
        if yesterday.get('pct_change', 0) < 2.0:
            return None
        
        # 寻找平底形态
        flat_base = self.find_flat_base(df)
        if flat_base is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'base_high': flat_base['base_high'],
            'base_low': flat_base['base_low'],
            'base_range_pct': flat_base['base_range_pct'],
            'breakout_pct': flat_base['breakout_pct'],
            'volume_ratio': flat_base['volume_ratio'],
            'volume_contraction': flat_base['volume_contraction'],
            'base_days': flat_base['base_days']
        }
    
    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """详细检查单个股票"""
        from database import get_session, Stock
        
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        reasons = []
        details = {}
        
        try:
            session = get_session(init_db())
            stock = session.query(Stock).filter_by(code=code).first()
            name = stock.name if stock else ''
            session.close()
        except:
            name = ''
        
        df = self.get_stock_data(code, days=60)
        if df is None or len(df) < 40:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少40天）']
            }
        
        yesterday = df.iloc[-1]
        
        # 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2.0:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < 2%')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 检查平底形态
        flat_base = self.find_flat_base(df)
        
        if flat_base is None:
            reasons.append(f'未找到平底形态（需满足：整理期{self.min_base_days}-{self.max_base_days}天、'
                          f'波动≤{self.max_range_pct*100:.0f}%、突破≥{self.min_breakout_pct*100:.0f}%）')
        else:
            details['整理区间高点'] = f"{flat_base['base_high']:.2f}"
            details['整理区间低点'] = f"{flat_base['base_low']:.2f}"
            details['区间波动'] = f"{flat_base['base_range_pct']:.2f}%"
            details['突破幅度'] = f"{flat_base['breakout_pct']:.2f}%"
            details['量比'] = f"{flat_base['volume_ratio']:.2f}倍"
            details['缩量程度'] = f"{flat_base['volume_contraction']:.1f}%"
            details['整理天数'] = flat_base['base_days']
            
            # 风控计算
            stop_loss = flat_base['base_low'] * 0.97
            target = flat_base['base_high'] + (flat_base['base_high'] - flat_base['base_low']) * 1.5
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and flat_base is not None:
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [],
                'details': details,
                'risk_management': risk_management
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details if details else None,
                'risk_management': None
            }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='平底形态筛选器（欧奈尔标准）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = FlatBaseScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只平底形态股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 区间{r['base_range_pct']:.1f}%, 突破{r['breakout_pct']:.1f}%")
