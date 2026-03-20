#!/usr/bin/env python3
"""
涨停试盘线筛选器 - Zhang Ting Shi Pan Xian Screener

策略逻辑：
1. 低位横盘阶段，出现高量阳线（近期最大量）— 主力吸筹
2. 随后出现涨停，成交量低于高量阳线 — 快速脱离成本区
3. 回调过程中，股价在涨停板区间内波动
4. 成交量逐步缩量到高量柱的1/4以下 — 抛压很轻
5. 再次出现放量 — 买入信号

参数可调：
- 横盘阶段判断
- 高量阳线判断周期
- 缩量阈值
- 涨停板区间波动范围
"""

# 清除代理环境变量，避免网络请求失败
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
from sqlalchemy import create_engine
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"


class ShiPanXianScreener:
    """涨停试盘线筛选器"""
    
    def __init__(self, 
                 db_path=None,
                 consolidation_days=20,       # 低位横盘判断天数
                 high_volume_lookback=30,      # 高量阳线回看周期
                 max_consolidation_gain=0.10,  # 横盘期最大涨幅
                 volume_shrink_threshold=0.25, # 缩量阈值（高量的1/4）
                 callback_max_days=10,         # 最大回调天数
                 breakout_volume_ratio=1.5):   # 再次放量倍数
        """
        初始化筛选器
        
        Args:
            db_path: 数据库路径
            consolidation_days: 低位横盘判断天数
            high_volume_lookback: 高量阳线回看周期
            max_consolidation_gain: 横盘期最大涨幅
            volume_shrink_threshold: 缩量阈值（相对于高量阳线）
            callback_max_days: 最大回调天数
            breakout_volume_ratio: 再次放量倍数（相对于缩量期均量）
        """
        actual_db_path = db_path or DB_PATH
        self.engine = create_engine(f'sqlite:///{actual_db_path}', echo=False)
        init_db(self.engine)
        self.session = get_session(self.engine)
        self.consolidation_days = consolidation_days
        self.high_volume_lookback = high_volume_lookback
        self.max_consolidation_gain = max_consolidation_gain
        self.volume_shrink_threshold = volume_shrink_threshold
        self.callback_max_days = callback_max_days
        self.breakout_volume_ratio = breakout_volume_ratio
        
    def get_stock_data(self, code, days=150):
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
    
    def is_low_consolidation(self, df, high_volume_idx):
        """判断是否为低位横盘阶段"""
        if high_volume_idx < self.consolidation_days:
            return False
        
        # 检查高量阳线前N天的价格波动
        consolidation_period = df.iloc[high_volume_idx - self.consolidation_days:high_volume_idx]
        
        if len(consolidation_period) < self.consolidation_days:
            return False
        
        price_start = consolidation_period.iloc[0]['close']
        price_end = consolidation_period.iloc[-1]['close']
        
        # 横盘期涨幅不能超过阈值
        gain = (price_end - price_start) / price_start
        
        return abs(gain) <= self.max_consolidation_gain
    
    def find_high_volume_yang_line(self, df):
        """
        寻找低位横盘后的高量阳线
        返回高量阳线的索引
        """
        if len(df) < self.high_volume_lookback + 10:
            return None
        
        # 从后往前找
        for i in range(len(df) - 5, self.consolidation_days, -1):
            row = df.iloc[i]
            
            # 必须是阳线（收盘>开盘）
            if row['close'] <= row['open']:
                continue
            
            # 检查是否为回看周期内的最大成交量
            lookback_period = df.iloc[max(0, i - self.high_volume_lookback):i]
            if len(lookback_period) == 0:
                continue
            
            max_volume_in_period = lookback_period['volume'].max()
            
            # 当前成交量必须是近期最大
            if row['volume'] < max_volume_in_period * 0.95:  # 允许5%误差
                continue
            
            # 检查是否为低位横盘
            if not self.is_low_consolidation(df, i):
                continue
            
            return i
        
        return None
    
    def check_limit_up_and_callback(self, df, high_volume_idx):
        """
        检查随后的涨停和回调阶段
        
        Returns:
            dict or None: 符合条件返回信息，否则None
        """
        if high_volume_idx >= len(df) - 3:
            return None
        
        high_volume_row = df.iloc[high_volume_idx]
        high_volume_price = high_volume_row['close']
        high_volume = high_volume_row['volume']
        
        # 寻找随后的涨停（在接下来5天内）
        limit_up_idx = None
        for i in range(high_volume_idx + 1, min(high_volume_idx + 6, len(df))):
            row = df.iloc[i]
            prev_close = df.iloc[i-1]['close']
            
            if self.is_limit_up(row, prev_close):
                # 涨停成交量必须低于高量阳线
                if row['volume'] < high_volume:
                    limit_up_idx = i
                    break
        
        if limit_up_idx is None:
            return None
        
        limit_up_row = df.iloc[limit_up_idx]
        limit_up_high = limit_up_row['high']
        limit_up_low = limit_up_row['low']
        
        # 回调阶段检查
        callback_start = limit_up_idx + 1
        shrink_volume_found = False
        shrink_volume_idx = None
        min_volume_during_callback = float('inf')
        
        for i in range(callback_start, min(callback_start + self.callback_max_days, len(df))):
            day_row = df.iloc[i]
            
            # 检查股价是否在涨停板区间内
            if day_row['low'] < limit_up_low or day_row['high'] > limit_up_high:
                break
            
            # 记录最小成交量
            if day_row['volume'] < min_volume_during_callback:
                min_volume_during_callback = day_row['volume']
            
            # 检查是否缩量到高量的1/4以下
            if day_row['volume'] < high_volume * self.volume_shrink_threshold:
                shrink_volume_found = True
                shrink_volume_idx = i
            
            # 检查是否出现再次放量（买入信号）
            if shrink_volume_found and i > shrink_volume_idx:
                # 计算缩量期平均成交量
                shrink_period = df.iloc[shrink_volume_idx:i]
                if len(shrink_period) > 0:
                    avg_shrink_volume = shrink_period['volume'].mean()
                    
                    if day_row['volume'] > avg_shrink_volume * self.breakout_volume_ratio:
                        return {
                            'high_volume_date': high_volume_row['trade_date'].strftime('%Y-%m-%d'),
                            'high_volume_price': high_volume_price,
                            'high_volume': high_volume,
                            'limit_up_date': limit_up_row['trade_date'].strftime('%Y-%m-%d'),
                            'limit_up_price': limit_up_row['close'],
                            'limit_up_high': limit_up_high,
                            'limit_up_low': limit_up_low,
                            'limit_up_volume': limit_up_row['volume'],
                            'callback_days': i - limit_up_idx,
                            'shrink_volume_found': True,
                            'shrink_volume_idx': shrink_volume_idx,
                            'min_volume_during_callback': min_volume_during_callback,
                            'breakout_date': day_row['trade_date'].strftime('%Y-%m-%d'),
                            'breakout_price': day_row['close'],
                            'breakout_volume': day_row['volume'],
                            'volume_shrink_ratio': min_volume_during_callback / high_volume
                        }
        
        # 如果找到缩量但未突破，也记录下来
        if shrink_volume_found:
            return {
                'high_volume_date': high_volume_row['trade_date'].strftime('%Y-%m-%d'),
                'high_volume_price': high_volume_price,
                'high_volume': high_volume,
                'limit_up_date': limit_up_row['trade_date'].strftime('%Y-%m-%d'),
                'limit_up_price': limit_up_row['close'],
                'limit_up_high': limit_up_high,
                'limit_up_low': limit_up_low,
                'limit_up_volume': limit_up_row['volume'],
                'callback_days': len(df) - limit_up_idx - 1,
                'shrink_volume_found': True,
                'shrink_volume_idx': shrink_volume_idx,
                'min_volume_during_callback': min_volume_during_callback,
                'breakout_date': None,
                'breakout_price': None,
                'breakout_volume': None,
                'volume_shrink_ratio': min_volume_during_callback / high_volume
            }
        
        return None
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code)
        if df is None or len(df) < 50:
            return None
        
        # 寻找高量阳线
        high_volume_idx = self.find_high_volume_yang_line(df)
        if high_volume_idx is None:
            return None
        
        # 检查涨停和回调
        result = self.check_limit_up_and_callback(df, high_volume_idx)
        if result is None:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        return {
            'code': code,
            'name': name,
            'high_volume_date': result['high_volume_date'],
            'high_volume_price': result['high_volume_price'],
            'high_volume': result['high_volume'],
            'limit_up_date': result['limit_up_date'],
            'limit_up_price': result['limit_up_price'],
            'limit_up_high': result['limit_up_high'],
            'limit_up_low': result['limit_up_low'],
            'limit_up_volume': result['limit_up_volume'],
            'callback_days': result['callback_days'],
            'shrink_volume_found': result['shrink_volume_found'],
            'min_volume_during_callback': result['min_volume_during_callback'],
            'volume_shrink_ratio': result['volume_shrink_ratio'],
            'breakout_date': result['breakout_date'],
            'breakout_price': result['breakout_price'],
            'breakout_volume': result['breakout_volume'],
            'current_price': latest['close'],
            'current_change': latest['pct_change'],
            'days_since_limit_up': len(df) - 1 - high_volume_idx
        }
    
    def run_screening(self, date=None):
        """运行筛选"""
        if date_str:
            self.current_date = date_str
        
        # 检查数据是否可用
        if not self.check_data_availability(self.current_date):
            logger.warning(f"⚠️  无可用数据 ({self.current_date}) - 市场尚未收盘或数据未下载")
            return [{
                'code': 'STATUS',
                'name': 'No Data',
                'message': f'无可用数据 ({self.current_date})，市场尚未收盘或数据未下载',
                'error': 'no_data'
            }]
        logger.info("="*60)
        logger.info("涨停试盘线筛选 - Zhang Ting Shi Pan Xian Screener")
        logger.info(f"参数: 横盘{self.consolidation_days}天, "
                   f"缩量阈值{self.volume_shrink_threshold}, "
                   f"最大回调{self.callback_max_days}天")
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
                           f"高量{result['high_volume_date']}, "
                           f"涨停{result['limit_up_date']}, "
                           f"缩量至{result['volume_shrink_ratio']:.2%}, {breakout_status}")
        
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
            filename = f"data/shi_pan_xian_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'current_price', 'current_change',
            'high_volume_date', 'high_volume_price', 'high_volume',
            'limit_up_date', 'limit_up_price', 'limit_up_high', 'limit_up_low', 'limit_up_volume',
            'callback_days', 'shrink_volume_found', 'min_volume_during_callback', 'volume_shrink_ratio',
            'breakout_date', 'breakout_price', 'breakout_volume',
            'days_since_limit_up'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '当前价格', '当前涨幅%',
            '高量日期', '高量收盘价', '高量成交量',
            '涨停日期', '涨停收盘价', '涨停最高价', '涨停最低价', '涨停成交量',
            '回调天数', '是否缩量', '回调期最小量', '缩量比例',
            '突破日期', '突破价格', '突破成交量',
            '距高量天数'
        ]
        
        df.to_excel(filename, index=False, engine='xlsxwriter')
        logger.info(f"Results saved to: {filename}")
        return filename


