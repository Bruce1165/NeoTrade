#!/usr/bin/env python3
"""
阈值测试脚本 - 比较 iFind 历史数据 vs 本地 DB 的耗时
"""

import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/dashboard')
sys.path.insert(0, '/Users/mac/pilot-ifind/src')

from ifind_history import IfindHistory
from ifind_realtime import RealtimeFeed

DB_PATH = Path('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')

def get_all_codes():
    """获取所有股票代码"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT DISTINCT code FROM daily_prices LIMIT 100")  # 先测100只
    codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return codes

def test_ifind_history(codes, days):
    """测试 iFind 获取历史数据"""
    print(f"\n🌐 iFind Historical - {len(codes)} stocks, {days} days")
    
    history = IfindHistory()
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    start_time = time.time()
    try:
        df = history.fetch_history(codes, start_date, end_date)
        elapsed = time.time() - start_time
        print(f"   ✅ Success: {len(df)} records, {elapsed:.2f}s")
        return elapsed, len(df)
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed: {e}, {elapsed:.2f}s")
        return elapsed, 0

def test_ifind_realtime(codes):
    """测试 iFind 实时数据"""
    print(f"\n⚡ iFind Realtime - {len(codes)} stocks")
    
    feed = RealtimeFeed()
    ifind_codes = [f"{c}.SH" if c.startswith('6') else f"{c}.SZ" for c in codes]
    
    start_time = time.time()
    try:
        df = feed.fetch(ifind_codes)
        elapsed = time.time() - start_time
        print(f"   ✅ Success: {len(df)} records, {elapsed:.2f}s")
        return elapsed, len(df)
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed: {e}, {elapsed:.2f}s")
        return elapsed, 0

def test_local_db(codes, days):
    """测试本地 DB 查询"""
    print(f"\n💾 Local DB - {len(codes)} stocks, {days} days")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    start_time = time.time()
    try:
        conn = sqlite3.connect(DB_PATH)
        placeholders = ','.join(['?' for _ in codes])
        query = f"""
            SELECT * FROM daily_prices 
            WHERE code IN ({placeholders}) 
            AND trade_date >= ?
            ORDER BY code, trade_date
        """
        import pandas as pd
        df = pd.read_sql(query, conn, params=codes + [start_date])
        conn.close()
        elapsed = time.time() - start_time
        print(f"   ✅ Success: {len(df)} records, {elapsed:.2f}s")
        return elapsed, len(df)
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"   ❌ Failed: {e}, {elapsed:.2f}s")
        return elapsed, 0

def main():
    print("=" * 60)
    print("📊 阈值测试 - iFind vs Local DB")
    print("=" * 60)
    
    # 获取股票代码
    codes = get_all_codes()
    print(f"\n📈 测试股票数: {len(codes)}")
    
    results = []
    
    # Test 1: iFind Realtime (1 day equivalent)
    t, n = test_ifind_realtime(codes)
    results.append(('iFind Realtime', 1, t, n))
    
    # Test 2: iFind Historical 30 days
    t, n = test_ifind_history(codes, 30)
    results.append(('iFind History', 30, t, n))
    
    # Test 3: iFind Historical 60 days
    t, n = test_ifind_history(codes, 60)
    results.append(('iFind History', 60, t, n))
    
    # Test 4: Local DB 60 days
    t, n = test_local_db(codes, 60)
    results.append(('Local DB', 60, t, n))
    
    # Test 5: Local DB 90 days
    t, n = test_local_db(codes, 90)
    results.append(('Local DB', 90, t, n))
    
    # Test 6: Local DB 250 days (coffee cup)
    t, n = test_local_db(codes, 250)
    results.append(('Local DB', 250, t, n))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)
    print(f"{'Source':<20} {'Days':<8} {'Time(s)':<12} {'Records':<10}")
    print("-" * 60)
    for source, days, t, n in results:
        print(f"{source:<20} {days:<8} {t:<12.2f} {n:<10}")
    
    # Find threshold
    print("\n" + "=" * 60)
    print("🎯 阈值建议")
    print("=" * 60)
    
    # Find where iFind becomes slower than acceptable
    ACCEPTABLE = 30  # seconds
    ifind_60 = next((t for s, d, t, _ in results if s == 'iFind History' and d == 60), None)
    
    if ifind_60 and ifind_60 > ACCEPTABLE:
        print(f"⚠️  iFind 60天耗时 {ifind_60:.1f}s > {ACCEPTABLE}s 阈值")
        print(f"✅ 建议阈值: 30-60 天之间")
    elif ifind_60:
        print(f"✅ iFind 60天耗时 {ifind_60:.1f}s ≤ {ACCEPTABLE}s")
        print(f"✅ 建议阈值: 60天")
    
    print(f"\n☕ 咖啡杯需要 250 天 → 必须使用 Local DB")

if __name__ == '__main__':
    main()
