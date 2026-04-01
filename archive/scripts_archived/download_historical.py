#!/usr/bin/env python3
"""
下载历史数据补充脚本 - 补充第7-18个月数据
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
from fetcher_baostock import BaostockFetcher
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_historical_data():
    """下载第7-18个月的历史数据"""
    
    # 计算时间范围
    # 当前数据到2026-03-11，补充2024-09到2025-09（约12个月）
    end_date = datetime(2025, 9, 15)  # 从现有数据开始往前
    start_date = datetime(2024, 9, 1)  # 再往前12个月
    
    logger.info("="*60)
    logger.info(f"下载历史数据: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    logger.info("="*60)
    
    engine = init_db()
    session = get_session(engine)
    fetcher = BaostockFetcher()
    
    if not fetcher.login():
        logger.error("登录失败")
        return
    
    try:
        # 获取所有股票
        stocks = session.query(Stock).all()
        total = len(stocks)
        
        logger.info(f"共 {total} 只股票需要更新")
        
        updated = 0
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        for i, stock in enumerate(stocks):
            code = f"sh.{stock.code}" if stock.code.startswith('6') else f"sz.{stock.code}"
            
            if (i + 1) % 100 == 0 or i == 0:
                logger.info(f"[{i+1}/{total}] 更新 {stock.code} {stock.name}...")
            
            # 获取历史数据
            df = fetcher.get_daily_data(code, start_str, end_str)
            
            if not df.empty:
                for _, row in df.iterrows():
                    trade_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                    
                    # 检查是否已存在
                    existing = session.query(DailyPrice).filter_by(
                        code=stock.code,
                        trade_date=trade_date
                    ).first()
                    
                    if existing:
                        continue  # 跳过已存在的数据
                    
                    # 新增
                    new_price = DailyPrice(
                        code=stock.code,
                        trade_date=trade_date,
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        volume=row.get('volume'),
                        amount=row.get('amount'),
                        turnover=row.get('turn'),
                        preclose=row.get('preclose'),
                        pct_change=row.get('pctChg')
                    )
                    session.add(new_price)
                
                updated += 1
                
                # 每50只提交一次
                if updated % 50 == 0:
                    session.commit()
                    logger.info(f"已提交 {updated} 只股票数据")
            
            # 每100只暂停
            if (i + 1) % 100 == 0:
                import time
                time.sleep(1)
        
        session.commit()
        logger.info(f"历史数据更新完成，共更新 {updated} 只股票")
        
    finally:
        fetcher.logout()
        session.close()

if __name__ == '__main__':
    download_historical_data()
