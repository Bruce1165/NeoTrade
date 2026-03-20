#!/usr/bin/env python3
"""
iFind 实时数据同步到本地数据库
每天收盘后同步当天数据到 daily_prices 表
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

# 添加路径
WORKSPACE = Path('/Users/mac/.openclaw/workspace-neo')
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / 'dashboard'))

import pandas as pd
from ifind_realtime import RealtimeFeed
from ifind_client import IfindClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = WORKSPACE / 'data' / 'stock_data.db'


class IfindToDbSync:
    """iFind 数据同步器"""
    
    def __init__(self):
        self.feed = RealtimeFeed()
        self.db_path = str(DB_PATH)
        
    def get_all_stock_codes(self) -> List[str]:
        """从数据库获取所有股票代码"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT DISTINCT code FROM stocks")
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        logger.info(f"获取到 {len(codes)} 只股票代码")
        return codes
    
    def to_ifind_code(self, code: str) -> str:
        """转换为 iFind 格式"""
        code = str(code).strip()
        return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
    
    def from_ifind_code(self, ifind_code: str) -> str:
        """从 iFind 格式转换"""
        return ifind_code.split('.')[0] if '.' in ifind_code else ifind_code
    
    def fetch_realtime_data(self, codes: List[str]) -> pd.DataFrame:
        """从 iFind 获取实时数据"""
        # 转换为 iFind 格式
        ifind_codes = [self.to_ifind_code(c) for c in codes]
        
        # 分批获取（每次最多100只）
        all_data = []
        batch_size = 100
        
        for i in range(0, len(ifind_codes), batch_size):
            batch = ifind_codes[i:i + batch_size]
            try:
                df = self.feed.fetch(
                    batch, 
                    indicators="open,high,low,latest,change,changeRatio,volume,amount,preClose,turnoverRatio"
                )
                all_data.append(df)
                logger.info(f"获取批次 {i//batch_size + 1}: {len(batch)} 只")
            except Exception as e:
                logger.error(f"获取批次失败: {e}")
                continue
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()
    
    def transform_to_db_format(self, df: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        """转换为数据库格式"""
        if df.empty:
            return df
        
        # 重命名列
        column_map = {
            'thscode': 'code',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'latest': 'close',
            'change': 'change',
            'changeRatio': 'pct_change',
            'volume': 'volume',
            'amount': 'amount',
            'preClose': 'preclose',
            'turnoverRatio': 'turnover'
        }
        
        # 选择并重命名列
        df = df.rename(columns=column_map)
        
        # 提取纯代码
        df['code'] = df['code'].apply(self.from_ifind_code)
        
        # 添加日期
        df['trade_date'] = trade_date
        
        # 转换数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'change', 'pct_change', 
                       'volume', 'amount', 'preclose', 'turnover']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 选择需要的列
        required_cols = ['code', 'trade_date', 'open', 'high', 'low', 'close', 
                        'volume', 'amount', 'turnover', 'preclose', 'pct_change']
        
        # 过滤停牌股票（close 为 0 或 NaN）
        df = df[df['close'].notna() & (df['close'] != 0)]
        
        return df[required_cols]
    
    def upsert_to_db(self, df: pd.DataFrame) -> int:
        """写入数据库（UPSERT 逻辑）"""
        if df.empty:
            logger.warning("没有数据需要写入")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        
        for _, row in df.iterrows():
            try:
                # 检查是否存在
                cursor.execute(
                    "SELECT id FROM daily_prices WHERE code = ? AND trade_date = ?",
                    (row['code'], row['trade_date'])
                )
                existing = cursor.fetchone()
                
                if existing:
                    # 更新
                    cursor.execute("""
                        UPDATE daily_prices 
                        SET open = ?, high = ?, low = ?, close = ?,
                            volume = ?, amount = ?, turnover = ?, preclose = ?, 
                            pct_change = ?, updated_at = ?
                        WHERE code = ? AND trade_date = ?
                    """, (
                        row['open'], row['high'], row['low'], row['close'],
                        row['volume'], row['amount'], row['turnover'], row['preclose'],
                        row['pct_change'], datetime.now(),
                        row['code'], row['trade_date']
                    ))
                    updated += 1
                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO daily_prices 
                        (code, trade_date, open, high, low, close, volume, amount, 
                         turnover, preclose, pct_change, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['code'], row['trade_date'], row['open'], row['high'], 
                        row['low'], row['close'], row['volume'], row['amount'],
                        row['turnover'], row['preclose'], row['pct_change'], datetime.now()
                    ))
                    inserted += 1
                    
            except Exception as e:
                logger.error(f"写入 {row['code']} 失败: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        logger.info(f"插入: {inserted}, 更新: {updated}")
        return inserted + updated
    
    def sync(self, trade_date: Optional[str] = None) -> Dict:
        """执行同步"""
        if trade_date is None:
            trade_date = date.today().strftime('%Y-%m-%d')
        
        logger.info(f"开始同步数据: {trade_date}")
        
        # 1. 获取股票代码
        codes = self.get_all_stock_codes()
        
        # 2. 获取实时数据
        logger.info("从 iFind 获取实时数据...")
        df = self.fetch_realtime_data(codes)
        
        if df.empty:
            logger.error("未能获取到数据")
            return {'success': False, 'error': 'No data fetched'}
        
        logger.info(f"获取到 {len(df)} 条数据")
        
        # 3. 转换格式
        df = self.transform_to_db_format(df, trade_date)
        logger.info(f"转换后 {len(df)} 条有效数据")
        
        # 4. 写入数据库
        count = self.upsert_to_db(df)
        
        return {
            'success': True,
            'trade_date': trade_date,
            'total_stocks': len(codes),
            'fetched': len(df),
            'written': count
        }


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='同步 iFind 数据到本地数据库')
    parser.add_argument('--date', help='交易日期 (YYYY-MM-DD)，默认今天')
    args = parser.parse_args()
    
    sync = IfindToDbSync()
    result = sync.sync(args.date)
    
    if result['success']:
        print(f"✅ 同步完成: {result['written']} 只股票")
    else:
        print(f"❌ 同步失败: {result.get('error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
