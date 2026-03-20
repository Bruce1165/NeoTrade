#!/usr/bin/env python3
"""
快速修复 03-17 缺失数据
"""
import sqlite3
import baostock as bs
from datetime import datetime
import time

DB_PATH = 'data/stock_data.db'
TARGET_DATE = '2026-03-17'

# 获取所有股票
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute('SELECT code FROM stocks')
all_stocks = [row[0] for row in cursor.fetchall()]

# 获取已有数据
cursor.execute('SELECT DISTINCT code FROM daily_prices WHERE trade_date = ?', (TARGET_DATE,))
existing = {row[0] for row in cursor.fetchall()}
conn.close()

# 需要下载的股票
missing = [s for s in all_stocks if s not in existing]
print(f"总股票: {len(all_stocks)}")
print(f"已有: {len(existing)}")
print(f"缺失: {len(missing)}")

# 登录
lg = bs.login()
print(f"登录: {lg.error_msg}")

batch_data = []
failed = []

for i, code in enumerate(missing):
    try:
        bs_code = f"sh.{code}" if code.startswith('6') else f"sz.{code}"
        rs = bs.query_history_k_data_plus(
            code=bs_code,
            fields='date,code,open,high,low,close,preclose,volume,amount,turn,pctChg',
            start_date=TARGET_DATE,
            end_date=TARGET_DATE
        )
        
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            batch_data.append({
                'trade_date': row[0],
                'code': code,
                'open': float(row[2]) if row[2] else None,
                'high': float(row[3]) if row[3] else None,
                'low': float(row[4]) if row[4] else None,
                'close': float(row[5]) if row[5] else None,
                'preclose': float(row[6]) if row[6] else None,
                'volume': int(float(row[7])) if row[7] else None,
                'amount': float(row[8]) if row[8] else None,
                'turnover': float(row[9]) if row[9] else None,
                'pct_change': float(row[10]) if row[10] else None
            })
        
        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(missing)}, 成功: {len(batch_data)}, 失败: {len(failed)}")
            # 批量插入
            if batch_data:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                for item in batch_data:
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO daily_prices 
                            (trade_date, code, open, high, low, close, preclose, volume, amount, turnover, pct_change)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (item['trade_date'], item['code'], item['open'], item['high'], 
                              item['low'], item['close'], item['preclose'], item['volume'],
                              item['amount'], item['turnover'], item['pct_change']))
                    except Exception as e:
                        pass
                conn.commit()
                conn.close()
                batch_data = []
        
        time.sleep(0.02)
    except Exception as e:
        failed.append(code)

# 最后一批插入
if batch_data:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for item in batch_data:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_prices 
                (trade_date, code, open, high, low, close, preclose, volume, amount, turnover, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item['trade_date'], item['code'], item['open'], item['high'], 
                  item['low'], item['close'], item['preclose'], item['volume'],
                  item['amount'], item['turnover'], item['pct_change']))
        except:
            pass
    conn.commit()
    conn.close()

bs.logout()

# 检查结果
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM daily_prices WHERE trade_date = ?', (TARGET_DATE,))
final_count = cursor.fetchone()[0]
conn.close()

print(f"\n✅ 完成！03-17 数据: {final_count} 条")
