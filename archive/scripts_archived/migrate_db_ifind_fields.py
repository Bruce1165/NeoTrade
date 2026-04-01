#!/usr/bin/env python3
"""
数据库迁移脚本 - 扩展 stocks 表字段
添加 iFind 提供的额外字段
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')

def migrate():
    """执行数据库迁移"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 开始数据库迁移...")
    
    # 检查现有字段
    cursor.execute("PRAGMA table_info(stocks)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"   现有字段: {existing_columns}")
    
    # 要添加的新字段
    new_fields = [
        ('sector_lv1', 'VARCHAR(50)', '申万行业分类（一级板块）'),
        ('sector_lv2', 'VARCHAR(50)', '同花顺行业分类（二级板块）'),
        ('pe_ratio', 'REAL', '市盈率'),
        ('roe', 'REAL', '净资产收益率 ROE'),
        ('debt_ratio', 'REAL', '资产负债率'),
        ('revenue', 'REAL', '营业收入（亿元）'),
        ('profit', 'REAL', '净利润（亿元）'),
        ('ifind_updated_at', 'DATETIME', 'iFind数据更新时间'),
    ]
    
    for field_name, field_type, comment in new_fields:
        if field_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE stocks ADD COLUMN {field_name} {field_type}")
                print(f"   ✅ 添加字段: {field_name} ({comment})")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️  字段 {field_name} 可能已存在: {e}")
        else:
            print(f"   ⏭️  字段已存在: {field_name}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ 数据库迁移完成")
    
    # 显示更新后的表结构
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(stocks)")
    columns = cursor.fetchall()
    print("\n📋 更新后的 stocks 表结构:")
    print("-" * 60)
    for col in columns:
        print(f"   {col[1]:<20} {col[2]:<15} {'NULL' if col[3] == 0 else 'NOT NULL'}")
    conn.close()

if __name__ == '__main__':
    migrate()
