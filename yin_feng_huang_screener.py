#!/usr/bin/env python3
"""
涨停银凤凰筛选器 - Zhang Ting Yin Feng Huang Screener

策略逻辑：
1. 股价上涨初期，出现实体涨停
2. 次日开始回调，不跌破涨停板一半位置（50%）
3. 成交量缩量
4. 回调时间7天内
5. 出现放量阳线或试盘线突破

参数可调：
- 回调时间范围
- 最大回调幅度（相对于涨停价）
- 缩量阈值
- 突破放量倍数
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


class YinFengHuangScreener:
    """涨停银凤凰筛选器"""
    
    def __init__(self, 
                 min_callback_days=2,
                 max_callback_days=7,
                 max_callback_pct=0.50,  # 不跌破涨停价的50%
                 volume_shrink_threshold=0.6,  # 缩量阈值
                 breakout_volume_ratio=1.3,    # 突破时放量倍数
                 min_uptrend_days=5,           # 上涨初期判断天数
                 min_uptrend_gain=0.05):       # 上涨初期最小涨幅
        """
        初始化筛选器
        
        Args:
            min_callback_days: 最小回调天数
            max_callback_days: 最大回调天数（默认7天）
            max_callback_pct: 最大回调幅度（相对于涨停价，默认50%）
            volume_shrink_threshold: 缩量阈值（相对于涨停当天）
            breakout_volume_ratio: 突破时放量倍数（相对于回调期均量）
            min_uptrend_days: 判断上涨初期的天数
            min_uptrend_gain: 上涨初期最小涨幅
        """
        self.engine = init_db()
        self.session = get_session(self.engine)
        self.min_callback_days = min_callback_days
        self.max_callback_days = max_callback_days
        self.max_callback_pct = max_callback_pct
        self.volume_shrink_threshold = volume_shrink_threshold
        self.breakout_volume_ratio = breakout_volume_ratio
        self.min_uptrend_days = min_uptrend_days
        self.min_uptrend_gain = min_uptrend_gain
        
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
        df = df.sort_values('trade_date').reset_index(drop=True)
        df['code'] = code  # ADD THIS LINE - Fix for is_limit_up()
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
    
    def is_early_uptrend(self, df, limit_up_idx):
        """判断是否为上涨初期（有一定涨幅但不过分）"""
        if limit_up_idx < self.min_uptrend_days:
            return False
        
        # 检查涨停前N天的涨幅
        price_n_days_ago = df.iloc[limit_up_idx - self.min_uptrend_days]['close']
        price_before_limit_up = df.iloc[limit_up_idx - 1]['close']
        
        gain = (price_before_limit_up - price_n_days_ago) / price_n_days_ago
        
        # 要求有一定涨幅（上涨初期），但不能已经翻倍（避免高位）
        return self.min_uptrend_gain <= gain <= 0.50
    
    def find_limit_up_day(self, df):
        """
        寻找上涨初期的实体涨停板
        返回涨停日的索引
        """
        if len(df) < 30:
            return None
        
        # 从后往前找
        for i in range(len(df) - 1, self.min_uptrend_days + 1, -1):
            row = df.iloc[i]
            prev_close = df.iloc[i-1]['close']
            
            # 检查是否为涨停
            if not self.is_limit_up(row, prev_close):
                continue
            
            # 检查是否为上涨初期
            if not self.is_early_uptrend(df, i):
                continue
            
            # 检查前一天是否也是涨停（避免连板）
            if i > 1 and self.is_limit_up(df.iloc[i-1], df.iloc[i-2]['close']):
                continue
            
            return i
        
        return None
    
    def check_callback_and_support(self, df, limit_up_idx):
        """
        检查回调阶段是否满足条件
        
        Returns:
            dict or None: 符合条件返回回调信息，否则None
        """
        if limit_up_idx >= len(df) - 2:
            return None
        
        limit_up_row = df.iloc[limit_up_idx]
        limit_up_price = limit_up_row['close']
        limit_up_open = limit_up_row['open']
        
        # 计算支撑位（涨停价的一半）
        support_price = limit_up_price * (1 - self.max_callback_pct)
        
        # 次日开始回调
        callback_start_idx = limit_up_idx + 1
        
        callback_days = 0
        min_price_during_callback = limit_up_price
        max_price_during_callback = limit_up_price
        callback_volume_sum = 0
        has_shrink_volume = False
        
        # 检查回调阶段
        for i in range(callback_start_idx, min(callback_start_idx + self.max_callback_days, len(df))):
            day_row = df.iloc[i]
            
            # 检查是否跌破支撑位
            if day_row['low'] < support_price:
                break
            
            # 记录回调期间数据
            callback_days += 1
            min_price_during_callback = min(min_price_during_callback, day_row['low'])
            max_price_during_callback = max(max_price_during_callback, day_row['high'])
            callback_volume_sum += day_row['volume']
            
            # 检查是否缩量
            if day_row['volume'] < limit_up_row['volume'] * self.volume_shrink_threshold:
                has_shrink_volume = True
            
            # 检查是否出现突破信号（放量阳线）
            if callback_days >= self.min_callback_days:
                avg_callback_volume = callback_volume_sum / callback_days
                
                # 放量阳线突破
                if (day_row['close'] > day_row['open'] and 
                    day_row['volume'] > avg_callback_volume * self.breakout_volume_ratio):
                    
                    return {
                        'limit_up_date': limit_up_row['trade_date'].strftime('%Y-%m-%d'),
                        'limit_up_price': limit_up_price,
                        'limit_up_open': limit_up_open,
                        'support_price': support_price,
                        'callback_days': callback_days,
                        'callback_low': min_price_during_callback,
                        'callback_high': max_price_during_callback,
                        'has_shrink_volume': has_shrink_volume,
                        'breakout_date': day_row['trade_date'].strftime('%Y-%m-%d'),
                        'breakout_price': day_row['close'],
                        'breakout_volume_ratio': day_row['volume'] / avg_callback_volume,
                        'max_callback_pct': (limit_up_price - min_price_during_callback) / limit_up_price * 100
                    }
        
        # 如果回调天数足够但没有突破，也记录下来
        if callback_days >= self.min_callback_days:
            avg_callback_volume = callback_volume_sum / callback_days if callback_days > 0 else 0
            
            return {
                'limit_up_date': limit_up_row['trade_date'].strftime('%Y-%m-%d'),
                'limit_up_price': limit_up_price,
                'limit_up_open': limit_up_open,
                'support_price': support_price,
                'callback_days': callback_days,
                'callback_low': min_price_during_callback,
                'callback_high': max_price_during_callback,
                'has_shrink_volume': has_shrink_volume,
                'breakout_date': None,
                'breakout_price': None,
                'breakout_volume_ratio': None,
                'max_callback_pct': (limit_up_price - min_price_during_callback) / limit_up_price * 100
            }
        
        return None
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code)
        if df is None or len(df) < 30:
            return None
        
        # 寻找上涨初期的涨停
        limit_up_idx = self.find_limit_up_day(df)
        if limit_up_idx is None:
            return None
        
        # 检查回调和支撑
        result = self.check_callback_and_support(df, limit_up_idx)
        if result is None:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        return {
            'code': code,
            'name': name,
            'limit_up_date': result['limit_up_date'],
            'limit_up_price': result['limit_up_price'],
            'support_price': result['support_price'],
            'callback_days': result['callback_days'],
            'callback_low': result['callback_low'],
            'callback_high': result['callback_high'],
            'has_shrink_volume': result['has_shrink_volume'],
            'breakout_date': result['breakout_date'],
            'breakout_price': result['breakout_price'],
            'breakout_volume_ratio': result['breakout_volume_ratio'],
            'max_callback_pct': result['max_callback_pct'],
            'current_price': latest['close'],
            'current_change': latest['pct_change'],
            'days_since_limit_up': len(df) - 1 - limit_up_idx
        }
    
    def run_screening(self, date=None):
        """运行筛选"""
        logger.info("="*60)
        logger.info("涨停银凤凰筛选 - Zhang Ting Yin Feng Huang Screener")
        logger.info(f"参数: 回调{self.min_callback_days}-{self.max_callback_days}天, "
                   f"最大回调{self.max_callback_pct*100:.0f}%, "
                   f"缩量阈值{self.volume_shrink_threshold}")
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
                breakout_status = f"突破于{result['breakout_date']}" if result['breakout_date'] else "未突破"
                logger.info(f"✓ Found: {stock.code} {stock.name} - "
                           f"涨停{result['limit_up_date']}, "
                           f"回调{result['callback_days']}天, {breakout_status}")
        
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
            filename = f"data/yin_feng_huang_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'current_price', 'current_change',
            'limit_up_date', 'limit_up_price', 'support_price',
            'callback_days', 'callback_low', 'callback_high',
            'has_shrink_volume', 'max_callback_pct',
            'breakout_date', 'breakout_price', 'breakout_volume_ratio',
            'days_since_limit_up'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '当前价格', '当前涨幅%',
            '涨停日期', '涨停收盘价', '支撑位价格',
            '回调天数', '回调低点', '回调高点',
            '是否缩量', '最大回调%',
            '突破日期', '突破价格', '突破放量倍数',
            '距涨停天数'
        ]
        
        df.to_excel(filename, index=False)
        logger.info(f"Results saved to: {filename}")
        return filename


def main():
    parser = argparse.ArgumentParser(description='涨停银凤凰筛选器')
    parser.add_argument('--min-days', type=int, default=2, help='最小回调天数')
    parser.add_argument('--max-days', type=int, default=7, help='最大回调天数')
    parser.add_argument('--max-callback', type=float, default=0.50, help='最大回调幅度(相对于涨停价,默认0.5=50%)')
    parser.add_argument('--shrink-threshold', type=float, default=0.6, help='缩量阈值(相对于涨停当天)')
    parser.add_argument('--breakout-ratio', type=float, default=1.3, help='突破时放量倍数')
    parser.add_argument('--output', type=str, help='输出文件名')
    
    args = parser.parse_args()
    
    screener = YinFengHuangScreener(
        min_callback_days=args.min_days,
        max_callback_days=args.max_days,
        max_callback_pct=args.max_callback,
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
            shrink_status = "已缩量" if r['has_shrink_volume'] else "未缩量"
            breakout_status = f"突破于{r['breakout_date']}@{r['breakout_price']:.2f}" if r['breakout_date'] else "未突破"
            print(f"{r['code']} {r['name']}: 涨停{r['limit_up_date']}, "
                  f"回调{r['callback_days']}天, 最大回调{r['max_callback_pct']:.1f}%, "
                  f"{shrink_status}, {breakout_status}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
