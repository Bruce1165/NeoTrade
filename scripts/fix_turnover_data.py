#!/usr/bin/env python3
"""
Fix missing turnover data for specific dates using AKShare
"""

import sqlite3
import akshare as ak
from datetime import datetime

DB_PATH = "data/stock_data.db"

def fix_turnover_data(date_str):
    """Fix turnover data for a specific date"""
    print(f"Fixing turnover data for {date_str}...")
    
    # Format date for AKShare (YYYYMMDD)
    date_ak = date_str.replace('-', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all stocks for this date
    cursor.execute("SELECT code FROM daily_prices WHERE trade_date = ?", (date_str,))
    stocks = [r[0] for r in cursor.fetchall()]
    
    print(f"Found {len(stocks)} stocks to fix")
    
    fixed = 0
    skipped = 0
    
    for i, code in enumerate(stocks, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(stocks)}")
        
        try:
            # Get data from AKShare
            df = ak.stock_zh_a_hist(symbol=code, period='daily', 
                                   start_date=date_ak, end_date=date_ak, adjust='qfq')
            
            if df.empty:
                skipped += 1
                continue
            
            # Get turnover (换手率)
            turnover = df.iloc[0]['换手率']
            
            if pd.isna(turnover) or turnover == 0:
                skipped += 1
                continue
            
            # Update database
            cursor.execute("""
                UPDATE daily_prices 
                SET turnover = ? 
                WHERE code = ? AND trade_date = ?
            """, (turnover, code, date_str))
            
            fixed += 1
            
        except Exception as e:
            skipped += 1
            continue
    
    conn.commit()
    conn.close()
    
    print(f"✅ Fixed {fixed} records, skipped {skipped}")
    return fixed

if __name__ == '__main__':
    import pandas as pd
    
    # Fix 2026-03-23 and 2026-03-24
    for date in ['2026-03-23', '2026-03-24']:
        fix_turnover_data(date)
        print()
