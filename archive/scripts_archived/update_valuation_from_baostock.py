#!/usr/bin/env python3
"""
从 Baostock 更新 stocks 表估值数据 (PE, PB)
"""
import baostock as bs
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"

def update_valuation_data():
    """更新估值数据"""
    lg = bs.login()
    print(f'Login: {lg.error_code}')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all active stocks
    cursor.execute("""
        SELECT code FROM stocks 
        WHERE (is_delisted IS NULL OR is_delisted = 0)
        AND (pb_ratio IS NULL OR pe_ratio IS NULL)
    """)
    stocks = cursor.fetchall()
    print(f'Need to update: {len(stocks)} stocks')
    
    today = '2026-03-24'
    updated = 0
    total = len(stocks)
    
    for i, (code,) in enumerate(stocks, 1):
        try:
            # Format code
            if code.startswith('6'):
                bs_code = f'sh.{code}'
            elif code.startswith('0') or code.startswith('3'):
                bs_code = f'sz.{code}'
            elif code.startswith('8') or code.startswith('4'):
                bs_code = f'bj.{code}'
            else:
                continue
            
            # Query valuation data
            rs = bs.query_history_k_data_plus(
                bs_code, 
                'date,peTTM,pbMRQ',
                start_date=today, 
                end_date=today
            )
            
            if rs.error_code == '0' and rs.next():
                row = rs.get_row_data()
                pe = float(row[1]) if row[1] else None
                pb = float(row[2]) if row[2] else None
                
                cursor.execute('''
                    UPDATE stocks 
                    SET pe_ratio = COALESCE(?, pe_ratio),
                        pb_ratio = COALESCE(?, pb_ratio),
                        updated_at = ?
                    WHERE code = ?
                ''', (pe, pb, datetime.now(), code))
                
                if cursor.rowcount > 0:
                    updated += 1
            
            if i % 100 == 0:
                print(f'Progress: {i}/{total} ({i/total*100:.1f}%), updated: {updated}')
                conn.commit()
                
        except Exception as e:
            print(f'Error {code}: {e}')
    
    conn.commit()
    conn.close()
    bs.logout()
    print(f'Done! Updated {updated} stocks')

if __name__ == '__main__':
    update_valuation_data()
