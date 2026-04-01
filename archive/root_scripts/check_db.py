#!/usr/bin/env python3
"""快速检查数据库结构"""
import sqlite3

conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
cursor = conn.cursor()

# 检查现有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("现有表:", [t[0] for t in tables])

# 检查stock_daily表结构
cursor.execute("PRAGMA table_info(stock_daily)")
columns = cursor.fetchall()
print("\nstock_daily 列:", [c[1] for c in columns])

# 检查日期范围
cursor.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM stock_daily")
date_range = cursor.fetchone()
print(f"\n数据日期范围: {date_range[0]} 到 {date_range[1]}")
print(f"交易日数量: {date_range[2]}")

# 检查2024-09-02到2025-08-31的数据
cursor.execute("""
    SELECT COUNT(DISTINCT trade_date) FROM stock_daily 
    WHERE trade_date BETWEEN '2024-09-02' AND '2025-08-31'
""")
train_days = cursor.fetchone()[0]
print(f"训练集交易日: {train_days}")

# 检查2025-09-01之后的数据（应该被屏蔽）
cursor.execute("""
    SELECT COUNT(DISTINCT trade_date) FROM stock_daily 
    WHERE trade_date > '2025-08-31'
""")
shielded_days = cursor.fetchone()[0]
print(f"屏蔽数据交易日: {shielded_days} (验证集中，训练时不可见)")

conn.close()