def main():
    parser = argparse.ArgumentParser(description='涨停试盘线筛选器')
    parser.add_argument('--date', type=str, help='分析日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--consolidation-days', type=int, default=20, help='低位横盘判断天数')
    parser.add_argument('--high-volume-lookback', type=int, default=30, help='高量阳线回看周期')
    parser.add_argument('--max-consolidation-gain', type=float, default=0.10, help='横盘期最大涨幅')
    parser.add_argument('--shrink-threshold', type=float, default=0.25, help='缩量阈值(相对于高量,默认0.25=1/4)')
    parser.add_argument('--callback-max-days', type=int, default=10, help='最大回调天数')
    parser.add_argument('--breakout-ratio', type=float, default=1.5, help='再次放量倍数')
    parser.add_argument('--output', type=str, help='输出文件名')
    
    args = parser.parse_args()
    
    # 设置分析日期
    if args.date:
        # 这里简化处理，实际应该传入run_screening
        os.environ['SCREEN_DATE'] = args.date
    
    screener = ShiPanXianScreener(
        consolidation_days=args.consolidation_days,
        high_volume_lookback=args.high_volume_lookback,
        max_consolidation_gain=args.max_consolidation_gain,
        volume_shrink_threshold=args.shrink_threshold,
        callback_max_days=args.callback_max_days,
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
            shrink_status = f"缩量至{r['volume_shrink_ratio']:.1%}" if r['shrink_volume_found'] else "未缩量"
            breakout_status = f"突破于{r['breakout_date']}@{r['breakout_price']:.2f}" if r['breakout_date'] else "未突破"
            print(f"{r['code']} {r['name']}: 高量{r['high_volume_date']}, "
                  f"涨停{r['limit_up_date']}, 回调{r['callback_days']}天, "
                  f"{shrink_status}, {breakout_status}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'shi_pan_xian_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
