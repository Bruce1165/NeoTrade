#!/usr/bin/env python3
"""
数据源抽象基类
定义所有数据源的统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class StockData:
    """统一的股票数据模型"""
    code: str                    # 股票代码（统一格式：600000）
    name: str                    # 股票名称
    close: float                 # 收盘价
    change: float               # 涨跌额
    change_ratio: float         # 涨跌幅（%）
    volume: float               # 成交量
    amount: float               # 成交额
    timestamp: datetime         # 数据时间
    source: str                 # 数据来源：baostock/ifind
    
    # 可选字段
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    turnover: Optional[float] = None  # 换手率
    preclose: Optional[float] = None


@dataclass  
class ScreenerResult:
    """统一的筛选结果模型"""
    screener_id: str
    screener_name: str
    run_date: str               # YYYY-MM-DD
    run_time: datetime
    stocks: List[StockData]
    total_checked: int
    data_source: str            # baostock/ifind
    execution_time_ms: int
    error_message: Optional[str] = None


class DataSource(ABC):
    """数据源抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass
    
    @abstractmethod
    def get_stock_data(self, code: str, date: Optional[str] = None) -> StockData:
        """获取单只股票数据"""
        pass
    
    @abstractmethod
    def get_all_stocks(self, date: Optional[str] = None) -> List[StockData]:
        """获取所有股票数据"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass
    
    @abstractmethod
    def get_date_range(self) -> tuple:
        """获取数据日期范围 (start_date, end_date)"""
        pass