#!/usr/bin/env python3
"""
补充历史数据下载 - 针对数据不足的股票
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
from fetcher_baostock import BaostockFetcher
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"

def get_stocks_with_insufficient_data(min_days=100):
    """获取数据不足的股票"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT 
            s.code,
            s.name,
            COUNT(d.code) as days
        FROM stocks s
        LEFT JOIN daily_prices d ON s.code = d.code
        WHERE s.code NOT LIKE '399%'
          AND s.code NOT LIKE '000%'
          AND s.name NOT LIKE '%退%'
          AND s.name NOT LIKE '%ST%'
          AND s.code NOT LIKE '8%'
          AND s.code NOT LIKE '4%'
        GROUP BY s.code
        HAVING days < ?
        ORDER BY days ASC
    """
    df = pd.read_sql_query(query, conn, params=(min_days,))
    conn.close()
    return df

def download_stock_data(fetcher, code, start_date, end_date):
    """下载单只股票数据"""
    bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
    try:
        df = fetcher.get_daily_data(bs_code, start_date, end_date)
        return df
    except Exception as e:
        logger.error(f"下载 {code} 失败: {e}")
        return pd.DataFrame()

def main():
    # 获取数据不足的股票
    stocks_df = get_stocks_with_insufficient_data(min_days=100)
    logger.info(f"发现 {len(stocks_df)} 只股票数据不足")
    
    if stocks_df.empty:
        logger.info("所有股票数据充足")
        return
    
    # 显示前20个
    logger.info("数据不足的股票（前20）:")
    for _, row in stocks_df.head(20).iterrows():
        logger.info(f"  {row['code']} {row['name']}: {row['days']} 天")
    
    # 下载数据
    engine = init_db()
    session = get_session(engine)
    fetcher = BaostockFetcher()
    
    if not fetcher.login():
        logger.error("登录失败")
        return
    
    try:
        start_date = "2024-09-01"
        end_date = "2026-03-12"
        
        for idx, row in stocks_df.iterrows():
            code = row['code']
            name = row['name']
            current_days = row['days']
            
            logger.info(f"[{idx+1}/{len(stocks_df)}] 下载 {code} {name} (当前{current_days}天)...")
            
            df = download_stock_data(fetcher, code, start_date, end_date)
            
            if not df.empty:
                for _, row_data in df.iterrows():
                    trade_date = datetime.strptime(row_data['date'], '%Y-%m-%d').date()
                    
                    # 检查是否已存在
                    existing = session.query(DailyPrice).filter_by(
                        code=code,
                        trade_date=trade_date
                    ).first()
                    
                    if existing:
                        continue
                    
                    new_price = DailyPrice(
                        code=code,
                        trade_date=trade_date,
                        open=row_data.get('open'),
                        high=row_data.get('high'),
                        low=row_data.get('low'),
                        close=row_data.get('close'),
                        volume=row_data.get('volume'),
                        amount=row_data.get('amount'),
                        turnover=row_data.get('turn'),
                        preclose=row_data.get('preclose'),
                        pct_change=row_data.get('pctChg')
                    )
                    session.add(new_price)
                
                session.commit()
                logger.info(f"  ✓ 下载完成: {len(df)} 条记录")
            else:
                logger.warning(f"  ✗ 无数据")
            
            time.sleep(0.1)
    
    finally:
        fetcher.logout()
        session.close()
    
    logger.info("补充下载完成")

if __name__ == '__main__':
    main()
