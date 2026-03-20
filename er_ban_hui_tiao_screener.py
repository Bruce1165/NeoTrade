#!/usr/bin/env python3
"""
二板回调筛选器 - 二板回调战法

核心逻辑：
- 过去21个交易日内出现二连涨停板
- 随后回调不跌破首板最低价
- 再次放量启动

筛选条件：
1. 过去21天内出现二连涨停（涨幅≥9.9%）
2. 二连涨停后股价回调
3. 回调不跌破首板最低价（支撑位）
4. 近期有企稳或放量迹象
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

class ErBanHuiTiaoScreener:
    """二板回调筛选器"""
    
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
    
    def find_er_ban(self, df):
        """
        寻找二连涨停
        返回: (首板索引, 二板索引, 首板最低价, 二板最高价) 或 None
        """
        if len(df) < 2:
            return None
        
        # 从后往前找（最近发生的）
        for i in range(len(df) - 2, -1, -1):
            # 检查是否二连涨停（涨幅≥9.9%）
            if i + 1 < len(df):
                first_pct = df.iloc[i]['pct_change'] or 0
                second_pct = df.iloc[i + 1]['pct_change'] or 0
                
                if first_pct >= 9.9 and second_pct >= 9.9:
                    first_low = df.iloc[i]['low']
                    second_high = df.iloc[i + 1]['high']
                    return i, i + 1, first_low, second_high
        
        return None
    
    def check_hui_tiao(self, df, er_ban_info):
        """
        检查回调是否符合条件
        - 二连涨停后有回调
        - 不跌破首板最低价
        """
        first_idx, second_idx, first_low, second_high = er_ban_info
        
        # 检查二连涨停后是否有数据
        if second_idx + 1 >= len(df):
            return False, "无二连涨停后的数据"
        
        # 获取二连涨停后的数据
        after_er_ban = df.iloc[second_idx + 1:]
        
        if after_er_ban.empty:
            return False, "无二连涨停后的数据"
        
        # 检查是否跌破首板最低价
        min_low_after = after_er_ban['low'].min()
        
        if min_low_after < first_low * 0.99:  # 允许1%误差
            return False, f"跌破首板最低价: {min_low_after:.2f} < {first_low:.2f}"
        
        # 检查回调天数（至少1天）
        hui_tiao_days = len(after_er_ban)
        
        # 检查是否有企稳迹象（最近3天）
        recent_3 = after_er_ban.tail(3)
        if len(recent_3) >= 2:
            # 最近有上涨或企稳
            recent_trend = recent_3['close'].iloc[-1] - recent_3['close'].iloc[0]
            if recent_trend < -first_low * 0.05:  # 最近还在大跌
                return False, "最近仍在下跌，未企稳"
        
        return True, f"回调{hui_tiao_days}天，未破支撑位{first_low:.2f}"
    
    def screen_stock(self, code, name):
        """筛选单只股票"""
        df = self.get_stock_data(code, days=LIMIT_DAYS + 10)
        if df is None or len(df) < 5:
            return None
        
        # 寻找二连涨停
        er_ban_info = self.find_er_ban(df)
        if er_ban_info is None:
            return None
        
        first_idx, second_idx, first_low, second_high = er_ban_info
        
        # 检查是否在21天内
        er_ban_date = df.iloc[second_idx]['trade_date']
        latest_date = df.iloc[-1]['trade_date']
        days_ago = (latest_date - er_ban_date).days
        
        if days_ago > LIMIT_DAYS:
            return None
        
        # 检查回调
        hui_tiao_ok, hui_tiao_msg = self.check_hui_tiao(df, er_ban_info)
        if not hui_tiao_ok:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        return {
            'code': code,
            'name': name,
            'er_ban_date': er_ban_date.strftime('%Y-%m-%d'),
            'days_ago': days_ago,
            'first_low': first_low,
            'second_high': second_high,
            'current_price': latest['close'],
            'support_distance': (latest['close'] - first_low) / first_low * 100,
            'turnover': latest.get('turnover', 0) or 0,
            'pct_change': latest.get('pct_change', 0) or 0,
            'hui_tiao_status': hui_tiao_msg
        }
    
    def run_screening(self, trade_date: str = None):
        """运行筛选
        
        Args:
            trade_date: 交易日期，格式 YYYYMMDD 或 YYYY-MM-DD，默认为今天
        """
        logger.info("="*60)
        logger.info("二板回调筛选器 - Er Ban Hui Tiao Screener")
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
                logger.info(f"✓ Found: {stock.code} {stock.name} - 二板日期: {result['er_ban_date']}")
        
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
            filename = f"data/er_ban_hui_tiao_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        
        df = pd.DataFrame(results)
        
        # 调整列顺序
        columns = [
            'code', 'name', 'er_ban_date', 'days_ago', 'first_low', 'second_high',
            'current_price', 'support_distance', 'turnover', 'pct_change', 'hui_tiao_status'
        ]
        df = df[columns]
        
        # 重命名列为中文
        df.columns = [
            '股票代码', '股票名称', '二板日期', '距今天数', '首板最低价', '二板最高价',
            '当前价格', '支撑位距离%', '换手率%', '涨幅%', '回调状态'
        ]
        
        df.to_excel(filename, index=False)
        logger.info(f"Results saved to: {filename}")
        return filename

def main():
    screener = ErBanHuiTiaoScreener()
    results = screener.run_screening()
    
    if results:
        screener.save_results(results)
        
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            print(f"{r['code']} {r['name']}: 二板{r['er_ban_date']}, "
                  f"支撑位{r['first_low']:.2f}, 当前{r['current_price']:.2f}, "
                  f"距离支撑位{r['support_distance']:.1f}%")
    else:
        print("\n没有找到符合条件的股票")

if __name__ == '__main__':
    main()
