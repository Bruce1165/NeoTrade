#!/usr/bin/env python3
"""
涨停倍量阴筛选器 - 放量阴拉涨停战法

核心逻辑：
- 首板实体涨停
- 次日高开低走，中大阴线，成交量比涨停日还大（倍量）
- 后续回调缩量到极致（地量，低于倍量阴的一半）
- 地量说明抛压很轻，主力控盘度高

筛选条件：
1. 过去21天内出现首板涨停（涨幅≥9.9%）
2. 次日高开低走，形成中大阴线（实体≥3%）
3. 次日成交量 > 涨停日成交量（倍量）
4. 后续出现地量（成交量 < 倍量阴的一半）
5. 地量后企稳或开始上涨
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
LIMIT_DAYS = 21  # 过去21个交易日

class ZhangTingBeiLiangYinScreener:
    """涨停倍量阴筛选器"""
    
    def __init__(self):
        self.engine = init_db()
        self.session = get_session(self.engine)
    
    def get_stock_data(self, code, days=30):
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
    
    def find_zhang_ting_bei_liang_yin(self, df):
        """
        寻找涨停倍量阴形态
        返回: (涨停索引, 倍量阴索引, 地量索引) 或 None
        """
        if len(df) < 5:
            return None
        
        # 从后往前找（最近发生的）
        for i in range(len(df) - 2, -1, -1):
            # 检查是否首板涨停（涨幅≥9.9%）
            zt_pct = df.iloc[i]['pct_change'] or 0
            if zt_pct < 9.9:
                continue
            
            # 获取涨停日最低价（支撑位）
            zt_low = df.iloc[i]['low']
            
            # 检查涨停后21天内，收盘价是否都高于涨停日最低价
            days_to_check = min(21, len(df) - i - 1)
            support_broken = False
            for k in range(1, days_to_check + 1):
                if i + k < len(df):
                    if df.iloc[i + k]['close'] < zt_low * 0.99:  # 允许1%误差
                        support_broken = True
                        break
            
            if support_broken:
                continue
            
            # 检查次日是否高开低走中大阴线
            if i + 1 >= len(df):
                continue
            
            next_open = df.iloc[i + 1]['open']
            next_close = df.iloc[i + 1]['close']
            next_low = df.iloc[i + 1]['low']
            zt_close = df.iloc[i]['close']
            
            # 高开：开盘价 > 涨停收盘价
            if next_open <= zt_close * 1.01:  # 允许1%误差
                continue
            
            # 低走：收盘价 < 开盘价，且实体较大（≥3%）
            body_pct = (next_open - next_close) / zt_close * 100
            if body_pct < 3:
                continue
            
            # 倍量：次日成交量 > 涨停日成交量
            zt_volume = df.iloc[i]['volume']
            next_volume = df.iloc[i + 1]['volume']
            if next_volume <= zt_volume:
                continue
            
            # 找到倍量阴后，检查后续是否出现地量
            if i + 2 >= len(df):
                continue
            
            # 检查后续3-7天内是否出现地量
            for j in range(i + 2, min(i + 8, len(df))):
                current_volume = df.iloc[j]['volume']
                # 地量：成交量 < 倍量阴的一半
                if current_volume < next_volume * 0.5:
                    return i, i + 1, j
        
        return None
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code, days=LIMIT_DAYS + 10)
        if df is None or len(df) < 5:
            return None
        
        # 寻找涨停倍量阴形态
        pattern = self.find_zhang_ting_bei_liang_yin(df)
        if pattern is None:
            return None
        
        zt_idx, bei_liang_idx, di_liang_idx = pattern
        
        # 检查是否在21天内
        latest_date = df.iloc[-1]['trade_date']
        pattern_date = df.iloc[bei_liang_idx]['trade_date']
        days_ago = (latest_date - pattern_date).days
        
        if days_ago > LIMIT_DAYS:
            return None
        
        # 获取关键数据
        zt_row = df.iloc[zt_idx]
        bei_liang_row = df.iloc[bei_liang_idx]
        di_liang_row = df.iloc[di_liang_idx]
        latest = df.iloc[-1]
        
        # 计算支撑位（涨停最低价或倍量阴最低价）
        support_price = min(zt_row['low'], bei_liang_row['low'])
        
        # 检查是否跌破支撑位
        if latest['close'] < support_price * 0.98:
            return None
        
        return {
            'code': code,
            'name': name,
            'zt_date': zt_row['trade_date'].strftime('%Y-%m-%d'),
            'bei_liang_date': bei_liang_row['trade_date'].strftime('%Y-%m-%d'),
            'di_liang_date': di_liang_row['trade_date'].strftime('%Y-%m-%d'),
            'days_ago': days_ago,
            'zt_close': zt_row['close'],
            'bei_liang_open': bei_liang_row['open'],
            'bei_liang_close': bei_liang_row['close'],
            'bei_liang_volume': bei_liang_row['volume'],
            'zt_volume': zt_row['volume'],
            'volume_ratio': bei_liang_row['volume'] / zt_row['volume'],
            'di_liang_volume': di_liang_row['volume'],
            'di_liang_ratio': di_liang_row['volume'] / bei_liang_row['volume'],
            'support_price': support_price,
            'current_price': latest['close'],
            'support_distance': (latest['close'] - support_price) / support_price * 100,
            'turnover': latest.get('turnover', 0) or 0,
            'pct_change': latest.get('pct_change', 0) or 0
        }
    
    def run_screening(self, trade_date: str = None):
        """运行筛选

        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为今天
        """
        logger.info("="*60)
        logger.info("涨停倍量阴筛选器 - Zhang Ting Bei Liang Yin Screener")
        logger.info(f"时间范围: 过去{LIMIT_DAYS}个交易日")
        if trade_date:
            logger.info(f"指定日期: {trade_date}")
        logger.info("="*60)
        
        # 获取所有活跃股票
        stocks = self.session.query(Stock).all()
        stocks = [
            s for s in stocks
            if not s.code.startswith('8')
            and not s.code.startswith('4')
            and not s.code.startswith('399')
            and not s.code.startswith('000')
            and '退' not in (s.name or '')
            and 'ST' not in (s.name or '')
        ]
        
        logger.info(f"Total stocks: {len(stocks)}")
        
        results = []
        checked = 0
        
        for stock in stocks:
            checked += 1
            if checked % 500 == 0:
                logger.info(f"Checked {checked} stocks, found {len(results)} matches")
            
            result = self.screen_stock(stock.code, stock.name)
            if result:
                results.append(result)
                logger.info(f"✓ Found: {stock.code} {stock.name} - 倍量阴日期: {result['bei_liang_date']}")
        
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
            filename = f"data/zhang_ting_bei_liang_yin_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'zt_date', 'bei_liang_date', 'di_liang_date', 'days_ago',
            'zt_close', 'bei_liang_open', 'bei_liang_close', 'bei_liang_volume', 'zt_volume',
            'volume_ratio', 'di_liang_volume', 'di_liang_ratio', 'support_price',
            'current_price', 'support_distance', 'turnover', 'pct_change'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '涨停日期', '倍量阴日期', '地量日期', '距今天数',
            '涨停收盘价', '倍量阴开盘价', '倍量阴收盘价', '倍量阴成交量', '涨停成交量',
            '倍量比例', '地量成交量', '地量比例', '支撑位',
            '当前价格', '支撑位距离%', '换手率%', '涨幅%'
        ]
        
        df.to_excel(filename, index=False)
        logger.info(f"Results saved to: {filename}")
        return filename

def main():
    screener = ZhangTingBeiLiangYinScreener()
    results = screener.run_screening()
    
    if results:
        screener.save_results(results)
        
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            print(f"{r['code']} {r['name']}: 涨停{r['zt_date']}, 倍量阴{r['bei_liang_date']}, "
                  f"倍量{r['volume_ratio']:.1f}x, 地量{r['di_liang_ratio']:.1f}x")
    else:
        print("\n没有找到符合条件的股票")

if __name__ == '__main__':
    main()
