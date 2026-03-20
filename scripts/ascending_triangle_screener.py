#!/usr/bin/env python3
"""
上升三角形筛选器 - Ascending Triangle Screener (欧奈尔 CANSLIM)

形态定义：
- 股价形成一系列高点相近的水平阻力线
- 低点逐渐抬高，形成上升支撑线
- 两条线形成向上的三角形
- 突破时成交量放大

技术参数（欧奈尔标准）：
- 整理周期：4-8周（20-40个交易日）
- 至少2个高点相近（±3%）
- 至少2个低点逐渐抬高
- 突破幅度：收盘价突破阻力线3%以上
- 突破成交量：≥1.5倍整理期均量

特点：
- 看涨持续形态
- 显示买方力量逐渐增强
- 通常出现在上升趋势中
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


class AscendingTriangleScreener(BaseScreener):
    """上升三角形筛选器（欧奈尔标准）"""
    
    def __init__(self,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='ascending_triangle',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        # 欧奈尔上升三角形标准参数
        self.min_triangle_days = 20     # 整理期最小20天（4周）
        self.max_triangle_days = 40     # 整理期最大40天（8周）
        self.resistance_tolerance = 0.03  # 阻力线容忍度±3%
        self.min_touches = 2            # 最少触及次数
        self.min_breakout_pct = 0.03    # 突破最小3%
        self.min_volume_ratio = 1.5     # 突破成交量1.5倍
    
    def find_ascending_triangle(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找上升三角形形态
        
        Returns:
            三角形信息或None
        """
        if len(df) < 60:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 从后向前寻找整理区间
        for i in range(len(df) - 1, self.max_triangle_days, -1):
            period = df.iloc[i - self.max_triangle_days:i]
            
            if len(period) < self.min_triangle_days:
                continue
            
            # 寻找高点（阻力线）
            highs = period['high'].nlargest(5).values  # 取最高的5个点
            
            # 检查高点是否接近（形成水平阻力线）
            resistance_price = np.median(highs)
            high_variation = np.max(np.abs(highs - resistance_price)) / resistance_price
            
            if high_variation > self.resistance_tolerance:
                continue
            
            # 寻找低点（支撑线）
            # 寻找至少2个逐渐抬高的低点
            lows_data = []
            for j in range(1, len(period) - 1):
                # 局部低点
                if (period.iloc[j]['low'] < period.iloc[j-1]['low'] and 
                    period.iloc[j]['low'] < period.iloc[j+1]['low']):
                    lows_data.append({
                        'idx': j,
                        'price': period.iloc[j]['low']
                    })
            
            if len(lows_data) < self.min_touches:
                continue
            
            # 检查低点是否逐渐抬高
            ascending = True
            for k in range(1, len(lows_data)):
                if lows_data[k]['price'] <= lows_data[k-1]['price'] * 1.01:  # 允许1%误差
                    ascending = False
                    break
            
            if not ascending:
                continue
            
            # 计算支撑线斜率（应为正）
            support_slope = (lows_data[-1]['price'] - lows_data[0]['price']) / (lows_data[-1]['idx'] - lows_data[0]['idx'])
            if support_slope <= 0:
                continue
            
            # 检查突破
            latest = df.iloc[-1]
            breakout_price = latest['close']
            
            # 收盘价突破阻力线3%以上
            if breakout_price < resistance_price * (1 + self.min_breakout_pct):
                continue
            
            # 检查突破成交量
            period_volume_avg = period['volume'].mean()
            if period_volume_avg > 0 and latest['volume'] < period_volume_avg * self.min_volume_ratio:
                continue
            
            # 计算形态高度（用于目标位）
            lowest_low = period['low'].min()
            triangle_height = resistance_price - lowest_low
            
            return {
                'resistance_price': round(resistance_price, 2),
                'support_start': round(lows_data[0]['price'], 2),
                'support_end': round(lows_data[-1]['price'], 2),
                'support_slope': round(support_slope, 4),
                'high_touches': len(highs),
                'low_touches': len(lows_data),
                'lowest_low': round(lowest_low, 2),
                'triangle_height': round(triangle_height, 2),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - resistance_price) / resistance_price * 100, 2),
                'volume_ratio': round(latest['volume'] / period_volume_avg, 2) if period_volume_avg > 0 else 0,
                'triangle_days': len(period)
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
        
        # 寻找上升三角形
        triangle = self.find_ascending_triangle(df)
        if triangle is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'resistance_price': triangle['resistance_price'],
            'support_slope': triangle['support_slope'],
            'high_touches': triangle['high_touches'],
            'low_touches': triangle['low_touches'],
            'triangle_height': triangle['triangle_height'],
            'breakout_pct': triangle['breakout_pct'],
            'volume_ratio': triangle['volume_ratio'],
            'triangle_days': triangle['triangle_days']
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
        
        # 检查上升三角形
        triangle = self.find_ascending_triangle(df)
        
        if triangle is None:
            reasons.append(f'未找到上升三角形（需满足：整理期{self.min_triangle_days}-{self.max_triangle_days}天、'
                          f'水平阻力线、低点抬高、突破≥{self.min_breakout_pct*100:.0f}%）')
        else:
            details['阻力线价格'] = f"{triangle['resistance_price']:.2f}"
            details['阻力触及次数'] = triangle['high_touches']
            details['支撑触及次数'] = triangle['low_touches']
            details['形态高度'] = f"{triangle['triangle_height']:.2f}"
            details['突破幅度'] = f"{triangle['breakout_pct']:.2f}%"
            details['量比'] = f"{triangle['volume_ratio']:.2f}倍"
            details['整理天数'] = triangle['triangle_days']
            
            # 风控计算
            stop_loss = triangle['support_end'] * 0.97
            target = triangle['resistance_price'] + triangle['triangle_height']  # 等幅上涨
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and triangle is not None:
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
    parser = argparse.ArgumentParser(description='上升三角形筛选器（欧奈尔标准）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = AscendingTriangleScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只上升三角形股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 突破{r['breakout_pct']:.1f}%, 高度{r['triangle_height']:.2f}")
