#!/usr/bin/env python3
"""
20天突破策略筛选器 - 20-Day Breakout Screener

策略逻辑：
1. 横盘箱体 ≥ 7天
2. 突破前高/箱体上沿/年线
3. 突破日成交量 ≥ 近5日均量的1.5-2倍（不能超3倍）
4. 收盘站稳突破位上方，中阳/大阳
5. 所属板块当天强于大盘（可选）

出场信号（监控）：
- 收盘跌破突破位
- 放量长上影
- 高位高换手不涨停
- 利好兑现高开低走

参数可调：
- 横盘天数
- 放量倍数范围
- 突破类型
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)


class Breakout20DayScreener(BaseScreener):
    """20天突破策略筛选器"""
    
    def __init__(self,
                 consolidation_days: int = 7,      # 横盘天数
                 volume_breakout_min: float = 1.5,  # 最小放量倍数
                 volume_breakout_max: float = 2.0,  # 最大放量倍数（防假突破）
                 min_breakout_pct: float = 3.0,     # 最小突破涨幅
                 max_breakout_pct: float = 7.0,     # 最大突破涨幅（防追高）
                 lookback_days: int = 20,           # 回看周期
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        """
        初始化筛选器
        
        Args:
            consolidation_days: 横盘整理天数（默认7天）
            volume_breakout_min: 最小放量倍数（默认1.5）
            volume_breakout_max: 最大放量倍数（默认2.0，防暴量假突破）
            min_breakout_pct: 最小突破涨幅（默认3%）
            max_breakout_pct: 最大突破涨幅（默认7%，防追高）
            lookback_days: 回看周期（默认20天）
        """
        super().__init__(
            screener_name='breakout_20day',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        self.consolidation_days = consolidation_days
        self.volume_breakout_min = volume_breakout_min
        self.volume_breakout_max = volume_breakout_max
        self.min_breakout_pct = min_breakout_pct
        self.max_breakout_pct = max_breakout_pct
        self.lookback_days = lookback_days
    
    def find_consolidation_and_breakout(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找横盘整理后的突破
        
        Returns:
            突破信息或None
        """
        if len(df) < self.consolidation_days + 5:
            return None
        
        # 获取最新数据（昨天）
        latest = df.iloc[-1]
        latest_price = latest['close']
        latest_high = latest['high']
        latest_low = latest['low']
        latest_volume = latest['volume']
        latest_pct_change = latest.get('pct_change', 0) or 0
        
        # 检查涨幅是否在合理范围（3%-7%，防追高）
        if not (self.min_breakout_pct <= latest_pct_change <= self.max_breakout_pct):
            return None
        
        # 检查K线实体（中阳/大阳）
        body_pct = abs(latest['close'] - latest['open']) / latest['open'] * 100
        if body_pct < 2:  # 实体太小
            return None
        
        # 检查是否阳线
        if latest['close'] <= latest['open']:
            return None
        
        # 获取横盘期数据（前N天）
        consolidation_period = df.iloc[-self.consolidation_days-1:-1]
        
        if len(consolidation_period) < self.consolidation_days:
            return None
        
        # 计算横盘期高点（箱体上沿/前高）
        consolidation_high = consolidation_period['high'].max()
        consolidation_low = consolidation_period['low'].min()
        consolidation_close_high = consolidation_period['close'].max()
        
        # 检查是否突破箱体上沿
        if latest_price <= consolidation_high * 1.01:  # 需要突破1%以上
            return None
        
        # 检查横盘期波动幅度（确认是横盘不是趋势）
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
        if consolidation_range > 0.15:  # 波动太大不算横盘
            return None
        
        # 计算成交量条件
        avg_volume_5 = df.iloc[-6:-1]['volume'].mean()  # 近5日均量
        volume_ratio = latest_volume / avg_volume_5 if avg_volume_5 > 0 else 0
        
        # 检查放量倍数（1.5-2倍，不能超3倍防假突破）
        if not (self.volume_breakout_min <= volume_ratio <= self.volume_breakout_max):
            return None
        
        # 检查是否站稳突破位上方（收盘不破）
        if latest_price < consolidation_high:
            return None
        
        # 计算突破质量
        breakout_quality = (latest_price - consolidation_high) / consolidation_high * 100
        
        return {
            'consolidation_high': round(consolidation_high, 2),
            'consolidation_low': round(consolidation_low, 2),
            'consolidation_range_pct': round(consolidation_range * 100, 2),
            'breakout_price': round(latest_price, 2),
            'breakout_high': round(latest_high, 2),
            'breakout_low': round(latest_low, 2),
            'breakout_pct': round(latest_pct_change, 2),
            'body_pct': round(body_pct, 2),
            'volume_ratio': round(volume_ratio, 2),
            'avg_volume_5': int(avg_volume_5),
            'breakout_quality': round(breakout_quality, 2),
            'consolidation_days': self.consolidation_days
        }
    
    def check_ma_trend(self, df: pd.DataFrame) -> Dict:
        """检查均线趋势"""
        if len(df) < 20:
            return {'ma5': 0, 'ma10': 0, 'ma20': 0, 'trend': 'unknown'}
        
        ma5 = df.iloc[-5:]['close'].mean()
        ma10 = df.iloc[-10:]['close'].mean()
        ma20 = df.iloc[-20:]['close'].mean()
        
        # 判断趋势
        if ma5 > ma10 > ma20:
            trend = 'bullish'
        elif ma5 < ma10 < ma20:
            trend = 'bearish'
        else:
            trend = 'mixed'
        
        return {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'trend': trend
        }
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.lookback_days + 10)
        if df is None or len(df) < self.lookback_days:
            return None
        
        df['code'] = code
        
        # 寻找横盘突破
        breakout_info = self.find_consolidation_and_breakout(df)
        if breakout_info is None:
            return None
        
        # 检查均线趋势
        ma_info = self.check_ma_trend(df)
        
        # 排除空头排列（只做顺势）
        if ma_info['trend'] == 'bearish':
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(breakout_info['breakout_price'], 2),
            'current_price': round(breakout_info['breakout_price'], 2),
            'pct_change': breakout_info['breakout_pct'],
            'turnover': round(df.iloc[-1].get('turnover', 0) or 0, 2),
            'consolidation_high': breakout_info['consolidation_high'],
            'consolidation_low': breakout_info['consolidation_low'],
            'consolidation_range_pct': breakout_info['consolidation_range_pct'],
            'breakout_high': breakout_info['breakout_high'],
            'breakout_low': breakout_info['breakout_low'],
            'breakout_pct': breakout_info['breakout_pct'],
            'body_pct': breakout_info['body_pct'],
            'volume_ratio': breakout_info['volume_ratio'],
            'avg_volume_5': breakout_info['avg_volume_5'],
            'breakout_quality': breakout_info['breakout_quality'],
            'consolidation_days': breakout_info['consolidation_days'],
            'ma5': ma_info['ma5'],
            'ma10': ma_info['ma10'],
            'ma20': ma_info['ma20'],
            'ma_trend': ma_info['trend']
        }
    
    def save_results(self, results: List[Dict], 
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'close': '收盘价',
            'current_price': '当前价格',
            'pct_change': '涨幅%',
            'turnover': '换手率%',
            'consolidation_high': '箱体上沿',
            'consolidation_low': '箱体下沿',
            'consolidation_range_pct': '箱体波动%',
            'breakout_high': '突破最高价',
            'breakout_low': '突破最低价',
            'breakout_pct': '突破涨幅%',
            'body_pct': 'K线实体%',
            'volume_ratio': '放量倍数',
            'avg_volume_5': '5日均量',
            'breakout_quality': '突破质量%',
            'consolidation_days': '横盘天数',
            'ma5': 'MA5',
            'ma10': 'MA10',
            'ma20': 'MA20',
            'ma_trend': '均线趋势'
        }
        
        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='20天突破策略筛选器')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--consolidation-days', type=int, default=7, help='横盘天数（默认7）')
    parser.add_argument('--volume-min', type=float, default=1.5, help='最小放量倍数（默认1.5）')
    parser.add_argument('--volume-max', type=float, default=2.0, help='最大放量倍数（默认2.0）')
    parser.add_argument('--breakout-min', type=float, default=3.0, help='最小突破涨幅（默认3%）')
    parser.add_argument('--breakout-max', type=float, default=7.0, help='最大突破涨幅（默认7%）')
    parser.add_argument('--lookback', type=int, default=20, help='回看周期（默认20天）')
    parser.add_argument('--no-news', action='store_true', help='禁用新闻抓取')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM分析')
    parser.add_argument('--no-progress', action='store_true', help='禁用进度跟踪')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    screener = Breakout20DayScreener(
        consolidation_days=args.consolidation_days,
        volume_breakout_min=args.volume_min,
        volume_breakout_max=args.volume_max,
        min_breakout_pct=args.breakout_min,
        max_breakout_pct=args.breakout_max,
        lookback_days=args.lookback,
        db_path=args.db_path,
        enable_news=False,  # 禁用新闻
        enable_llm=False,   # 禁用LLM
        enable_progress=not args.no_progress
    )
    
    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=False  # 禁用LLM分析
    )
    
    # Handle different return formats
    if result is None:
        results, analysis_data = [], {}
    elif isinstance(result, tuple) and len(result) == 2:
        results, analysis_data = result
    else:
        results, analysis_data = result, {}
    
    if results:
        output_path = screener.save_results(results, analysis_data)
        print(f"\n结果已保存至: {output_path}")
        
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            trend_icon = "📈" if r['ma_trend'] == 'bullish' else "➡️"
            print(f"{r['code']} {r['name']}: 突破{r['breakout_pct']:.1f}%, "
                  f"放量{r['volume_ratio']:.1f}x, 箱体{r['consolidation_range_pct']:.1f}%, "
                  f"{trend_icon} {r['ma_trend']}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'breakout_20day_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
