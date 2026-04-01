#!/usr/bin/env python3
"""
Fix turnover data using Baostock
"""
import sqlite3
import baostock as bs
import pandas as pd
from datetime import datetime

DB_PATH = "data/stock_data.db"

def get_stock_list():
    """Get all stock codes from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT code FROM daily_prices WHERE trade_date = '2026-03-24'")
    codes = [r[0] for r in cursor.fetchall()]
    conn.close()
    return codes

def fix_turnover_for_date(date_str):
    """Fix turnover for all stocks on a given date"""
    print(f"\n=== Fixing {date_str} ===")
    
    # Get stocks with 0 turnover
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code FROM daily_prices 
        WHERE trade_date = ? AND (turnover = 0 OR turnover IS NULL)
    """, (date_str,))
    codes_to_fix = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    print(f"Found {len(codes_to_fix)} stocks to fix")
    
    if not codes_to_fix:
        print("No stocks need fixing")
        return 0
    
    # Login to Baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"Login failed: {lg.error_msg}")
        return 0
    
    fixed = 0
    failed = 0
    
    for i, code in enumerate(codes_to_fix, 1):
        if i % 200 == 0:
            print(f"  Progress: {i}/{len(codes_to_fix)} (fixed: {fixed}, failed: {failed})")
        
        # Format code for Baostock
        if code.startswith('6'):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        try:
            rs = bs.query_history_k_data_plus(bs_code,
                'date,turn',
                start_date=date_str, end_date=date_str)
            
            if rs.error_code != '0':
                failed += 1
                continue
            
            data = rs.get_row_data()
            if not data or len(data) < 2:
                failed += 1
                continue
            
            turnover = float(data[1]) if data[1] else 0
            
            if turnover > 0:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE daily_prices 
                    SET turnover = ? 
                    WHERE code = ? AND trade_date = ?
                """, (turnover, code, date_str))
                conn.commit()
                conn.close()
                fixed += 1
            else:
                failed += 1
                
        except Exception as e:
            failed += 1
            continue
    
    bs.logout()
    print(f"✅ Fixed {fixed} records, failed: {failed}")
    return fixed

if __name__ == '__main__':
    total = 0
    for date in ['2026-03-23', '2026-03-24']:
        total += fix_turnover_for_date(date)
    print(f"\n🎉 Total fixed: {total} records")
