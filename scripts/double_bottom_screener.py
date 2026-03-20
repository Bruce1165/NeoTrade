#!/usr/bin/env python3
"""
双底形态筛选器 - Double Bottom Screener (欧奈尔 CANSLIM)

形态定义：
- 股价下跌后形成第一个底部（左底）
- 反弹至颈线后再次回调
- 形成第二个底部（右底），与左底价格接近（±5%）
- 放量突破颈线确认形态完成

技术参数（欧奈尔标准）：
- 底部之间时间间隔：3-6周
- 两个低点价格差：≤5%
- 颈线突破：收盘价突破颈线3%以上
- 突破成交量：≥1.5倍20日均量
- 底部分别需要有明显的缩量特征
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


class DoubleBottomScreener(BaseScreener):
    """双底形态筛选器（欧奈尔标准）"""
    
    def __init__(self,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='double_bottom',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        # 欧奈尔双底标准参数
        self.min_bottom_days = 15      # 两个底部最小间隔15天（3周）
        self.max_bottom_days = 45      # 两个底部最大间隔45天（6周）
        self.max_price_diff = 0.05     # 两个低点最大价差5%
        self.min_breakout_pct = 0.03   # 突破颈线最小3%
        self.min_volume_ratio = 1.5    # 突破成交量1.5倍
    
    def find_double_bottom(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找双底形态
        
        Returns:
            双底信息或None
        """
        if len(df) < 60:  # 需要足够的历史数据
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 寻找局部低点（谷值）
        lows = []
        for i in range(2, len(df) - 2):
            # 当前点是局部低点
            if (df.iloc[i]['low'] < df.iloc[i-1]['low'] and 
                df.iloc[i]['low'] < df.iloc[i-2]['low'] and
                df.iloc[i]['low'] < df.iloc[i+1]['low'] and
                df.iloc[i]['low'] < df.iloc[i+2]['low']):
                lows.append({
                    'index': i,
                    'date': df.iloc[i]['trade_date'],
                    'price': df.iloc[i]['low'],
                    'close': df.iloc[i]['close']
                })
        
        if len(lows) < 2:
            return None
        
        # 寻找双底对
        for i in range(len(lows) - 1):
            left_bottom = lows[i]
            
            for j in range(i + 1, len(lows)):
                right_bottom = lows[j]
                
                # 检查时间间隔
                days_between = right_bottom['index'] - left_bottom['index']
                if not (self.min_bottom_days <= days_between <= self.max_bottom_days):
                    continue
                
                # 检查价格接近度
                price_diff = abs(right_bottom['price'] - left_bottom['price']) / left_bottom['price']
                if price_diff > self.max_price_diff:
                    continue
                
                # 寻找颈线（两个底部之间的最高点）
                middle_period = df.iloc[left_bottom['index']:right_bottom['index']]
                if len(middle_period) < 5:
                    continue
                
                neck_price = middle_period['high'].max()
                
                # 检查颈线是否明显高于两个底部
                avg_bottom = (left_bottom['price'] + right_bottom['price']) / 2
                if neck_price < avg_bottom * 1.05:  # 颈线应至少高于底部5%
                    continue
                
                # 检查突破
                after_right = df.iloc[right_bottom['index'] + 1:]
                if len(after_right) < 1:
                    continue
                
                latest = df.iloc[-1]
                breakout_price = latest['close']
                
                # 收盘价突破颈线3%以上
                if breakout_price < neck_price * (1 + self.min_breakout_pct):
                    continue
                
                # 检查突破成交量
                avg_volume_20 = df.iloc[-20:]['volume'].mean()
                if avg_volume_20 > 0 and latest['volume'] < avg_volume_20 * self.min_volume_ratio:
                    continue
                
                # 检查双底期间的缩量特征
                left_volume_avg = df.iloc[max(0, left_bottom['index']-5):left_bottom['index']]['volume'].mean()
                right_volume_avg = df.iloc[max(0, right_bottom['index']-5):right_bottom['index']]['volume'].mean()
                
                return {
                    'left_bottom_date': str(left_bottom['date']),
                    'left_bottom_price': round(left_bottom['price'], 2),
                    'right_bottom_date': str(right_bottom['date']),
                    'right_bottom_price': round(right_bottom['price'], 2),
                    'neck_price': round(neck_price, 2),
                    'breakout_price': round(breakout_price, 2),
                    'breakout_pct': round((breakout_price - neck_price) / neck_price * 100, 2),
                    'price_diff_pct': round(price_diff * 100, 2),
                    'days_between': days_between,
                    'volume_ratio': round(latest['volume'] / avg_volume_20, 2) if avg_volume_20 > 0 else 0
                }
        
        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=120)
        if df is None or len(df) < 60:
            return None
        
        yesterday = df.iloc[-1]
        
        # 基础条件：涨幅 > 2%
        if yesterday.get('pct_change', 0) < 2.0:
            return None
        
        # 寻找双底形态
        double_bottom = self.find_double_bottom(df)
        if double_bottom is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'left_bottom_date': double_bottom['left_bottom_date'],
            'left_bottom_price': double_bottom['left_bottom_price'],
            'right_bottom_date': double_bottom['right_bottom_date'],
            'right_bottom_price': double_bottom['right_bottom_price'],
            'neck_price': double_bottom['neck_price'],
            'breakout_pct': double_bottom['breakout_pct'],
            'price_diff_pct': double_bottom['price_diff_pct'],
            'days_between': double_bottom['days_between'],
            'volume_ratio': double_bottom['volume_ratio']
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
        
        df = self.get_stock_data(code, days=120)
        if df is None or len(df) < 60:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少60天）']
            }
        
        yesterday = df.iloc[-1]
        
        # 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2.0:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < 2%')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 检查双底形态
        double_bottom = self.find_double_bottom(df)
        
        if double_bottom is None:
            reasons.append(f'未找到双底形态（需满足：底部间隔{self.min_bottom_days}-{self.max_bottom_days}天、'
                          f'价格差≤{self.max_price_diff*100:.0f}%、突破颈线≥{self.min_breakout_pct*100:.0f}%）')
        else:
            details['左底日期'] = double_bottom['left_bottom_date']
            details['左底价格'] = f"{double_bottom['left_bottom_price']:.2f}"
            details['右底日期'] = double_bottom['right_bottom_date']
            details['右底价格'] = f"{double_bottom['right_bottom_price']:.2f}"
            details['颈线价格'] = f"{double_bottom['neck_price']:.2f}"
            details['双底价差'] = f"{double_bottom['price_diff_pct']:.2f}%"
            details['间隔天数'] = double_bottom['days_between']
            details['突破幅度'] = f"{double_bottom['breakout_pct']:.2f}%"
            details['量比'] = f"{double_bottom['volume_ratio']:.2f}倍"
            
            # 风控计算
            stop_loss = double_bottom['right_bottom_price'] * 0.97
            target = double_bottom['neck_price'] + (double_bottom['neck_price'] - double_bottom['right_bottom_price'])
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and double_bottom is not None:
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
    parser = argparse.ArgumentParser(description='双底形态筛选器（欧奈尔标准）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = DoubleBottomScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只双底形态股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 突破{r['breakout_pct']:.1f}%")
