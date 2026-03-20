#!/usr/bin/env python3
"""
Baostock 数据回填脚本 - Baostock Backfill
根据完整性检查报告，使用Baostock回填缺失数据
"""

import os
import sys
import sqlite3
import json
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import baostock as bs
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
REPORT_DIR = Path('/Users/mac/.openclaw/workspace-neo/logs')
CHUNK_SIZE = 200  # Baostock批量大小
BATCH_DELAY = 2.0  # 批次间延迟（秒）
STOCK_DELAY = 0.5  # 单只股票延迟（秒）


@dataclass
class GapInfo:
    """缺口信息"""
    code: str
    name: str
    is_delisted: bool
    missing_days: int
    missing_dates: List[str]


class BaostockBackfill:
    """Baostock数据回填器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.lg = None
        self.stats = {
            'stocks_processed': 0,
            'stocks_success': 0,
            'stocks_failed': 0,
            'records_downloaded': 0,
            'records_inserted': 0,
            'records_skipped': 0,
            'records_failed': 0
        }
    
    def login(self) -> bool:
        """登录Baostock"""
        logger.info("🔐 登录Baostock...")
        self.lg = bs.login()
        if self.lg.error_code != '0':
            logger.error(f"登录失败: {self.lg.error_msg}")
            return False
        logger.info(f"✅ 登录成功")
        return True
    
    def logout(self):
        """登出"""
        if self.lg:
            bs.logout()
            logger.info("👋 已登出Baostock")
    
    def load_gap_report(self, report_path: str) -> List[GapInfo]:
        """从JSON报告加载缺口信息"""
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        gaps = []
        for r in data.get('gap_reports', []):
            if r['missing_days'] > 0:
                gaps.append(GapInfo(
                    code=r['code'],
                    name=r['name'],
                    is_delisted=r['is_delisted'],
                    missing_days=r['missing_days'],
                    missing_dates=r['missing_dates']
                ))
        
        logger.info(f"📂 加载缺口报告: {len(gaps)} 只股票需要回填")
        return gaps
    
    def load_gap_csv(self, csv_path: str) -> List[GapInfo]:
        """从CSV加载缺口信息（备用）"""
        gaps = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            next(f)  # 跳过表头
            for line in f:
                parts = line.strip().split(',', 4)  # 最多分5部分
                if len(parts) >= 4:
                    dates_str = parts[4] if len(parts) > 4 else ""
                    dates = [d for d in dates_str.strip('"').split(';') if d]
                    gaps.append(GapInfo(
                        code=parts[0],
                        name=parts[1],
                        is_delisted=parts[2] == 'True',
                        missing_days=int(parts[3]),
                        missing_dates=dates
                    ))
        
        logger.info(f"📂 加载CSV缺口文件: {len(gaps)} 只股票需要回填")
        return gaps
    
    def to_baostock_code(self, code: str) -> str:
        """转换为Baostock代码格式"""
        if code.startswith('6'):
            return f"sh.{code}"
        else:
            return f"sz.{code}"
    
    def fetch_missing_data(self, gap: GapInfo) -> List[Dict]:
        """从Baostock获取缺失数据"""
        if not gap.missing_dates:
            return []
        
        bs_code = self.to_baostock_code(gap.code)
        start_date = min(gap.missing_dates)
        end_date = max(gap.missing_dates)
        
        fields = "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg"
        
        try:
            rs = bs.query_history_k_data_plus(
                bs_code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"  # 前复权
            )
            
            if rs.error_code != '0':
                logger.warning(f"  获取 {gap.code} 数据失败: {rs.error_msg}")
                return []
            
            records = []
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()
                date_str = row[0]  # YYYY-MM-DD format
                
                # 只保留我们需要的缺失日期
                if date_str in gap.missing_dates:
                    try:
                        record = {
                            'code': gap.code,
                            'trade_date': date_str,
                            'open': float(row[2]) if row[2] else None,
                            'high': float(row[3]) if row[3] else None,
                            'low': float(row[4]) if row[4] else None,
                            'close': float(row[5]) if row[5] else None,
                            'preclose': float(row[6]) if row[6] else None,
                            'volume': float(row[7]) if row[7] else None,
                            'amount': float(row[8]) if row[8] else None,
                            'turnover': float(row[9]) if row[9] else None,
                            'pct_change': float(row[10]) if row[10] else None,
                            'updated_at': datetime.now().isoformat()
                        }
                        records.append(record)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"  解析 {gap.code} {date_str} 数据失败: {e}")
                        continue
            
            return records
            
        except Exception as e:
            logger.error(f"  获取 {gap.code} 数据异常: {e}")
            return []
    
    def upsert_to_db(self, records: List[Dict]) -> Tuple[int, int, int]:
        """UPSERT数据到数据库，返回 (插入, 跳过, 失败)"""
        if not records:
            return 0, 0, 0
        
        conn = sqlite3.connect(self.db_path)
        inserted = 0
        skipped = 0
        failed = 0
        
        for r in records:
            try:
                # 先检查是否存在
                cursor = conn.execute(
                    "SELECT id FROM daily_prices WHERE code = ? AND trade_date = ?",
                    (r['code'], r['trade_date'])
                )
                existing = cursor.fetchone()
                
                if existing:
                    # 更新现有记录
                    conn.execute(
                        """UPDATE daily_prices SET
                           open = ?, high = ?, low = ?, close = ?,
                           preclose = ?, volume = ?, amount = ?, turnover = ?,
                           pct_change = ?, updated_at = ?
                           WHERE code = ? AND trade_date = ?""",
                        (r['open'], r['high'], r['low'], r['close'],
                         r['preclose'], r['volume'], r['amount'], r['turnover'],
                         r['pct_change'], r['updated_at'],
                         r['code'], r['trade_date'])
                    )
                    skipped += 1  # 统计为已存在（更新）
                else:
                    # 插入新记录
                    conn.execute(
                        """INSERT INTO daily_prices
                           (code, trade_date, open, high, low, close, preclose,
                            volume, amount, turnover, pct_change, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (r['code'], r['trade_date'], r['open'], r['high'], r['low'],
                         r['close'], r['preclose'], r['volume'], r['amount'],
                         r['turnover'], r['pct_change'], r['updated_at'])
                    )
                    inserted += 1
                    
            except Exception as e:
                logger.warning(f"   数据库操作失败 {r['code']} {r['trade_date']}: {e}")
                failed += 1
        
        conn.commit()
        conn.close()
        
        return inserted, skipped, failed
    
    def backfill_stock(self, gap: GapInfo) -> bool:
        """回填单只股票的缺失数据"""
        logger.info(f"📥 回填 {gap.code} ({gap.name}): {gap.missing_days} 天缺失")
        
        # 获取数据
        records = self.fetch_missing_data(gap)
        
        if not records:
            logger.warning(f"  ⚠️ 未获取到 {gap.code} 的数据")
            self.stats['stocks_failed'] += 1
            return False
        
        self.stats['records_downloaded'] += len(records)
        
        # 写入数据库
        inserted, skipped, failed = self.upsert_to_db(records)
        self.stats['records_inserted'] += inserted
        self.stats['records_skipped'] += skipped
        self.stats['records_failed'] += failed
        
        logger.info(f"  ✅ 插入 {inserted} 条, 更新 {skipped} 条, 失败 {failed} 条")
        
        if inserted > 0 or skipped > 0:
            self.stats['stocks_success'] += 1
        else:
            self.stats['stocks_failed'] += 1
        
        return inserted > 0
    
    def run_backfill(self, gaps: List[GapInfo], max_stocks: Optional[int] = None):
        """执行批量回填"""
        if not self.login():
            return
        
        try:
            # 限制处理数量
            if max_stocks and len(gaps) > max_stocks:
                logger.info(f"📝 限制处理前 {max_stocks} 只股票")
                gaps = gaps[:max_stocks]
            
            total = len(gaps)
            logger.info(f"🚀 开始回填 {total} 只股票")
            
            # 按批次处理
            for i in range(0, total, CHUNK_SIZE):
                chunk = gaps[i:i + CHUNK_SIZE]
                chunk_num = i // CHUNK_SIZE + 1
                total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                logger.info(f"\n📦 批次 {chunk_num}/{total_chunks} (股票 {i+1}-{min(i+CHUNK_SIZE, total)})")
                
                for j, gap in enumerate(chunk, 1):
                    self.backfill_stock(gap)
                    self.stats['stocks_processed'] += 1
                    
                    # 单只股票延迟
                    if j < len(chunk):
                        time.sleep(STOCK_DELAY)
                
                # 批次间延迟（除了最后一批）
                if i + CHUNK_SIZE < total:
                    logger.info(f"⏱️  批次完成，暂停 {BATCH_DELAY} 秒...")
                    time.sleep(BATCH_DELAY)
            
            logger.info("\n" + "="*60)
            logger.info("✅ 回填完成!")
            
        finally:
            self.logout()
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n" + "="*60)
        print("📊 Baostock 回填统计")
        print("="*60)
        print(f"处理股票: {self.stats['stocks_processed']}")
        print(f"成功回填: {self.stats['stocks_success']}")
        print(f"回填失败: {self.stats['stocks_failed']}")
        print("-"*60)
        print(f"下载记录: {self.stats['records_downloaded']}")
        print(f"插入记录: {self.stats['records_inserted']}")
        print(f"更新记录: {self.stats['records_skipped']}")
        print(f"失败记录: {self.stats['records_failed']}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Baostock数据回填工具')
    parser.add_argument('--report', '-r', help='完整性检查报告JSON文件路径')
    parser.add_argument('--csv', '-c', help='缺口摘要CSV文件路径（备用）')
    parser.add_argument('--max-stocks', '-n', type=int, help='最多处理N只股票')
    parser.add_argument('--stock', '-s', help='回填单只股票（如: 000001）')
    parser.add_argument('--dates', '-d', help='指定日期范围（如: 2024-09-02,2024-09-10）')
    
    args = parser.parse_args()
    
    backfill = BaostockBackfill()
    
    if args.stock:
        # 单只股票模式
        if not args.dates:
            logger.error("请使用 --dates 指定日期范围（逗号分隔）")
            return
        
        start, end = args.dates.split(',')
        gap = GapInfo(
            code=args.stock,
            name=args.stock,
            is_delisted=False,
            missing_days=0,
            missing_dates=[]  # 将由Baostock查询决定
        )
        # 生成日期列表
        from datetime import datetime, timedelta
        current = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        while current <= end_dt:
            gap.missing_dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        gap.missing_days = len(gap.missing_dates)
        
        backfill.run_backfill([gap])
        
    elif args.report:
        # 从JSON报告加载
        report_path = args.report
        if not os.path.isabs(report_path):
            report_path = str(REPORT_DIR / report_path)
        
        gaps = backfill.load_gap_report(report_path)
        backfill.run_backfill(gaps, max_stocks=args.max_stocks)
        
    elif args.csv:
        # 从CSV加载
        csv_path = args.csv
        if not os.path.isabs(csv_path):
            csv_path = str(REPORT_DIR / csv_path)
        
        gaps = backfill.load_gap_csv(csv_path)
        backfill.run_backfill(gaps, max_stocks=args.max_stocks)
        
    else:
        parser.print_help()
        logger.error("\n请提供 --report、--csv 或 --stock 参数")
        return
    
    backfill.print_summary()


if __name__ == '__main__':
    main()
