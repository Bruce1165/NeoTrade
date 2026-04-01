#!/usr/bin/env python3
"""
检查项目文件完整性
"""
import os

files_to_check = [
    'strategy_config.py',
    'signal_generator.py',
    'backtest_engine.py',
    'position_sizer.py',
    'strategy_backtest.py',
    'dashboard_tracker.py',
    'run_baseline.py',
    'launch_autoresearch.py',
    'autoresearch.config.md',
    'README_STRATEGY.md',
]

print("=" * 60)
print("NeoTrade 策略回测框架 - 文件检查")
print("=" * 60)

for f in files_to_check:
    path = f'/Users/mac/.openclaw/workspace-neo/{f}'
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✓ {f:<30} ({size:,} bytes)")
    else:
        print(f"✗ {f:<30} (缺失)")

print("=" * 60)

# 检查数据库连接
try:
    import sqlite3
    conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_daily")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily")
    date_range = cursor.fetchone()
    conn.close()
    print(f"\n✓ 数据库连接正常")
    print(f"  总记录数: {count:,}")
    print(f"  日期范围: {date_range[0]} 至 {date_range[1]}")
except Exception as e:
    print(f"\n✗ 数据库连接失败: {e}")

print("\n" + "=" * 60)
print("框架就绪，可以运行: python run_baseline.py")
print("=" * 60)
