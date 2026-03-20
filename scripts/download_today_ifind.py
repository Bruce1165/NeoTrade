#!/usr/bin/env python3
"""
Download today's stock data from iFind Realtime
Saves to SQLite database
"""
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add dashboard to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'dashboard'))

from ifind_realtime import RealtimeFeed
from ifind_client import IfindClient

def get_all_stock_codes(db_path='data/stock_data.db'):
    """Get all active stock codes from database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get codes and format them with exchange suffix
    cursor.execute("""
        SELECT code FROM stocks 
        WHERE (is_delisted IS NULL OR is_delisted = 0)
        ORDER BY code
    """)
    
    codes = []
    for row in cursor.fetchall():
        code = row[0]
        # Format: add exchange suffix
        if code.startswith('6'):
            codes.append(f"{code}.SH")
        else:
            codes.append(f"{code}.SZ")
    
    conn.close()
    return codes

def download_today_data():
    """Download today's data for all stocks"""
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Downloading data for {today}")
    
    # Get stock codes
    print("📋 Loading stock codes...")
    codes = get_all_stock_codes()
    print(f"🎯 Total stocks: {len(codes)}")
    
    # Initialize client and fetch data
    print("🔌 Connecting to iFind...")
    client = IfindClient()
    feed = RealtimeFeed(client)
    
    print("⬇️ Downloading realtime data...")
    try:
        df = feed.fetch(codes)
        print(f"✅ Downloaded {len(df)} stocks")
        print(f"📊 Columns: {list(df.columns)}")
        print(df.head())
        return df, today
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise

def save_to_database(df, trade_date, db_path='data/stock_data.db'):
    """Save data to SQLite database"""
    print(f"💾 Saving to database...")
    
    conn = sqlite3.connect(db_path)
    
    # Prepare data for insertion
    records = []
    for _, row in df.iterrows():
        # Column name is 'thscode' not 'code'
        thscode = row.get('thscode', '') or row.get('code', '')
        code = str(thscode).split('.')[0]  # Remove suffix
        if not code or code == 'nan':
            continue
            
        records.append({
            'code': code,
            'trade_date': trade_date,
            'open': row.get('open', 0),
            'close': row.get('latest', 0),  # Use latest as close
            'high': row.get('high', 0),
            'low': row.get('low', 0),
            'preclose': row.get('preClose', 0),
            'volume': row.get('volume', 0),
            'amount': row.get('amount', 0),
            'turnover': row.get('turnoverRatio', 0),
            'pct_change': row.get('changeRatio', 0)
        })
    
    # Insert or replace
    cursor = conn.cursor()
    inserted = 0
    for record in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_prices 
                (code, trade_date, open, close, high, low, preclose, volume, amount, turnover, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['code'], record['trade_date'], record['open'],
                record['close'], record['high'], record['low'],
                record['preclose'], record['volume'], record['amount'],
                record['turnover'], record['pct_change']
            ))
            inserted += 1
        except Exception as e:
            print(f"⚠️ Error inserting {record['code']}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Inserted/Updated {inserted} records")
    return inserted

if __name__ == '__main__':
    try:
        df, today = download_today_data()
        if len(df) > 0:
            inserted = save_to_database(df, today)
            print(f"\n🎉 Success! Downloaded {inserted} stocks for {today}")
        else:
            print("❌ No data downloaded")
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
