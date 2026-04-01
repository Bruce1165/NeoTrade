#!/usr/bin/env python3
"""
Quick fix turnover data using AKShare's daily data
"""

import sqlite3
import akshare as ak
import pandas as pd

DB_PATH = "data/stock_data.db"

def fix_turnover_for_date(date_str):
    """Fix turnover for all stocks on a given date"""
    print(f"\n=== Fixing {date_str} ===")
    
    # Format for AKShare
    date_ak = date_str.replace('-', '')
    
    # Get all stocks data for this date from AKShare
    print("Fetching data from AKShare...")
    try:
        # Get A-share daily data
        df = ak.stock_zh_a_spot_em()
        print(f"Got {len(df)} stocks from AKShare")
        
        # Rename columns to match our schema
        if '换手率' in df.columns:
            df_turnover = df[['代码', '换手率']].copy()
            df_turnover.columns = ['code', 'turnover']
            
            # Remove market prefix from code
            df_turnover['code'] = df_turnover['code'].astype(str).str.replace(r'^(sh|sz)', '', regex=True)
        else:
            print("No turnover column found")
            return 0
    except Exception as e:
        print(f"Error fetching from AKShare: {e}")
        return 0
    
    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get list of stocks we have for this date
    cursor.execute("SELECT code FROM daily_prices WHERE trade_date = ?", (date_str,))
    existing_codes = set(r[0] for r in cursor.fetchall())
    
    print(f"Database has {len(existing_codes)} stocks for {date_str}")
    
    fixed = 0
    for _, row in df_turnover.iterrows():
        code = str(row['code']).strip()
        turnover = row['turnover']
        
        if code not in existing_codes:
            continue
        
        if pd.isna(turnover) or turnover <= 0:
            continue
        
        try:
            cursor.execute("""
                UPDATE daily_prices 
                SET turnover = ? 
                WHERE code = ? AND trade_date = ?
            """, (turnover, code, date_str))
            fixed += 1
        except Exception as e:
            continue
    
    conn.commit()
    conn.close()
    
    print(f"✅ Fixed {fixed} records")
    return fixed

if __name__ == '__main__':
    # Fix both dates
    for date in ['2026-03-23', '2026-03-24']:
        fix_turnover_for_date(date)
