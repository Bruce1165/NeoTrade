#!/usr/bin/env python3
"""
Baostock 本地数据库数据源实现
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.sources.base import DataSource, StockData

logger = logging.getLogger(__name__)


class BaostockSource(DataSource):
    """本地 SQLite 数据库数据源"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        
    @property
    def name(self) -> str:
        return "baostock"
    
    def _get_connection(self):
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _close_connection(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def is_available(self) -> bool:
        """检查数据库是否可连接"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT 1 FROM daily_prices LIMIT 1")
            cursor.fetchone()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Baostock 数据源不可用: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM daily_prices")
            total_records = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
            latest_date = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_prices")
            total_days = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "status": "healthy",
                "total_records": total_records,
                "latest_date": latest_date,
                "total_days": total_days
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_date_range(self) -> tuple:
        """获取数据日期范围"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices")
        row = cursor.fetchone()
        conn.close()
        return (row[0], row[1]) if row else (None, None)
    
    def get_stock_data(self, code: str, date: Optional[str] = None) -> StockData:
        """获取单只股票数据"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT dp.*, s.name 
            FROM daily_prices dp
            LEFT JOIN stocks s ON dp.code = s.code
            WHERE dp.code = ? AND dp.trade_date = ?
        """, (code, date))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise ValueError(f"Stock {code} not found for date {date}")
        
        return self._row_to_stock_data(row, date)
    
    def get_all_stocks(self, date: Optional[str] = None) -> List[StockData]:
        """获取所有股票数据"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT dp.*, s.name 
            FROM daily_prices dp
            LEFT JOIN stocks s ON dp.code = s.code
            WHERE dp.trade_date = ? AND dp.close > 0
        """, (date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_stock_data(row, date) for row in rows]
    
    def _row_to_stock_data(self, row: sqlite3.Row, date: str) -> StockData:
        """将数据库行转换为 StockData"""
        return StockData(
            code=row['code'],
            name=row['name'] or '',
            close=float(row['close']) if row['close'] else 0.0,
            change=float(row['change']) if row['change'] else 0.0,
            change_ratio=float(row['pct_change']) if row['pct_change'] else 0.0,
            volume=float(row['volume']) if row['volume'] else 0.0,
            amount=float(row['amount']) if row['amount'] else 0.0,
            timestamp=datetime.strptime(date, '%Y-%m-%d'),
            source='baostock',
            open=float(row['open']) if row['open'] else None,
            high=float(row['high']) if row['high'] else None,
            low=float(row['low']) if row['low'] else None,
            turnover=float(row['turnover']) if row['turnover'] else None,
            preclose=float(row['preclose']) if row['preclose'] else None
        )