#!/usr/bin/env python3
"""
咖啡杯形态筛选器 - Coffee Cup Pattern Screener

杯柄形态定义：
- 杯沿 = 昨天收盘价
- 杯柄 = 过去某天（45天前或更早）的股价
- 杯沿 vs 杯柄价格差 ≤ 5%
- 杯底可以有凸起，但不能有高于杯柄/杯沿的凸起

杯沿条件（昨天）：
1. 换手率 ≥ 5%
2. 涨幅 ≥ 2%
3. 放量：最近3天成交额总和 ≥ 前3天成交额总和的 2倍
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"

class CoffeeCupScreener:
    def __init__(self):
        self.engine = init_db()
        self.session = get_session(self.engine)
        
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
        return df
    
    def check_volume_surge(self, df):
        """
        检查放量条件：
        最近3天（含今天）成交额总和 ≥ 前3天成交额总和的 2倍
        """
        if len(df) < 7:
            return False, 0
        
        # 最近3天 = 今天 + 昨天 + 前天（最后3条）
        recent_3_days = df.iloc[-3:]['amount'].sum()
        # 前3天 = 大前天 + 第5天 + 第6天
        previous_3_days = df.iloc[-6:-3]['amount'].sum()
        
        if previous_3_days <= 0:
            return False, 0
        
        volume_ratio = recent_3_days / previous_3_days
        return volume_ratio >= 2.0, volume_ratio
    
    def find_cup_handle(self, df, max_price):
        """
        寻找杯柄：
        - 45天前或更早
        - 股价与杯沿（max_price）相差不超过5%
        - 杯底不能有高于杯柄/杯沿的凸起
        """
        if len(df) < 46:
            return None
        
        # 杯沿价格（昨天收盘价）
        cup_rim_price = df.iloc[-1]['close']
        
        # 先找出所有可能的杯柄候选（45天前或更早，价格差<=5%）
        candidates = []
        for i in range(len(df) - 46, -1, -1):
            handle_price = df.iloc[i]['close']
            handle_high = df.iloc[i]['high']
            handle_date = df.iloc[i]['trade_date']
            
            # 价格差不超过5%
            price_diff_pct = abs(handle_price - cup_rim_price) / cup_rim_price
            if price_diff_pct > 0.05:
                continue
            
            # 杯柄必须是局部高点，且前7天不是连续/阶梯下跌
            if i < 7:  # 前面不足7天，跳过
                continue
            
            # 前3天（含当天）必须是局部高点
            prev_3_days = df.iloc[i-3:i+1]
            max_close_in_prev_3 = prev_3_days['close'].max()
            if handle_price < max_close_in_prev_3:
                continue
            
            # 检查前7天不是连续下跌或阶梯下跌
            prev_7_days = df.iloc[i-7:i]
            closes = prev_7_days['close'].values
            
            # 检查是否连续下跌（每一天都比前一天低）
            consecutive_down = all(closes[j] > closes[j+1] for j in range(len(closes)-1))
            if consecutive_down:
                continue
            
            # 检查是否阶梯下跌（整体趋势向下，且没有明显反弹）
            # 方法：前7天最高价出现在前几天，最低价出现在后几天
            max_idx = prev_7_days['close'].idxmax()
            min_idx = prev_7_days['close'].idxmin()
            if max_idx < min_idx:
                # 高点在前，低点在后，说明是下跌趋势
                # 检查跌幅是否超过5%（确认是明显下跌）
                max_price = prev_7_days.loc[max_idx, 'close']
                min_price = prev_7_days.loc[min_idx, 'close']
                if min_price <= max_price * 0.95:  # 跌幅超过5%
                    continue
            
            candidates.append({
                'idx': i,
                'price': handle_price,
                'high': handle_high,
                'date': handle_date,
                'diff_pct': price_diff_pct
            })
        
        if not candidates:
            return None
        
        # 从最早的候选开始检查（确保杯底期间没有更高的凸起）
        for candidate in reversed(candidates):  # 从最早的开始
            i = candidate['idx']
            handle_price = candidate['price']
            handle_date = candidate['date']
            
            # 检查杯底：杯柄到杯沿之间不能有高于杯柄/杯沿的凸起
            cup_bottom_df = df.iloc[i+1:-1]  # 杯柄之后到杯沿之前
            if cup_bottom_df.empty:
                continue
            
            # 杯沿和杯柄的较高者作为上限
            price_ceiling = max(handle_price, cup_rim_price)
            
            # 检查杯底期间：所有交易日的收盘价都必须低于杯柄和杯沿
            # 即不能有任何一个交易日的收盘价 >= price_ceiling
            max_close_in_cup = cup_bottom_df['close'].max()
            if max_close_in_cup >= price_ceiling:
                continue
            
            # 找到符合条件的杯柄
            days_apart = len(df) - 1 - i
            return {
                'handle_date': handle_date.strftime('%Y-%m-%d'),
                'handle_price': handle_price,
                'cup_rim_price': cup_rim_price,
                'price_diff_pct': candidate['diff_pct'] * 100,
                'days_apart': days_apart,
                'cup_depth_pct': (cup_rim_price - cup_bottom_df['low'].min()) / cup_rim_price * 100
            }
        
        return None
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code)
        if df is None or len(df) < 50:
            return None
        
        # 获取昨天数据
        yesterday = df.iloc[-1]
        
        # 条件1：换手率 ≥ 5%
        turnover = yesterday.get('turnover', 0) or 0
        if turnover < 5:
            return None
        
        # 条件2：涨幅 ≥ 2%
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2:
            return None
        
        # 条件3：放量 ≥ 2倍
        volume_surge, volume_ratio = self.check_volume_surge(df)
        if not volume_surge:
            return None
        
        # 寻找杯柄形态
        cup_handle = self.find_cup_handle(df, yesterday['close'])
        if cup_handle is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'turnover': turnover,
            'pct_change': pct_change,
            'volume_ratio': volume_ratio,
            'close': yesterday['close'],
            'amount': yesterday['amount'],
            **cup_handle
        }
    
    def run_screening(self, trade_date: str = None):
        """运行筛选

        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为今天
        """
        logger.info("="*60)
        logger.info("咖啡杯形态筛选 - Coffee Cup Pattern Screener")
        if trade_date:
            logger.info(f"指定日期: {trade_date}")
        logger.info("="*60)
        
        # 获取所有股票
        stocks = self.session.query(Stock).all()
        logger.info(f"Total stocks: {len(stocks)}")
        
        results = []
        checked = 0
        
        for stock in stocks:
            # 跳过指数和ST股
            if stock.code.startswith('399') or stock.code.startswith('000'):
                continue
            if stock.name and ('ST' in stock.name or '退' in stock.name):
                continue
            
            checked += 1
            if checked % 500 == 0:
                logger.info(f"Checked {checked} stocks, found {len(results)} matches")
            
            result = self.screen_stock(stock.code, stock.name)
            if result:
                results.append(result)
                logger.info(f"✓ Found: {stock.code} {stock.name}")
        
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
            filename = f"data/coffee_cup_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'close', 'turnover', 'pct_change', 'volume_ratio',
            'handle_date', 'handle_price', 'cup_rim_price', 'price_diff_pct',
            'days_apart', 'cup_depth_pct', 'amount'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '收盘价', '换手率%', '涨幅%', '放量倍数',
            '杯柄日期', '杯柄价格', '杯沿价格', '价格差%', '间隔天数', '杯深%', '成交额'
        ]
        
        df.to_excel(filename, index=False)
        logger.info(f"Results saved to: {filename}")
        return filename

def main():
    screener = CoffeeCupScreener()
    results = screener.run_screening()
    
    if results:
        screener.save_results(results)
        
        # 打印结果
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            print(f"{r['code']} {r['name']}: 杯柄{r['handle_date']}@{r['handle_price']:.2f}, "
                  f"杯沿@{r['cup_rim_price']:.2f}, 放量{r['volume_ratio']:.2f}x, "
                  f"换手{r['turnover']:.1f}%")
    else:
        print("\n没有找到符合条件的股票")

if __name__ == '__main__':
    main()
