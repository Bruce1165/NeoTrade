#!/usr/bin/env python3
"""
Add data availability check to all screeners
"""
import re
from pathlib import Path

SCRIPTS_DIR = Path("/Users/mac/.openclaw/workspace-neo/scripts")

# List of screeners that need the check
screeners = [
    "jin_feng_huang_screener.py",
    "yin_feng_huang_screener.py",
    "shi_pan_xian_screener.py",
    "shuang_shou_ban_screener.py",
    "breakout_main_screener.py",
    "zhang_ting_bei_liang_yin_screener.py",
    "ascending_triangle_screener.py",
    "double_bottom_screener.py",
    "breakout_20day_screener.py",
    "high_tight_flag_screener.py",
    "ashare_21_screener.py",
]

CHECK_CODE = '''        if date_str:
            self.current_date = date_str
        
        # 检查数据是否可用
        if not self.check_data_availability(self.current_date):
            logger.warning(f"⚠️  无可用数据 ({self.current_date}) - 市场尚未收盘或数据未下载")
            return [{
                'code': 'STATUS',
                'name': 'No Data',
                'message': f'无可用数据 ({self.current_date})，市场尚未收盘或数据未下载',
                'error': 'no_data'
            }]
'''

for screener_file in screeners:
    filepath = SCRIPTS_DIR / screener_file
    if not filepath.exists():
        print(f"❌ Not found: {screener_file}")
        continue
    
    content = filepath.read_text(encoding='utf-8')
    
    # Check if already has the check
    if 'check_data_availability' in content:
        print(f"✅ Already has check: {screener_file}")
        continue
    
    # Find the run_screening method and add check after the docstring
    # Pattern: def run_screening(...):\n        """..."""\n        [logger or code]
    
    pattern = r'(def run_screening\([^)]+\):\s*\n\s+"""[^"]*"""\s*\n)(\s+logger\.|\s+self\.|\s+if |\s+print\(|\s+#)'
    
    def replacer(m):
        return m.group(1) + CHECK_CODE + m.group(2)
    
    new_content = re.sub(pattern, replacer, content, count=1)
    
    if new_content == content:
        # Try alternative pattern (no docstring)
        pattern2 = r'(def run_screening\([^)]+\):\s*\n)(\s+logger\.|\s+self\.|\s+if |\s+print\(|\s+#|\s+"""[^"]*"""\s*\n)'
        new_content = re.sub(pattern2, replacer, content, count=1)
    
    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
        print(f"✅ Updated: {screener_file}")
    else:
        print(f"⚠️  Could not update: {screener_file}")

print("\nDone!")
