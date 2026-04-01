#!/usr/bin/env python3
"""
修复 stocks 表缺失的基本面数据
使用 iFind 或 AKShare 获取行业、市值、估值数据
"""
import sqlite3
import sys
from pathlib import Path
import akshare as ak
import pandas as pd
from datetime import datetime
import time

DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"

def get_stocks_needing_update():
    """获取需要更新基本面数据的股票"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT code, name FROM stocks 
        WHERE industry IS NULL OR industry = '' 
        OR total_market_cap IS NULL
        LIMIT 100
    """)
    stocks = cursor.fetchall()
    conn.close()
    return stocks

def fetch_stock_basic():
    """从 AKShare 获取股票基本信息"""
    print("获取股票基本信息...")
    try:
        df = ak.stock_zh_a_spot_em()
        return df
    except Exception as e:
        print(f"获取失败: {e}")
        return None

def update_stocks_basic():
    """更新 stocks 表基本面数据"""
    df = fetch_stock_basic()
    if df is None or df.empty:
        print("无法获取数据")
        return
    
    # 重命名列以匹配数据库
    column_mapping = {
        '代码': 'code',
        '名称': 'name',
        '行业': 'industry',
        '总市值': 'total_market_cap',
        '流通市值': 'circulating_market_cap',
        '市净率': 'pb_ratio',
        '市盈率-动态': 'pe_ratio',
    }
    
    df = df.rename(columns=column_mapping)
    
    # 只保留需要的列
    needed_cols = ['code', 'industry', 'total_market_cap', 'circulating_market_cap', 'pb_ratio', 'pe_ratio']
    df = df[[col for col in needed_cols if col in df.columns]]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated = 0
    for _, row in df.iterrows():
        try:
            code = str(row['code']).strip()
            
            # 转换市值单位（万元 -> 元）
            total_cap = row.get('total_market_cap')
            if pd.notna(total_cap):
                total_cap = float(total_cap) * 10000
            
            circulate_cap = row.get('circulating_market_cap')
            if pd.notna(circulate_cap):
                circulate_cap = float(circulate_cap) * 10000
            
            pb = row.get('pb_ratio')
            if pd.notna(pb):
                pb = float(pb)
            
            pe = row.get('pe_ratio')
            if pd.notna(pe):
                pe = float(pe)
            
            industry = row.get('industry')
            if pd.notna(industry):
                industry = str(industry)
            
            cursor.execute("""
                UPDATE stocks SET
                    industry = COALESCE(?, industry),
                    total_market_cap = COALESCE(?, total_market_cap),
                    circulating_market_cap = COALESCE(?, circulating_market_cap),
                    pb_ratio = COALESCE(?, pb_ratio),
                    pe_ratio = COALESCE(?, pe_ratio),
                    ifind_updated_at = ?
                WHERE code = ?
            """, (industry, total_cap, circulate_cap, pb, pe, datetime.now(), code))
            
            if cursor.rowcount > 0:
                updated += 1
                
        except Exception as e:
            print(f"更新 {row.get('code')} 失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"成功更新 {updated} 只股票的基本面数据")

def verify_update():
    """验证更新结果"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN industry IS NOT NULL AND industry != '' THEN 1 END) as has_industry,
            COUNT(CASE WHEN total_market_cap IS NOT NULL THEN 1 END) as has_market_cap,
            COUNT(CASE WHEN pb_ratio IS NOT NULL THEN 1 END) as has_pb,
            COUNT(CASE WHEN pe_ratio IS NOT NULL THEN 1 END) as has_pe
        FROM stocks
    """)
    row = cursor.fetchone()
    conn.close()
    
    print("\n=== 更新后统计 ===")
    print(f"总股票数: {row[0]}")
    print(f"有行业数据: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"有市值数据: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    print(f"有市净率: {row[3]} ({row[3]/row[0]*100:.1f}%)")
    print(f"有市盈率: {row[4]} ({row[4]/row[0]*100:.1f}%)")

def main():
    print("=== 修复 stocks 表基本面数据 ===\n")
    
    # 更新数据
    update_stocks_basic()
    
    # 验证
    verify_update()

if __name__ == "__main__":
    main()
