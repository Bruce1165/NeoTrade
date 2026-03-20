#!/usr/bin/env python3
"""
后台数据同步脚本 - Background Data Sync
运行顺序:
1. iFind 补充最近60天数据
2. Baostock 下载完整历史（2025-07至今）
3. 更新股票属性（板块、市值、财务）
4. 标识退市股票

用法: python3 background_sync.py > /tmp/sync.log 2>&1 &
"""

import os
import sys
import time
import json
import logging
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/background_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 路径配置
WORKSPACE = Path('/Users/mac/.openclaw/workspace-neo')
DB_PATH = WORKSPACE / 'data' / 'stock_data.db'
PID_FILE = Path('/tmp/background_sync.pid')
PROGRESS_FILE = Path('/tmp/background_sync_progress.json')

# 添加 Python 路径
sys.path.insert(0, str(WORKSPACE / 'scripts'))
sys.path.insert(0, '/Users/mac/pilot-ifind')


class BackgroundSync:
    """后台数据同步器"""
    
    def __init__(self):
        self.db_path = str(DB_PATH)
        self.progress = self.load_progress()
        
        # 延迟导入（避免启动时加载失败）
        self.ifind_client = None
        self.mcp_client = None
    
    def load_progress(self) -> dict:
        """加载进度"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            'status': 'idle',
            'phase': None,
            'started_at': None,
            'completed_at': None,
            'stats': {}
        }
    
    def save_progress(self):
        """保存进度"""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def init_ifind(self):
        """初始化 iFind 客户端"""
        if self.ifind_client is None:
            from src.client import IfindClient
            from src.mcp_client import IfindMCPClient
            self.ifind_client = IfindClient()
            self.mcp_client = IfindMCPClient('stock')
    
    # ==================== Phase 1: iFind 60天补充 ====================
    
    def phase1_ifind_fill(self, max_stocks: int = None):
        """Phase 1: 用 iFind 补充最近60天数据"""
        logger.info("=" * 60)
        logger.info("🚀 Phase 1: iFind 60天数据补充")
        logger.info("=" * 60)
        
        self.init_ifind()
        self.progress['phase'] = 'ifind_60d'
        self.progress['status'] = 'running'
        self.save_progress()
        
        # 获取需要补充的活跃股票
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT code FROM stocks WHERE is_delisted = 0 OR is_delisted IS NULL"
        )
        all_codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # 检查每只股票最近60天的数据
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        need_fill = []
        
        conn = sqlite3.connect(self.db_path)
        for code in all_codes[:max_stocks or len(all_codes)]:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE code = ? AND trade_date >= ?",
                (code, start_date)
            )
            count = cursor.fetchone()[0]
            if count < 40:  # 少于40天认为需要补充
                need_fill.append(code)
        conn.close()
        
        logger.info(f"📊 发现 {len(need_fill)} 只股票需要补充60天数据")
        
        # 开始补充
        total_filled = 0
        for i, code in enumerate(need_fill, 1):
            filled = self._fill_single_stock_ifind(code)
            if filled > 0:
                total_filled += filled
                logger.info(f"[{i}/{len(need_fill)}] {code}: ✅ 补充 {filled} 天")
            
            if i % 100 == 0:
                self.progress['stats'] = {
                    'processed': i,
                    'total': len(need_fill),
                    'filled': total_filled
                }
                self.save_progress()
                logger.info(f"📈 进度: {i}/{len(need_fill)}, 已补充 {total_filled} 条")
        
        logger.info(f"✅ Phase 1 完成: 补充 {total_filled} 条数据")
        self.progress['stats']['phase1_filled'] = total_filled
        self.save_progress()
        
        return total_filled
    
    def _fill_single_stock_ifind(self, code: str) -> int:
        """从 iFind 补充单只股票"""
        try:
            ifind_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            end = datetime.now()
            start = end - timedelta(days=70)  # 多取几天
            
            params = {
                'codes': ifind_code,
                'indicators': 'open,high,low,close,volume,amount,changeRatio',
                'startdate': start.strftime('%Y%m%d'),
                'enddate': end.strftime('%Y%m%d'),
                'functionpara': {'Fill': 'Blank'}
            }
            
            result = self.ifind_client.post('cmd_history_quotation', params)
            tables = result.get('tables', [])
            
            if not tables:
                return 0
            
            table = tables[0]
            time_list = table.get('time', [])
            table_data = table.get('table', {})
            
            if not time_list:
                return 0
            
            # 构建记录
            records = []
            cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            
            for i, date_str in enumerate(time_list):
                if date_str < cutoff:
                    continue
                
                record = (
                    code, date_str,
                    table_data.get('open', [None]*100)[i],
                    table_data.get('high', [None]*100)[i],
                    table_data.get('low', [None]*100)[i],
                    table_data.get('close', [None]*100)[i],
                    table_data.get('volume', [None]*100)[i],
                    table_data.get('amount', [None]*100)[i],
                    table_data.get('changeRatio', [None]*100)[i],
                    datetime.now().isoformat()
                )
                records.append(record)
            
            # 批量插入
            if records:
                conn = sqlite3.connect(self.db_path)
                conn.executemany(
                    """INSERT OR REPLACE INTO daily_prices 
                       (code, trade_date, open, high, low, close, volume, amount, pct_change, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    records
                )
                conn.commit()
                conn.close()
                return len(records)
            
            return 0
            
        except Exception as e:
            logger.debug(f"填充 {code} 失败: {e}")
            return 0
    
    # ==================== Phase 2: Baostock 下载 ====================
    
    def phase2_baostock_download(self):
        """Phase 2: Baostock 下载完整历史"""
        logger.info("=" * 60)
        logger.info("🚀 Phase 2: Baostock 历史数据下载")
        logger.info("=" * 60)
        
        self.progress['phase'] = 'baostock_download'
        self.save_progress()
        
        # 调用现有的下载脚本
        try:
            result = subprocess.run(
                ['python3', str(WORKSPACE / 'scripts' / 'update_daily_chunked.py')],
                capture_output=True,
                text=True,
                timeout=7200  # 2小时超时
            )
            
            if result.returncode == 0:
                logger.info("✅ Baostock 下载完成")
                self.progress['stats']['baostock_status'] = 'success'
            else:
                logger.error(f"❌ Baostock 下载失败: {result.stderr}")
                self.progress['stats']['baostock_status'] = 'failed'
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Baostock 下载超时")
            self.progress['stats']['baostock_status'] = 'timeout'
        except Exception as e:
            logger.error(f"❌ Baostock 下载错误: {e}")
            self.progress['stats']['baostock_status'] = f'error: {e}'
        
        self.save_progress()
    
    # ==================== Phase 3: 更新股票属性 ====================
    
    def phase3_update_attributes(self, max_stocks: int = None):
        """Phase 3: 更新股票属性（板块、市值、财务）"""
        logger.info("=" * 60)
        logger.info("🚀 Phase 3: 更新股票属性")
        logger.info("=" * 60)
        
        self.init_ifind()
        self.progress['phase'] = 'update_attributes'
        self.save_progress()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT code FROM stocks WHERE is_delisted = 0 OR is_delisted IS NULL"
        )
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if max_stocks:
            codes = codes[:max_stocks]
        
        logger.info(f"📊 开始更新 {len(codes)} 只股票属性")
        
        updated = 0
        for i, code in enumerate(codes, 1):
            try:
                self._update_single_stock_attributes(code)
                updated += 1
                
                if i % 50 == 0:
                    logger.info(f"📈 进度: {i}/{len(codes)}, 已更新 {updated}")
                    self.progress['stats']['attributes_updated'] = updated
                    self.save_progress()
                    
            except Exception as e:
                logger.warning(f"更新 {code} 失败: {e}")
        
        logger.info(f"✅ Phase 3 完成: 更新 {updated} 只股票属性")
        self.progress['stats']['phase3_updated'] = updated
        self.save_progress()
    
    def _update_single_stock_attributes(self, code: str):
        """更新单只股票属性"""
        try:
            ifind_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            
            # 获取财务数据
            result = self.mcp_client.call_tool(
                'get_stock_financials',
                {'query': f'{ifind_code} 所属申万行业 所属同花顺行业 总市值 流通市值 市盈率 ROE'}
            )
            
            if not isinstance(result, dict) or result.get('code') != 1:
                return
            
            answer = result.get('data', {}).get('answer', '')
            
            # 解析数据
            import re
            data = {}
            
            # 提取申万行业
            match = re.search(r'所属申万行业\|([^|]+)', answer)
            if match:
                data['sector_lv1'] = match.group(1).strip()
            
            # 提取同花顺行业
            match = re.search(r'所属同花顺行业\|([^|]+)', answer)
            if match:
                data['sector_lv2'] = match.group(1).strip()
            
            # 提取总市值
            match = re.search(r'总市值.*?([\d.]+)亿', answer)
            if match:
                data['total_market_cap'] = float(match.group(1))
            
            # 提取流通市值
            match = re.search(r'流通市值.*?([\d.]+)亿', answer)
            if match:
                data['circulating_market_cap'] = float(match.group(1))
            
            # 更新数据库
            if data:
                conn = sqlite3.connect(self.db_path)
                fields = []
                values = []
                for k, v in data.items():
                    fields.append(f"{k} = ?")
                    values.append(v)
                
                if fields:
                    values.append(code)
                    query = f"UPDATE stocks SET {', '.join(fields)}, ifind_updated_at = ? WHERE code = ?"
                    values.insert(-1, datetime.now().isoformat())
                    conn.execute(query, values)
                    conn.commit()
                conn.close()
                
        except Exception as e:
            logger.debug(f"更新 {code} 属性失败: {e}")
    
    # ==================== Phase 4: 标识退市股票 ====================
    
    def phase4_mark_delisted(self):
        """Phase 4: 标识退市股票"""
        logger.info("=" * 60)
        logger.info("🚀 Phase 4: 标识退市股票")
        logger.info("=" * 60)
        
        self.init_ifind()
        self.progress['phase'] = 'mark_delisted'
        self.save_progress()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT code FROM stocks WHERE is_delisted = 0 OR is_delisted IS NULL"
        )
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"📊 检查 {len(codes)} 只股票状态")
        
        delisted = []
        for i, code in enumerate(codes, 1):
            try:
                is_active, last_date = self._check_stock_status(code)
                
                if not is_active and last_date:
                    delisted.append((code, last_date))
                    
                    conn = sqlite3.connect(self.db_path)
                    conn.execute(
                        "UPDATE stocks SET is_delisted = 1, last_trade_date = ? WHERE code = ?",
                        (last_date, code)
                    )
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"[{i}/{len(codes)}] {code}: 🔴 退市/停牌 (最后交易 {last_date})")
                
                if i % 100 == 0:
                    logger.info(f"📈 进度: {i}/{len(codes)}, 发现 {len(delisted)} 只退市")
                    self.progress['stats']['delisted_count'] = len(delisted)
                    self.save_progress()
                    
            except Exception as e:
                logger.debug(f"检查 {code} 失败: {e}")
        
        logger.info(f"✅ Phase 4 完成: 标识 {len(delisted)} 只退市股票")
        self.progress['stats']['phase4_delisted'] = len(delisted)
        self.save_progress()
    
    def _check_stock_status(self, code: str) -> Tuple[bool, Optional[str]]:
        """检查股票是否活跃"""
        try:
            ifind_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            end = datetime.now()
            start = end - timedelta(days=10)
            
            params = {
                'codes': ifind_code,
                'indicators': 'close',
                'startdate': start.strftime('%Y%m%d'),
                'enddate': end.strftime('%Y%m%d'),
                'functionpara': {'Fill': 'Blank'}
            }
            
            result = self.ifind_client.post('cmd_history_quotation', params)
            tables = result.get('tables', [])
            
            if tables and tables[0].get('time'):
                dates = tables[0]['time']
                last_date = dates[-1]
                last_trade = datetime.strptime(last_date, '%Y-%m-%d')
                is_active = (end - last_trade).days <= 5
                return is_active, last_date
            else:
                return False, None
                
        except:
            return True, None  # 默认活跃
    
    # ==================== 主流程 ====================
    
    def run_full_sync(self):
        """运行完整同步流程"""
        logger.info("=" * 60)
        logger.info("🚀 启动后台数据同步")
        logger.info("=" * 60)
        
        self.progress['status'] = 'running'
        self.progress['started_at'] = datetime.now().isoformat()
        self.save_progress()
        
        # 写入 PID 文件
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            # Phase 1: iFind 60天补充
            self.phase1_ifind_fill()
            
            # Phase 2: Baostock 下载
            self.phase2_baostock_download()
            
            # Phase 3: 更新属性（只更新一部分，避免太慢）
            self.phase3_update_attributes(max_stocks=500)
            
            # Phase 4: 标识退市
            self.phase4_mark_delisted()
            
            self.progress['status'] = 'completed'
            self.progress['completed_at'] = datetime.now().isoformat()
            logger.info("=" * 60)
            logger.info("✅ 所有阶段完成！")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 同步失败: {e}")
            self.progress['status'] = 'failed'
            self.progress['error'] = str(e)
        
        finally:
            self.save_progress()
            if PID_FILE.exists():
                PID_FILE.unlink()


