#!/usr/bin/env python3
"""
混合数据补充策略
Phase 1: iFind 补充最近60天 + 标识退市股票
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Set

sys.path.insert(0, '/Users/mac/pilot-ifind')
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

from src.client import IfindClient
from src.mcp_client import IfindMCPClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
FILL_DAYS = 60  # iFind 补充最近60天


class HybridDataFiller:
    """混合数据补充器"""
    
    def __init__(self):
        self.ifind_client = IfindClient()
        self.mcp_client = IfindMCPClient('stock')
        self.db_path = str(DB_PATH)
    
    def add_delisted_flag(self):
        """添加退市标识字段到 stocks 表"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("ALTER TABLE stocks ADD COLUMN is_delisted INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE stocks ADD COLUMN last_trade_date DATE")
            conn.commit()
            logger.info("✅ 添加退市标识字段")
        except sqlite3.OperationalError:
            logger.info("⏭️  字段已存在")
        conn.close()
    
    def check_stock_status(self, code: str) -> Tuple[bool, str]:
        """
        检查股票状态
        返回: (是否活跃, 最后交易日期)
        """
        try:
            # 使用 iFind 获取最近5天数据
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
                # 如果最后交易日期在5天内，认为是活跃的
                last_trade = datetime.strptime(last_date, '%Y-%m-%d')
                is_active = (end - last_trade).days <= 5
                return is_active, last_date
            else:
                return False, None
                
        except Exception as e:
            logger.warning(f"检查 {code} 状态失败: {e}")
            return True, None  # 默认活跃
    
    def mark_delisted_stocks(self, sample_size: int = 100):
        """标识退市股票"""
        logger.info("🔍 开始检查股票状态（退市标识）...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT code FROM stocks WHERE is_delisted IS NULL OR is_delisted = 0 LIMIT ?", (sample_size,))
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        delisted = []
        active = []
        
        for i, code in enumerate(codes, 1):
            is_active, last_date = self.check_stock_status(code)
            
            if not is_active and last_date:
                # 超过5天无交易，可能是退市或停牌
                delisted.append((code, last_date))
                logger.info(f"[{i}/{len(codes)}] {code}: 🔴 最后交易 {last_date}")
            else:
                active.append(code)
            
            if i % 20 == 0:
                logger.info(f"📈 进度: {i}/{len(codes)}, 发现 {len(delisted)} 只可能退市")
        
        # 更新数据库
        conn = sqlite3.connect(self.db_path)
        for code, last_date in delisted:
            conn.execute(
                "UPDATE stocks SET is_delisted = 1, last_trade_date = ? WHERE code = ?",
                (last_date, code)
            )
        conn.commit()
        conn.close()
        
        logger.info(f"✅ 完成: 标识 {len(delisted)} 只可能退市股票")
        return delisted
    
    def get_active_stocks(self) -> List[str]:
        """获取活跃股票列表（非退市）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT code FROM stocks WHERE is_delisted = 0 OR is_delisted IS NULL"
        )
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        return codes
    
    def find_recent_gaps(self, days: int = 60) -> List[Tuple[str, int]]:
        """找出最近N天有数据缺口的活跃股票"""
        logger.info(f"🔍 扫描最近 {days} 天的数据缺口...")
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        
        # 只检查活跃股票
        cursor = conn.execute(
            "SELECT code FROM stocks WHERE is_delisted = 0 OR is_delisted IS NULL"
        )
        active_codes = [row[0] for row in cursor.fetchall()]
        
        gaps = []
        for code in active_codes:
            cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE code = ? AND trade_date >= ?",
                (code, start_date)
            )
            count = cursor.fetchone()[0]
            
            # 预计交易日（排除周末约等于 days * 5/7）
            expected = int(days * 5 / 7)
            if count < expected * 0.9:  # 少于90%认为有缺口
                gaps.append((code, count, expected - count))
        
        conn.close()
        
        # 按缺口大小排序
        gaps.sort(key=lambda x: x[2], reverse=True)
        
        total_gaps = sum(g for _, _, g in gaps)
        logger.info(f"📊 发现 {len(gaps)} 只活跃股票有缺口，总计 {total_gaps} 天")
        
        return gaps
    
    def fill_from_ifind(self, code: str, days: int = 60) -> int:
        """从 iFind 补充单只股票最近N天数据"""
        ifind_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        
        end = datetime.now()
        start = end - timedelta(days=days + 10)  # 多取几天确保覆盖
        
        params = {
            'codes': ifind_code,
            'indicators': 'open,high,low,close,volume,amount,changeRatio',
            'startdate': start.strftime('%Y%m%d'),
            'enddate': end.strftime('%Y%m%d'),
            'functionpara': {'Fill': 'Blank'}
        }
        
        try:
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
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            for i, date_str in enumerate(time_list):
                if date_str < cutoff_date:
                    continue  # 只保留最近N天
                
                try:
                    record = {
                        'code': code,
                        'trade_date': date_str,
                        'open': table_data.get('open', [None]*len(time_list))[i],
                        'high': table_data.get('high', [None]*len(time_list))[i],
                        'low': table_data.get('low', [None]*len(time_list))[i],
                        'close': table_data.get('close', [None]*len(time_list))[i],
                        'volume': table_data.get('volume', [None]*len(time_list))[i],
                        'amount': table_data.get('amount', [None]*len(time_list))[i],
                        'pct_change': table_data.get('changeRatio', [None]*len(time_list))[i],
                    }
                    records.append(record)
                except:
                    continue
            
            # 插入数据库
            if records:
                conn = sqlite3.connect(self.db_path)
                inserted = 0
                for r in records:
                    try:
                        conn.execute(
                            """INSERT OR REPLACE INTO daily_prices 
                               (code, trade_date, open, high, low, close, volume, amount, pct_change, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (r['code'], r['trade_date'], r['open'], r['high'], r['low'],
                             r['close'], r['volume'], r['amount'], r['pct_change'],
                             datetime.now().isoformat())
                        )
                        inserted += 1
                    except:
                        continue
                conn.commit()
                conn.close()
                return inserted
            
            return 0
            
        except Exception as e:
            logger.warning(f"获取 {code} 失败: {e}")
            return 0
    
    def run_phase1(self, max_stocks: int = None):
        """执行 Phase 1: 退市标识 + iFind 60天补充"""
        logger.info("=" * 60)
        logger.info("🚀 Phase 1: 退市标识 + iFind 60天数据补充")
        logger.info("=" * 60)
        
        # Step 1: 添加字段
        self.add_delisted_flag()
        
        # Step 2: 标识退市股票（先处理100只测试）
        delisted = self.mark_delisted_stocks(sample_size=100)
        
        # Step 3: 找出有缺口的活跃股票
        gaps = self.find_recent_gaps(days=FILL_DAYS)
        
        if max_stocks:
            gaps = gaps[:max_stocks]
        
        # Step 4: 用 iFind 补充
        logger.info(f"🌐 开始用 iFind 补充 {len(gaps)} 只股票最近{FILL_DAYS}天数据...")
        
        total_filled = 0
        quota_used = 0
        
        for i, (code, have, missing) in enumerate(gaps, 1):
            filled = self.fill_from_ifind(code, days=FILL_DAYS)
            if filled > 0:
                total_filled += filled
                quota_used += filled
                logger.info(f"[{i}/{len(gaps)}] {code}: ✅ 补充 {filled} 天")
            else:
                logger.info(f"[{i}/{len(gaps)}] {code}: ⚠️ 无数据")
            
            if i % 50 == 0:
                logger.info(f"📈 进度: {i}/{len(gaps)}, 已补充 {total_filled} 条, 配额使用 {quota_used}")
        
        logger.info("=" * 60)
        logger.info(f"✅ Phase 1 完成:")
        logger.info(f"   - 标识 {len(delisted)} 只退市股票")
        logger.info(f"   - 补充 {total_filled} 条数据")
        logger.info(f"   - iFind 配额使用: {quota_used}/1,000,000 ({quota_used/10000:.1f}%)")
        logger.info("=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='混合数据补充 Phase 1')
    parser.add_argument('--max', type=int, help='最多处理多少只股票（测试用）')
    args = parser.parse_args()
    
    filler = HybridDataFiller()
    filler.run_phase1(max_stocks=args.max)


if __name__ == '__main__':
    main()
