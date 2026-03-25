#!/usr/bin/env python3
"""
Batch fix turnover data with retry logic
"""

import sqlite3
import akshare as ak
import time
from datetime import datetime

DB_PATH = "data/stock_data.db"

def get_turnover_from_akshare():
    """Get turnover data from AKShare with retry"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Fetching data from AKShare (attempt {attempt + 1})...")
            df = ak.stock_zh_a_spot_em()
            print(f"✅ Got {len(df)} stocks")
            return df
        except Exception as e:
            print(f"⚠️  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print("❌ All retries failed")
                return None

def fix_date_turnover(date_str, turnover_dict):
    """Fix turnover for a specific date"""
    print(f"\n=== Fixing {date_str} ===")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find stocks with 0 or NULL turnover
    cursor.execute("""
        SELECT code FROM daily_prices 
        WHERE trade_date = ? AND (turnover = 0 OR turnover IS NULL)
    """, (date_str,))
    
    codes_to_fix = [r[0] for r in cursor.fetchall()]
    print(f"Found {len(codes_to_fix)} stocks to fix")
    
    if not codes_to_fix:
        print("No stocks need fixing")
        conn.close()
        return 0
    
    fixed = 0
    not_found = 0
    
    for i, code in enumerate(codes_to_fix, 1):
        if i % 500 == 0:
            print(f"  Progress: {i}/{len(codes_to_fix)} (fixed: {fixed})")
        
        if code in turnover_dict:
            turnover = turnover_dict[code]
            if turnover and turnover > 0:
                cursor.execute("""
                    UPDATE daily_prices 
                    SET turnover = ? 
                    WHERE code = ? AND trade_date = ?
                """, (turnover, code, date_str))
                fixed += 1
        else:
            not_found += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Fixed {fixed} records, not found: {not_found}")
    return fixed

if __name__ == '__main__':
    # Get turnover data once
    df = get_turnover_from_akshare()
    
    if df is None:
        print("Failed to get data from AKShare")
        exit(1)
    
    # Build turnover dictionary
    print("Building turnover dictionary...")
    turnover_dict = {}
    for _, row in df.iterrows():
        code = str(row['代码']).replace('sh', '').replace('sz', '').strip()
        try:
            turnover = float(row.get('换手率', 0))
            if turnover > 0:
                turnover_dict[code] = turnover
        except:
            continue
    
    print(f"Valid turnover data for {len(turnover_dict)} stocks")
    
    # Fix both dates
    total_fixed = 0
    for date in ['2026-03-23', '2026-03-24']:
        total_fixed += fix_date_turnover(date, turnover_dict)
        time.sleep(1)  # Brief pause between dates
    
    print(f"\n🎉 Total fixed: {total_fixed} records")
