#!/usr/bin/env python3
"""
Chunked historical data download - downloads missing data in batches
Can resume if interrupted
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import json
import sqlite3
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"
PROGRESS_FILE = "data/download_progress.json"
CHUNK_SIZE = 200  # Process 200 stocks at a time

def load_progress():
    """Load download progress"""
    try:
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"completed": [], "failed": [], "last_chunk": 0}

def save_progress(progress):
    """Save download progress"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def get_stocks_needing_data():
    """Get list of stocks with incomplete data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.code, s.name, COUNT(d.code) as data_days
        FROM stocks s
        LEFT JOIN daily_prices d ON s.code = d.code
        WHERE s.code NOT LIKE '399%' 
          AND s.code NOT LIKE '000%'
          AND s.name NOT LIKE '%退%'
        GROUP BY s.code
        HAVING data_days < 300
        ORDER BY data_days DESC
    """)
    
    stocks = cursor.fetchall()
    conn.close()
    return stocks

def download_chunk(stock_codes, start_date, end_date):
    """Download data for a chunk of stocks"""
    from fetcher_baostock import BaostockFetcher
    from database import init_db, get_session, DailyPrice
    
    engine = init_db()
    session = get_session(engine)
    fetcher = BaostockFetcher()
    
    if not fetcher.login():
        logger.error("Failed to login to Baostock")
        return [], stock_codes
    
    completed = []
    failed = []
    
    try:
        for i, code in enumerate(stock_codes):
            bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
            
            logger.info(f"[{i+1}/{len(stock_codes)}] Downloading {code}...")
            
            try:
                df = fetcher.get_daily_data(bs_code, start_date, end_date)
                
                if not df.empty:
                    for _, row in df.iterrows():
                        trade_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                        
                        # Check if exists
                        existing = session.query(DailyPrice).filter_by(
                            code=code,
                            trade_date=trade_date
                        ).first()
                        
                        if existing:
                            continue
                        
                        # Add new record
                        new_price = DailyPrice(
                            code=code,
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
                    
                    completed.append(code)
                else:
                    failed.append(code)
                    
            except Exception as e:
                logger.error(f"Error downloading {code}: {e}")
                failed.append(code)
            
            # Small delay between requests
            time.sleep(0.1)
        
        session.commit()
        logger.info(f"Chunk complete: {len(completed)} success, {len(failed)} failed")
        
    finally:
        fetcher.logout()
        session.close()
    
    return completed, failed

def main():
    # Date range: from 2024-09-01 to 2026-03-11 (existing data range)
    start_date = "2024-09-01"
    end_date = "2026-03-12"
    
    logger.info("="*60)
    logger.info("Chunked Historical Data Download")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info("="*60)
    
    # Load progress
    progress = load_progress()
    logger.info(f"Previous progress: {len(progress['completed'])} completed, {len(progress['failed'])} failed")
    
    # Get stocks needing data
    stocks = get_stocks_needing_data()
    logger.info(f"Found {len(stocks)} stocks needing data")
    
    # Filter out already completed
    remaining = [s[0] for s in stocks if s[0] not in progress['completed']]
    logger.info(f"Remaining to download: {len(remaining)}")
    
    if not remaining:
        logger.info("All stocks already downloaded!")
        return
    
    # Process in chunks
    total_chunks = (len(remaining) + CHUNK_SIZE - 1) // CHUNK_SIZE
    start_chunk = progress.get('last_chunk', 0)
    
    for chunk_idx in range(start_chunk, total_chunks):
        start = chunk_idx * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, len(remaining))
        chunk = remaining[start:end]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} stocks)")
        logger.info(f"{'='*60}")
        
        completed, failed = download_chunk(chunk, start_date, end_date)
        
        # Update progress
        progress['completed'].extend(completed)
        progress['failed'].extend(failed)
        progress['last_chunk'] = chunk_idx + 1
        progress['last_update'] = datetime.now().isoformat()
        save_progress(progress)
        
        logger.info(f"Progress saved: {len(progress['completed'])} total completed")
        
        # Pause between chunks
        if chunk_idx < total_chunks - 1:
            logger.info("Pausing 3 seconds before next chunk...")
            time.sleep(3)
    
    logger.info("\n" + "="*60)
    logger.info("Download complete!")
    logger.info(f"Total completed: {len(progress['completed'])}")
    logger.info(f"Total failed: {len(progress['failed'])}")
    logger.info("="*60)

if __name__ == '__main__':
    main()
