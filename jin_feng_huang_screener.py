#!/usr/bin/env python3
"""
涨停金凤凰筛选器 - Zhang Ting Jin Feng Huang Screener

策略逻辑：
1. 首板涨停板，放出倍量
2. 次日高开，留缺口，冲高回落
3. 横盘整理3-5天，不跌破涨停最高价，不补缺口
4. 小阴小阳调整，成交量未明显萎缩
5. 出现缩倍量后，放量阳线突破横盘区间

参数可调：
- 横盘天数范围
- 缺口保留要求
- 成交量阈值
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"


class JinFengHuangScreener:
    """涨停金凤凰筛选器"""
    
    def __init__(self, 
                 min_consolidation_days=3,
                 max_consolidation_days=5,
                 max_pullback_pct=0.0,  # 不跌破涨停最高价
                 require_gap=True,
                 volume_shrink_threshold=0.5,  # 缩倍量阈值
                 breakout_volume_ratio=1.5):   # 突破时放量倍数
        """
        初始化筛选器
        
        Args:
            min_consolidation_days: 最小横盘天数
            max_consolidation_days: 最大横盘天数
            max_pullback_pct: 最大回调幅度（相对于涨停最高价）
            require_gap: 是否要求保留缺口
            volume_shrink_threshold: 缩量阈值（相对于涨停当天）
            breakout_volume_ratio: 突破时放量倍数（相对于横盘期均量）
        """
        self.engine = init_db()
        self.session = get_session(self.engine)
        self.min_consolidation_days = min_consolidation_days
        self.max_consolidation_days = max_consolidation_days
        self.max_pullback_pct = max_pullback_pct
        self.require_gap = require_gap
        self.volume_shrink_threshold = volume_shrink_threshold
        self.breakout_volume_ratio = breakout_volume_ratio
        
    def get_stock_data(self, code, days=100):
        """获取股票最近N天的数据"""
        query = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn, params=(code, days))
        conn.close()
        
        if df.empty:
            return None

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df['code'] = code  # ADD THIS LINE - Fix for is_limit_up()
        df = df.sort_values('trade_date').reset_index(drop=True)
        return df
    
    def is_limit_up(self, row, prev_close):
        """判断是否为涨停板（考虑不同板块的涨停幅度）"""
        if prev_close <= 0:
            return False
        
        pct_change = row['pct_change']
        
        # 创业板/科创板 20%
        if row['code'].startswith(('300', '301', '688', '689')):
            return pct_change >= 19.5
        
        # 北交所 30%
        if row['code'].startswith('8'):
            return pct_change >= 29.5
        
        # 主板/ST 10%
        if 'ST' in str(row.get('name', '')):
            return pct_change >= 4.5
        
        return pct_change >= 9.5
    
    def find_limit_up_day(self, df):
        """
        寻找首板涨停板（有一定涨幅后的第一个涨停）
        返回涨停日的索引和前后数据
        """
        if len(df) < 20:
            return None
        
        # 从后往前找，优先找最近的
        for i in range(len(df) - 1, 10, -1):
            row = df.iloc[i]
            prev_close = df.iloc[i-1]['close']
            
            # 检查是否为涨停
            if not self.is_limit_up(row, prev_close):
                continue
            
            # 检查前10天涨幅（确保是上涨趋势中的首板）
            price_10_days_ago = df.iloc[i-10]['close']
            gain_10_days = (prev_close - price_10_days_ago) / price_10_days_ago
            
            # 要求有一定涨幅（10%以上），但不能已经连板
            if gain_10_days < 0.10:
                continue
            
            # 检查前一天是否也是涨停（避免连板）
            if self.is_limit_up(df.iloc[i-1], df.iloc[i-2]['close']):
                continue
            
            return i
        
        return None
    
    def check_gap_and_consolidation(self, df, limit_up_idx):
        """
        检查次日高开缺口和横盘整理
        
        Returns:
            dict or None: 符合条件返回横盘信息，否则None
        """
        if limit_up_idx >= len(df) - 2:
            return None
        
        limit_up_row = df.iloc[limit_up_idx]
        next_day = df.iloc[limit_up_idx + 1]
        
        limit_up_high = limit_up_row['high']
        limit_up_close = limit_up_row['close']
        limit_up_low = limit_up_row['low']
        
        # 次日必须高开（有缺口）
        if next_day['open'] <= limit_up_high:
            return None
        
        gap_low = limit_up_high
        gap_high = next_day['open']
        
        # 次日冲高回落（收盘价低于开盘价）
        if next_day['close'] >= next_day['open']:
            return None
        
        # 寻找横盘区间
        consolidation_days = 0
        max_consolidation_high = next_day['high']
        min_consolidation_low = next_day['low']
        consolidation_volume_sum = next_day['volume']
        
        # 从第3天开始检查横盘
        for i in range(limit_up_idx + 2, min(limit_up_idx + 2 + self.max_consolidation_days, len(df))):
            day_row = df.iloc[i]
            
            # 检查是否跌破涨停最高价
            if day_row['low'] < limit_up_high * (1 - self.max_pullback_pct):
                break
            
            # 检查是否补缺口（如果要求保留缺口）
            if self.require_gap and day_row['low'] <= gap_low:
                break
            
            # 检查是否为小阴小阳（波动不大）
            day_range = (day_row['high'] - day_row['low']) / day_row['close']
            if day_range > 0.05:  # 波动超过5%不算小阴小阳
                break
            
            consolidation_days += 1
            max_consolidation_high = max(max_consolidation_high, day_row['high'])
            min_consolidation_low = min(min_consolidation_low, day_row['low'])
            consolidation_volume_sum += day_row['volume']
        
        # 检查横盘天数
        if consolidation_days < self.min_consolidation_days:
            return None
        
        # 检查是否有缩倍量出现
        shrink_day = None
        for i in range(limit_up_idx + 2, limit_up_idx + 2 + consolidation_days):
            day_row = df.iloc[i]
            if day_row['volume'] < limit_up_row['volume'] * self.volume_shrink_threshold:
                shrink_day = i
                break
        
        # 检查突破
        breakout_day = None
        avg_consolidation_volume = consolidation_volume_sum / (consolidation_days + 1)
        
        for i in range(limit_up_idx + 2 + consolidation_days - 1, min(limit_up_idx + 2 + consolidation_days + 3, len(df))):
            if i >= len(df):
                break
            day_row = df.iloc[i]
            
            # 放量阳线突破横盘区间
            if (day_row['close'] > max_consolidation_high and 
                day_row['close'] > day_row['open'] and
                day_row['volume'] > avg_consolidation_volume * self.breakout_volume_ratio):
                breakout_day = i
                break
        
        return {
            'limit_up_date': limit_up_row['trade_date'].strftime('%Y-%m-%d'),
            'limit_up_price': limit_up_close,
            'limit_up_high': limit_up_high,
            'gap_high': gap_high,
            'gap_low': gap_low,
            'consolidation_days': consolidation_days,
            'consolidation_high': max_consolidation_high,
            'consolidation_low': min_consolidation_low,
            'has_shrink_volume': shrink_day is not None,
            'shrink_day_idx': shrink_day,
            'breakout_day_idx': breakout_day,
            'breakout_date': df.iloc[breakout_day]['trade_date'].strftime('%Y-%m-%d') if breakout_day else None
        }
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code)
        if df is None or len(df) < 30:
            return None
        
        # 寻找首板涨停
        limit_up_idx = self.find_limit_up_day(df)
        if limit_up_idx is None:
            return None
        
        # 检查缺口和横盘
        result = self.check_gap_and_consolidation(df, limit_up_idx)
        if result is None:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        limit_up_row = df.iloc[limit_up_idx]
        
        return {
            'code': code,
            'name': name,
            'limit_up_date': result['limit_up_date'],
            'limit_up_price': result['limit_up_price'],
            'limit_up_high': result['limit_up_high'],
            'gap_high': result['gap_high'],
            'gap_low': result['gap_low'],
            'consolidation_days': result['consolidation_days'],
            'consolidation_high': result['consolidation_high'],
            'consolidation_low': result['consolidation_low'],
            'has_shrink_volume': result['has_shrink_volume'],
            'breakout_date': result['breakout_date'],
            'current_price': latest['close'],
            'current_change': latest['pct_change'],
            'limit_up_volume': limit_up_row['volume'],
            'days_since_limit_up': len(df) - 1 - limit_up_idx
        }
    
    def run_screening(self, date=None):
        """运行筛选"""
        logger.info("="*60)
        logger.info("涨停金凤凰筛选 - Zhang Ting Jin Feng Huang Screener")
        logger.info(f"参数: 横盘{self.min_consolidation_days}-{self.max_consolidation_days}天, "
                   f"缺口保留={self.require_gap}, 缩量阈值={self.volume_shrink_threshold}")
        logger.info("="*60)
        
        # 获取所有股票
        stocks = self.session.query(Stock).all()
        logger.info(f"Total stocks: {len(stocks)}")
        
        results = []
        checked = 0
        
        for stock in stocks:
            # 跳过指数和ST股
            if stock.code.startswith(('399', '000', '899')):
                continue
            if stock.name and ('ST' in stock.name or '退' in stock.name):
                continue
            
            checked += 1
            if checked % 500 == 0:
                logger.info(f"Checked {checked} stocks, found {len(results)} matches")
            
            result = self.screen_stock(stock.code, stock.name)
            if result:
                results.append(result)
                logger.info(f"✓ Found: {stock.code} {stock.name} - "
                           f"涨停于{result['limit_up_date']}, "
                           f"横盘{result['consolidation_days']}天")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Screening complete!")
        logger.info(f"Checked: {checked} stocks")
        logger.info(f"Matches: {len(results)} stocks")
        logger.info(f"{'='*60}")
        
        return results
    
    def save_results(self, results, filename=None):
        """保存结果到Excel"""
        if not results:
            logger.warning("No results to save")
            return
        
        if filename is None:
            filename = f"data/jin_feng_huang_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'current_price', 'current_change',
            'limit_up_date', 'limit_up_price', 'limit_up_high',
            'gap_high', 'gap_low', 'consolidation_days',
            'consolidation_high', 'consolidation_low', 'has_shrink_volume',
            'breakout_date', 'days_since_limit_up', 'limit_up_volume'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '当前价格', '当前涨幅%',
            '涨停日期', '涨停收盘价', '涨停最高价',
            '缺口上沿', '缺口下沿', '横盘天数',
            '横盘高点', '横盘低点', '是否缩倍量',
            '突破日期', '距涨停天数', '涨停成交量'
        ]
        
        df.to_excel(filename, index=False)
        logger.info(f"Results saved to: {filename}")
        return filename


def main():
    parser = argparse.ArgumentParser(description='涨停金凤凰筛选器')
    parser.add_argument('--min-days', type=int, default=3, help='最小横盘天数')
    parser.add_argument('--max-days', type=int, default=5, help='最大横盘天数')
    parser.add_argument('--max-pullback', type=float, default=0.0, help='最大回调幅度(相对于涨停最高价)')
    parser.add_argument('--no-gap', action='store_true', help='不要求保留缺口')
    parser.add_argument('--shrink-threshold', type=float, default=0.5, help='缩量阈值(相对于涨停当天)')
    parser.add_argument('--breakout-ratio', type=float, default=1.5, help='突破时放量倍数')
    parser.add_argument('--output', type=str, help='输出文件名')
    
    args = parser.parse_args()
    
    screener = JinFengHuangScreener(
        min_consolidation_days=args.min_days,
        max_consolidation_days=args.max_days,
        max_pullback_pct=args.max_pullback,
        require_gap=not args.no_gap,
        volume_shrink_threshold=args.shrink_threshold,
        breakout_volume_ratio=args.breakout_ratio
    )
    
    results = screener.run_screening()
    
    if results:
        screener.save_results(results, args.output)
        
        # 打印结果
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            gap_status = "有缺口" if r['gap_high'] > r['gap_low'] else "无缺口"
            shrink_status = "已缩量" if r['has_shrink_volume'] else "未缩量"
            breakout_status = f"突破于{r['breakout_date']}" if r['breakout_date'] else "未突破"
            print(f"{r['code']} {r['name']}: 涨停{r['limit_up_date']}, "
                  f"横盘{r['consolidation_days']}天, {gap_status}, {shrink_status}, {breakout_status}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
