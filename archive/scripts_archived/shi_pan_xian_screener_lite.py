#!/usr/bin/env python3
"""
涨停试盘线筛选器 - 使用纯 sqlite3 实现，避免 SQLAlchemy 连接问题
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = '/Users/mac/.openclaw/workspace-neo/data/stock_data.db'

class ShiPanXianScreenerLite:
    """涨停试盘线筛选器 - Lite版本"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.consolidation_days = 20
        self.high_volume_lookback = 30
        self.volume_shrink_threshold = 0.25
        self.callback_max_days = 10
        self.breakout_volume_ratio = 1.5
        self.current_date = datetime.now().strftime('%Y-%m-%d')
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
    
    def get_stock_data(self, code, days=150):
        """获取股票数据"""
        query = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """
        conn = self._get_conn()
        df = pd.read_sql_query(query, conn, params=(code, days))
        conn.close()
        
        if df.empty:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        return df
    
    def check_single_stock(self, code, date_str=None):
        """检查单个股票"""
        if date_str:
            self.current_date = date_str
        
        # Get stock name
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM stocks WHERE code = ?", (code,))
        row = cursor.fetchone()
        name = row[0] if row else ''
        conn.close()
        
        df = self.get_stock_data(code, days=150)
        if df is None or len(df) < 50:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少50天）'],
                'details': {}
            }
        
        # Simplified check - just check if there was a recent limit up
        recent = df.tail(20)
        limit_up_days = recent[recent['pct_change'] >= 9.9]
        
        if len(limit_up_days) == 0:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['近20天无涨停'],
                'details': {
                    '近期最高涨幅': f"{recent['pct_change'].max():.2f}%"
                }
            }
        
        # Check volume pattern
        latest = df.iloc[-1]
        avg_volume_20 = df.tail(20)['volume'].mean()
        volume_ratio = latest['volume'] / avg_volume_20 if avg_volume_20 > 0 else 0
        
        return {
            'match': True,
            'code': code,
            'name': name,
            'date': self.current_date,
            'reasons': [],
            'details': {
                '近20天涨停次数': len(limit_up_days),
                '最新涨幅': f"{latest['pct_change']:.2f}%",
                '量比': f"{volume_ratio:.2f}",
                '换手率': f"{latest['turnover']:.2f}%"
            }
        }

# Backward compatibility
ShiPanXianScreener = ShiPanXianScreenerLite
