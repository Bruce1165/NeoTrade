#!/usr/bin/env python3
"""
交易日历模块 - Trading Calendar

功能：
- 自动跳过周末和节假日
- 从数据库推断最近有效交易日
- 提供统一的交易日历接口
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# A股节假日（2024-2026年主要节假日，需要定期更新）
HOLIDAYS_2024_2026 = {
    # 2024年 (补录数据范围起始)
    '2024-09-16', '2024-09-17',  # 中秋节 (9/15周日, 9/16-17调休)
    '2024-10-01', '2024-10-02', '2024-10-03', '2024-10-04', '2024-10-07',  # 国庆 (10/5-6周末)
    # 2025年
    '2025-01-01',  # 元旦
    '2025-01-28', '2025-01-29', '2025-01-30', '2025-01-31',  # 春节
    '2025-02-01', '2025-02-02', '2025-02-03', '2025-02-04',
    '2025-04-04', '2025-04-05', '2025-04-06',  # 清明
    '2025-05-01', '2025-05-02', '2025-05-03', '2025-05-04', '2025-05-05',  # 劳动节
    '2025-05-31', '2025-06-01', '2025-06-02',  # 端午
    '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04', '2025-10-05',  # 国庆
    '2025-10-06', '2025-10-07', '2025-10-08',
    # 2026年
    '2026-01-01', '2026-01-02', '2026-01-03',  # 元旦
    '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20', '2026-02-21',  # 春节
    '2026-02-22', '2026-02-23', '2026-02-24', '2026-02-25',
    '2026-04-04', '2026-04-05', '2026-04-06',  # 清明
    '2026-05-01', '2026-05-02', '2026-05-03', '2026-05-04', '2026-05-05',  # 劳动节
    '2026-06-19', '2026-06-20', '2026-06-21',  # 端午
    '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05',  # 国庆
    '2026-10-06', '2026-10-07', '2026-10-08',
}


class TradingCalendar:
    """交易日历类"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 自动推断数据库路径
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(os.path.dirname(script_dir), "data", "stock_data.db")
        self.db_path = db_path
        self._holidays = HOLIDAYS_2024_2026.copy()
        self._trading_days_cache = None
        self._cache_date = None
    
    def is_trading_day(self, date: datetime) -> bool:
        """检查是否为交易日"""
        date_str = date.strftime('%Y-%m-%d')
        
        # 检查周末
        if date.weekday() >= 5:  # 周六=5, 周日=6
            return False
        
        # 检查节假日
        if date_str in self._holidays:
            return False
        
        return True
    
    def is_trading_day_str(self, date_str: str) -> bool:
        """检查是否为交易日（字符串输入）"""
        date = datetime.strptime(date_str, '%Y-%m-%d')
        return self.is_trading_day(date)
    
    def get_trading_days_from_db(self, start_date: str, end_date: str) -> List[str]:
        """从数据库获取交易日列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT DISTINCT trade_date 
                FROM daily_prices 
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))
            conn.close()
            
            if not df.empty:
                return df['trade_date'].tolist()
            return []
        except Exception as e:
            logger.error(f"Error getting trading days from DB: {e}")
            return []
    
    def get_recent_trading_day(self, date_str: Optional[str] = None, 
                               direction: str = 'backward') -> str:
        """
        获取最近的有效交易日
        
        Args:
            date_str: 参考日期，默认为今天
            direction: 'backward' 向前找，'forward' 向后找
        
        Returns:
            最近的有效交易日字符串
        """
        if date_str is None:
            date = datetime.now()
        else:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # 先从数据库查询
        if direction == 'backward':
            start_date = (date - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = date.strftime('%Y-%m-%d')
        else:
            start_date = date.strftime('%Y-%m-%d')
            end_date = (date + timedelta(days=30)).strftime('%Y-%m-%d')
        
        trading_days = self.get_trading_days_from_db(start_date, end_date)
        
        if trading_days:
            if direction == 'backward':
                # 返回最近的交易日（小于等于参考日期）
                for d in reversed(trading_days):
                    if d <= date.strftime('%Y-%m-%d'):
                        return d
            else:
                # 返回最近的交易日（大于等于参考日期）
                for d in trading_days:
                    if d >= date.strftime('%Y-%m-%d'):
                        return d
        
        # 如果数据库没有数据，使用计算方式
        return self._calculate_trading_day(date, direction)
    
    def _calculate_trading_day(self, date: datetime, direction: str) -> str:
        """计算最近交易日（当数据库不可用时）"""
        current = date
        delta = timedelta(days=-1) if direction == 'backward' else timedelta(days=1)
        
        max_attempts = 30
        attempts = 0
        
        while attempts < max_attempts:
            if self.is_trading_day(current):
                return current.strftime('%Y-%m-%d')
            current += delta
            attempts += 1
        
        raise ValueError(f"Cannot find trading day within {max_attempts} days")
    
    def get_n_trading_days_ago(self, n: int, date_str: Optional[str] = None) -> str:
        """获取N个交易日前的日期"""
        if date_str is None:
            date_str = self.get_recent_trading_day()
        
        # 从数据库获取足够多的交易日
        end_date = date_str
        start_date = (datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=n*2)).strftime('%Y-%m-%d')
        
        trading_days = self.get_trading_days_from_db(start_date, end_date)
        
        if len(trading_days) >= n + 1:
            # 找到date_str在列表中的位置
            if date_str in trading_days:
                idx = trading_days.index(date_str)
                target_idx = idx - n
                if target_idx >= 0:
                    return trading_days[target_idx]
        
        # 回退到计算方式
        current = datetime.strptime(date_str, '%Y-%m-%d')
        count = 0
        while count < n:
            current -= timedelta(days=1)
            if self.is_trading_day(current):
                count += 1
        
        return current.strftime('%Y-%m-%d')
    
    def get_trading_days_window(self, end_date: str, n_days: int) -> List[str]:
        """
        获取以end_date结尾的N个交易日列表
        
        Args:
            end_date: 结束日期
            n_days: 交易日数量
        
        Returns:
            交易日列表（包含end_date）
        """
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=n_days*2)).strftime('%Y-%m-%d')
        trading_days = self.get_trading_days_from_db(start_date, end_date)
        
        if len(trading_days) >= n_days:
            return trading_days[-n_days:]
        
        return trading_days
    
    def get_next_trading_day(self, date_str: str) -> str:
        """获取下一个交易日"""
        return self.get_recent_trading_day(date_str, direction='forward')
    
    def get_previous_trading_day(self, date_str: str) -> str:
        """获取上一个交易日"""
        return self.get_recent_trading_day(date_str, direction='backward')


# 全局实例
def get_calendar(db_path: str = "data/stock_data.db") -> TradingCalendar:
    """获取交易日历实例"""
    return TradingCalendar(db_path)


def get_recent_trading_day(date_str: Optional[str] = None, 
                           db_path: str = "data/stock_data.db") -> str:
    """便捷函数：获取最近交易日"""
    calendar = get_calendar(db_path)
    return calendar.get_recent_trading_day(date_str)


if __name__ == '__main__':
    # 测试
    calendar = TradingCalendar()
    
    print("Testing Trading Calendar:")
    print(f"Today is trading day: {calendar.is_trading_day(datetime.now())}")
    print(f"Recent trading day: {calendar.get_recent_trading_day()}")
    print(f"5 trading days ago: {calendar.get_n_trading_days_ago(5)}")
    print(f"Trading days window (10 days): {calendar.get_trading_days_window(calendar.get_recent_trading_day(), 10)}")
