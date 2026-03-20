#!/usr/bin/env python3
"""
高紧旗形筛选器 - High Tight Flag Screener (欧奈尔 CANSLIM)

欧奈尔最喜欢的形态之一！

形态定义：
- 股价在短期内（3-6周）快速上涨 100%+（旗杆）
- 随后进入紧凑的、小幅回调的整理阶段（旗面）
- 整理幅度通常只有 10%-25%
- 整理期间成交量明显萎缩
- 突破时放量继续上攻

技术参数（欧奈尔标准）：
- 旗杆涨幅：≥100%（3-6周内翻倍）
- 旗面回调：10%-25%
- 旗面周期：2-4周
- 突破成交量：≥1.5倍旗面均量
- 整体形态紧凑，不松散

特点：
- 强势股的标志
- 通常出现在行业龙头股上
- 突破后涨幅可观
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


class HighTightFlagScreener(BaseScreener):
    """高紧旗形筛选器（欧奈尔最喜爱的形态）"""
    
    def __init__(self,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='high_tight_flag',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        # 欧奈尔高紧旗形标准参数
        self.pole_min_gain = 1.00      # 旗杆最小涨幅100%
        self.pole_max_days = 45        # 旗杆最大周期45天（6周）
        self.flag_max_retrace = 0.25   # 旗面最大回调25%
        self.flag_min_retrace = 0.10   # 旗面最小回调10%
        self.flag_max_days = 28        # 旗面最大周期28天（4周）
        self.flag_min_days = 10        # 旗面最小周期10天（2周）
        self.min_volume_ratio = 1.5    # 突破成交量1.5倍
    
    def find_high_tight_flag(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找高紧旗形形态
        
        Returns:
            旗形信息或None
        """
        if len(df) < 80:  # 需要足够的历史数据
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        latest = df.iloc[-1]
        
        # 从后向前寻找旗面整理期
        for flag_end_idx in range(len(df) - 1, self.flag_max_days + 10, -1):
            flag_start_idx = max(flag_end_idx - self.flag_max_days, flag_end_idx - self.flag_min_days)
            
            if flag_start_idx < 10:
                continue
            
            flag_period = df.iloc[flag_start_idx:flag_end_idx]
            
            if len(flag_period) < self.flag_min_days:
                continue
            
            flag_high = flag_period['high'].max()
            flag_low = flag_period['low'].min()
            
            # 检查旗面回调幅度
            flag_retrace = (flag_high - flag_low) / flag_high
            if not (self.flag_min_retrace <= flag_retrace <= self.flag_max_retrace):
                continue
            
            # 寻找旗杆起点（旗面前的高点）
            pole_period = df.iloc[max(0, flag_start_idx - self.pole_max_days):flag_start_idx]
            
            if len(pole_period) < 10:
                continue
            
            pole_start_price = pole_period.iloc[:5]['close'].mean()  # 旗杆起点均价
            pole_end_price = flag_high  # 旗杆终点即旗面高点
            
            # 检查旗杆涨幅
            pole_gain = (pole_end_price - pole_start_price) / pole_start_price
            if pole_gain < self.pole_min_gain:
                continue
            
            # 检查旗面成交量（应萎缩）
            pole_volume_avg = pole_period['volume'].mean()
            flag_volume_avg = flag_period['volume'].mean()
            
            if pole_volume_avg > 0:
                volume_contraction = flag_volume_avg / pole_volume_avg
                if volume_contraction > 0.70:  # 旗面成交量应明显小于旗杆
                    continue
            
            # 检查突破
            breakout_price = latest['close']
            
            # 收盘价突破旗面高点
            if breakout_price <= flag_high * 1.01:
                continue
            
            # 检查突破成交量
            if flag_volume_avg > 0 and latest['volume'] < flag_volume_avg * self.min_volume_ratio:
                continue
            
            # 计算旗面紧凑度（标准差/均值）
            flag_range_pct = flag_period['close'].std() / flag_period['close'].mean()
            
            return {
                'pole_start_price': round(pole_start_price, 2),
                'pole_end_price': round(pole_end_price, 2),
                'pole_gain': round(pole_gain * 100, 1),
                'pole_days': len(pole_period),
                'flag_high': round(flag_high, 2),
                'flag_low': round(flag_low, 2),
                'flag_retrace': round(flag_retrace * 100, 1),
                'flag_days': len(flag_period),
                'volume_contraction': round(volume_contraction * 100, 1),
                'flag_tightness': round(flag_range_pct * 100, 2),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - flag_high) / flag_high * 100, 2)
            }
        
        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=100)
        if df is None or len(df) < 80:
            return None
        
        yesterday = df.iloc[-1]
        
        # 基础条件
        if yesterday.get('pct_change', 0) < 2.0:
            return None
        
        # 寻找高紧旗形
        flag_pattern = self.find_high_tight_flag(df)
        if flag_pattern is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'pole_gain': flag_pattern['pole_gain'],
            'pole_days': flag_pattern['pole_days'],
            'flag_retrace': flag_pattern['flag_retrace'],
            'flag_days': flag_pattern['flag_days'],
            'volume_contraction': flag_pattern['volume_contraction'],
            'breakout_pct': flag_pattern['breakout_pct']
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
        
        df = self.get_stock_data(code, days=100)
        if df is None or len(df) < 80:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少80天）']
            }
        
        yesterday = df.iloc[-1]
        
        # 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2.0:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < 2%')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 检查高紧旗形
        flag_pattern = self.find_high_tight_flag(df)
        
        if flag_pattern is None:
            reasons.append(f'未找到高紧旗形（需满足：旗杆翻倍{self.pole_min_gain*100:.0f}%+、'
                          f'旗面回调{self.flag_min_retrace*100:.0f}%-{self.flag_max_retrace*100:.0f}%、'
                          f'旗面紧凑）')
        else:
            details['旗杆涨幅'] = f"{flag_pattern['pole_gain']:.1f}%"
            details['旗杆天数'] = flag_pattern['pole_days']
            details['旗面回调'] = f"{flag_pattern['flag_retrace']:.1f}%"
            details['旗面天数'] = flag_pattern['flag_days']
            details['旗面缩量'] = f"{flag_pattern['volume_contraction']:.1f}%"
            details['突破幅度'] = f"{flag_pattern['breakout_pct']:.2f}%"
            
            # 风控计算（高紧旗形通常更激进）
            stop_loss = flag_pattern['flag_low'] * 0.95  # 5%止损
            target = flag_pattern['pole_end_price'] + (flag_pattern['pole_end_price'] - flag_pattern['pole_start_price']) * 0.5
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and flag_pattern is not None:
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
    parser = argparse.ArgumentParser(description='高紧旗形筛选器（欧奈尔最喜爱的形态）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = HighTightFlagScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只高紧旗形股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 旗杆{r['pole_gain']:.0f}%, 旗面{r['flag_retrace']:.0f}%")
