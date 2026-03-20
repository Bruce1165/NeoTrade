#!/usr/bin/env python3
"""
Check data integrity and identify stocks with missing historical data.
Generates a list of stocks that need to be re-downloaded.
"""

import sqlite3
from datetime import datetime, timedelta
import json

DB_PATH = "data/stock_data.db"

def get_expected_trading_days(start_date, end_date):
    """Calculate expected number of trading days (excluding weekends)."""
    current = start_date
    trading_days = 0
    while current <= end_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            trading_days += 1
        current += timedelta(days=1)
    return trading_days

def check_data_integrity():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get date range in database
    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices")
    min_date, max_date = cursor.fetchone()
    
    if not min_date or not max_date:
        print("No data in database")
        return
    
    print(f"Database date range: {min_date} to {max_date}")
    
    # Expected trading days in this range
    start = datetime.strptime(min_date, "%Y-%m-%d")
    end = datetime.strptime(max_date, "%Y-%m-%d")
    expected_days = get_expected_trading_days(start, end)
    print(f"Expected trading days: ~{expected_days}")
    
    # Find stocks with insufficient data
    cursor.execute("""
        SELECT 
            s.code,
            s.name,
            s.list_date,
            COUNT(d.code) as data_days,
            MIN(d.trade_date) as earliest,
            MAX(d.trade_date) as latest
        FROM stocks s
        LEFT JOIN daily_prices d ON s.code = d.code
        WHERE s.code NOT LIKE '399%'  -- Exclude index symbols
          AND s.code NOT LIKE '000%'  -- Exclude index symbols
        GROUP BY s.code
        HAVING data_days < 100
        ORDER BY data_days ASC
    """)
    
    incomplete_stocks = cursor.fetchall()
    
    print(f"\nFound {len(incomplete_stocks)} stocks with < 100 days of data")
    print("\nTop 20 stocks with least data:")
    print("-" * 80)
    print(f"{'Code':<10} {'Name':<15} {'List Date':<12} {'Days':<6} {'Earliest':<12} {'Latest':<12}")
    print("-" * 80)
    
    for row in incomplete_stocks[:20]:
        code, name, list_date, days, earliest, latest = row
        print(f"{code:<10} {name or '':<15} {list_date or '':<12} {days:<6} {earliest or '':<12} {latest or '':<12}")
    
    # Save list for re-download
    stocks_to_download = [row[0] for row in incomplete_stocks]
    
    with open("data/stocks_to_repair.json", "w") as f:
        json.dump({
            "count": len(stocks_to_download),
            "stocks": stocks_to_download,
            "date_range": {"min": min_date, "max": max_date},
            "generated_at": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\nSaved {len(stocks_to_download)} stocks to data/stocks_to_repair.json")
    
    conn.close()
    return stocks_to_download

if __name__ == "__main__":
    check_data_integrity()
