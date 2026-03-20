#!/usr/bin/env python3
"""
Initialize database with default screeners
"""
import os
import sys
from pathlib import Path

# Add paths
DASHBOARD_DIR = Path(__file__).parent
sys.path.insert(0, str(DASHBOARD_DIR))

from models import init_db, register_screener

# Default screeners
DEFAULT_SCREENERS = [
    ('coffee_cup_screener', '咖啡杯形态筛选器', '欧奈尔咖啡杯形态选股', 'screener'),
    ('jin_feng_huang_screener', '涨停金凤凰筛选器', '涨停板后回调形态', 'screener'),
    ('er_ban_hui_tiao_screener', '二板回调筛选器', '二板涨停后回调选股', 'screener'),
    ('zhang_ting_bei_liang_yin_screener', '涨停倍量阴筛选器', '涨停后放量阴线选股', 'screener'),
    ('yin_feng_huang_screener', '涨停银凤凰筛选器', '银凤凰回调形态', 'screener'),
    ('shi_pan_xian_screener', '试盘线筛选器', '试盘线突破选股', 'screener'),
    ('breakout_20day_screener', '20日突破筛选器', '20日新高突破', 'screener'),
    ('breakout_main_screener', '主图突破筛选器', '主图技术指标突破', 'screener'),
    ('daily_hot_cold_screener', '每日热冷股筛选器', '每日热股和冷股筛选', 'screener'),
    ('ashare_21_screener', 'A股21天筛选器', 'A股21天周期筛选', 'screener'),
    ('double_bottom_screener', '双底形态筛选器', '双底形态选股', 'screener'),
    ('flat_base_screener', '平底形态筛选器', '欧奈尔平底形态', 'screener'),
    ('high_tight_flag_screener', '高紧旗形筛选器', '高紧旗形突破', 'screener'),
    ('ascending_triangle_screener', '上升三角形筛选器', '上升三角形突破', 'screener'),
]

def init_screeners():
    """Initialize default screeners"""
    init_db()
    
    count = 0
    for name, display_name, description, category in DEFAULT_SCREENERS:
        try:
            register_screener(name, display_name, description, '', category)
            print(f"✅ Registered: {display_name}")
            count += 1
        except Exception as e:
            print(f"⚠️  {display_name}: {e}")
    
    print(f"\n总计: {count} 个筛选器已初始化")
    return count

if __name__ == '__main__':
    init_screeners()