def check_status():
    """检查同步状态"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
        
        print("📊 同步状态:")
        print(f"   状态: {progress.get('status', 'unknown')}")
        print(f"   当前阶段: {progress.get('phase', 'N/A')}")
        print(f"   开始时间: {progress.get('started_at', 'N/A')}")
        print(f"   统计: {json.dumps(progress.get('stats', {}), indent=2)}")
        
        if PID_FILE.exists():
            with open(PID_FILE, 'r') as f:
                pid = f.read().strip()
            print(f"   进程PID: {pid}")
    else:
        print("⚠️  暂无同步记录")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='后台数据同步')
    parser.add_argument('--status', action='store_true', help='查看同步状态')
    parser.add_argument('--stop', action='store_true', help='停止同步')
    args = parser.parse_args()
    
    if args.status:
        check_status()
        return
    
    if args.stop:
        if PID_FILE.exists():
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)
            print(f"✅ 已发送停止信号到进程 {pid}")
        else:
            print("⚠️  没有运行中的同步进程")
        return
    
    # 检查是否已有进程在运行
    if PID_FILE.exists():
        with open(PID_FILE, 'r') as f:
            pid = f.read().strip()
        print(f"⚠️  已有同步进程在运行 (PID: {pid})")
        print("   使用 --status 查看状态")
        print("   使用 --stop 停止当前进程")
        return
    
    # 启动同步
    sync = BackgroundSync()
    sync.run_full_sync()


if __name__ == '__main__':
    main()
