#!/usr/bin/env python3
"""
修复 2026-03-23 缺失的数据
使用 Baostock 回填
"""
import sqlite3
import sys
from pathlib import Path
import baostock as bs
import pandas as pd
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"
TARGET_DATE = "2026-03-23"

def get_missing_stocks():
    """获取 03-23 缺失数据的股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取 03-24 有数据但 03-23 没有的股票
    cursor.execute("""
        SELECT DISTINCT code FROM daily_prices 
        WHERE trade_date = '2026-03-24'
        AND code NOT IN (
            SELECT DISTINCT code FROM daily_prices 
            WHERE trade_date = '2026-03-23'
        )
    """)
    missing = [row[0] for row in cursor.fetchall()]
    conn.close()
    return missing

def download_from_baostock(stock_codes, date_str):
    """从 Baostock 下载指定日期的数据"""
    print(f"登录 Baostock...")
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return []
    
    results = []
    total = len(stock_codes)
    
    for i, code in enumerate(stock_codes, 1):
        try:
            # 转换股票代码格式
            if code.startswith('6'):
                bs_code = f"sh.{code}"
            elif code.startswith('0') or code.startswith('3'):
                bs_code = f"sz.{code}"
            elif code.startswith('8') or code.startswith('4'):
                bs_code = f"bj.{code}"
            else:
                continue
            
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg",
                start_date=date_str,
                end_date=date_str,
                frequency="d",
                adjustflag="3"
            )
            
            if rs.error_code == '0' and rs.next():
                row = rs.get_row_data()
                if row[2]:  # open 不为空
                    results.append({
                        'code': code,
                        'trade_date': date_str,
                        'open': float(row[2]) if row[2] else None,
                        'high': float(row[3]) if row[3] else None,
                        'low': float(row[4]) if row[4] else None,
                        'close': float(row[5]) if row[5] else None,
                        'preclose': float(row[6]) if row[6] else None,
                        'volume': float(row[7]) if row[7] else None,
                        'amount': float(row[8]) if row[8] else None,
                        'turnover': float(row[9]) if row[9] else None,
                        'pct_change': float(row[10]) if row[10] else None,
                    })
            
            if i % 100 == 0:
                print(f"进度: {i}/{total} ({i/total*100:.1f}%)")
                
        except Exception as e:
            print(f"错误 {code}: {e}")
    
    bs.logout()
    return results

def save_to_db(data):
    """保存数据到数据库"""
    if not data:
        print("没有数据需要保存")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    for item in data:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_prices 
                (code, trade_date, open, high, low, close, preclose, volume, amount, turnover, pct_change, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item['code'], item['trade_date'], item['open'], item['high'], 
                item['low'], item['close'], item['preclose'], item['volume'],
                item['amount'], item['turnover'], item['pct_change'], datetime.now()
            ))
            inserted += 1
        except Exception as e:
            print(f"插入错误 {item['code']}: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功保存 {inserted} 条记录")

def main():
    print(f"=== 修复 {TARGET_DATE} 缺失数据 ===")
    
    # 获取缺失的股票
    missing = get_missing_stocks()
    print(f"缺失股票数量: {len(missing)}")
    
    if not missing:
        print("数据完整，无需修复")
        return
    
    # 下载数据
    print(f"开始从 Baostock 下载...")
    data = download_from_baostock(missing, TARGET_DATE)
    print(f"下载完成: {len(data)} 条")
    
    # 保存到数据库
    save_to_db(data)
    
    # 验证
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM daily_prices WHERE trade_date = '{TARGET_DATE}'")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"修复后 {TARGET_DATE} 数据量: {count}")

if __name__ == "__main__":
    main()
