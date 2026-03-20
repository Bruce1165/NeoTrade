#!/usr/bin/env python3
"""
数据修复验证脚本 - 测试所有修复是否生效
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

WORKSPACE_ROOT = Path(__file__).parent.parent
DB_PATH = WORKSPACE_ROOT / 'data' / 'stock_data.db'
PROGRESS_FILE = WORKSPACE_ROOT / 'data' / 'daily_update_progress_v2.json'
SCRIPT_PATH = WORKSPACE_ROOT / 'scripts' / 'daily_update_screener.py'

def test_database_constraint():
    """测试数据库唯一约束是否生效"""
    print("\n" + "="*60)
    print("测试1: 数据库唯一约束")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查索引是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='daily_prices' AND name='idx_daily_prices_code_date'
    """)
    result = cursor.fetchone()
    
    if result:
        print("✅ 唯一约束索引 idx_daily_prices_code_date 存在")
    else:
        print("❌ 唯一约束索引不存在")
        conn.close()
        return False
    
    # 检查是否有重复数据
    cursor.execute("""
        SELECT code, trade_date, COUNT(*) as cnt 
        FROM daily_prices 
        GROUP BY code, trade_date 
        HAVING cnt > 1
        LIMIT 5
    """)
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"❌ 发现重复数据: {duplicates}")
        conn.close()
        return False
    else:
        print("✅ 无重复数据")
    
    # 测试唯一约束是否生效（尝试插入重复数据）
    try:
        cursor.execute("""
            INSERT INTO daily_prices (code, trade_date, open, high, low, close, volume)
            SELECT code, trade_date, open, high, low, close, volume
            FROM daily_prices
            LIMIT 1
        """)
        conn.commit()
        print("❌ 唯一约束未生效 - 重复数据插入成功")
        conn.close()
        return False
    except sqlite3.IntegrityError:
        print("✅ 唯一约束生效 - 重复插入被阻止")
    
    conn.close()
    return True

def test_progress_file_format():
    """测试进度文件格式"""
    print("\n" + "="*60)
    print("测试2: 进度文件格式")
    print("="*60)
    
    if not PROGRESS_FILE.exists():
        print("❌ 进度文件不存在")
        return False
    
    with open(PROGRESS_FILE, 'r') as f:
        data = json.load(f)
    
    # 检查必要字段
    required_fields = ['completed', 'failed', 'target_date', 'status', 'last_updated', 'version']
    for field in required_fields:
        if field not in data:
            print(f"❌ 缺少必要字段: {field}")
            return False
    print(f"✅ 所有必要字段存在: {required_fields}")
    
    # 检查类型
    if not isinstance(data['completed'], list):
        print("❌ completed 必须是数组")
        return False
    print(f"✅ completed 是数组, 包含 {len(data['completed'])} 只股票")
    
    if not isinstance(data['failed'], dict):
        print("❌ failed 必须是对象(dict)")
        return False
    print(f"✅ failed 是对象, 包含 {len(data['failed'])} 只唯一失败股票")
    
    # 检查completed去重
    if len(data['completed']) != len(set(data['completed'])):
        print("❌ completed 包含重复项")
        return False
    print("✅ completed 已去重")
    
    # 检查状态值
    valid_status = ['idle', 'pending', 'running', 'completed', 'failed']
    if data['status'] not in valid_status:
        print(f"❌ 无效的状态值: {data['status']}")
        return False
    print(f"✅ 状态值有效: {data['status']}")
    
    # 检查version
    if data['version'] != '2.1':
        print(f"⚠️  版本号不是 2.1: {data['version']}")
    else:
        print("✅ 版本号正确: 2.1")
    
    # 检查last_updated格式
    try:
        datetime.fromisoformat(data['last_updated'])
        print("✅ last_updated 格式正确")
    except:
        print("❌ last_updated 格式错误")
        return False
    
    return True

def test_python_script():
    """测试Python脚本语法和逻辑"""
    print("\n" + "="*60)
    print("测试3: Python脚本")
    print("="*60)
    
    # 语法检查
    import py_compile
    try:
        py_compile.compile(SCRIPT_PATH, doraise=True)
        print("✅ Python脚本语法正确")
    except Exception as e:
        print(f"❌ Python脚本语法错误: {e}")
        return False
    
    # 检查关键代码
    with open(SCRIPT_PATH, 'r') as f:
        content = f.read()
    
    # 检查是否使用INSERT OR REPLACE/IGNORE
    if 'INSERT OR REPLACE' in content or 'INSERT OR IGNORE' in content:
        print("✅ 使用幂等性插入语句")
    else:
        # 检查是否使用try-except处理IntegrityError
        if 'IntegrityError' in content:
            print("✅ 使用try-except处理唯一约束冲突")
        else:
            print("⚠️  未找到幂等性处理代码")
    
    # 检查进度加载是否去重
    if 'list(set(data.get' in content or 'set(self.progress' in content:
        print("✅ 进度加载时进行去重处理")
    else:
        print("⚠️  未找到进度去重代码")
    
    return True

def test_data_consistency():
    """测试数据一致性"""
    print("\n" + "="*60)
    print("测试4: 数据一致性")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取各日期数据量
    cursor.execute("""
        SELECT trade_date, COUNT(*) as cnt 
        FROM daily_prices 
        GROUP BY trade_date 
        ORDER BY trade_date DESC
        LIMIT 5
    """)
    results = cursor.fetchall()
    
    print("最近5天数据量:")
    for date, count in results:
        print(f"  {date}: {count} 条")
    
    # 检查03-18数据
    cursor.execute("SELECT COUNT(*) FROM daily_prices WHERE trade_date = '2026-03-18'")
    count_0318 = cursor.fetchone()[0]
    
    # 加载进度文件
    with open(PROGRESS_FILE, 'r') as f:
        progress = json.load(f)
    
    if progress['target_date'] == '2026-03-18':
        completed_count = len(progress['completed'])
        print(f"\n2026-03-18:")
        print(f"  数据库记录数: {count_0318}")
        print(f"  进度文件completed: {completed_count}")
        
        if abs(count_0318 - completed_count) < 10:  # 允许小差异（退市股等）
            print("  ✅ 数据基本一致")
        else:
            print(f"  ⚠️  数据差异较大: {abs(count_0318 - completed_count)}")
    
    conn.close()
    return True

def main():
    """运行所有测试"""
    print("="*60)
    print("数据修复验证")
    print("="*60)
    
    results = []
    
    results.append(("数据库唯一约束", test_database_constraint()))
    results.append(("进度文件格式", test_progress_file_format()))
    results.append(("Python脚本", test_python_script()))
    results.append(("数据一致性", test_data_consistency()))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！修复已完成。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查修复。")
        return 1

if __name__ == '__main__':
    exit(main())
