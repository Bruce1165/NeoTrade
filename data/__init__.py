"""
数据源模块
提供统一的数据源抽象和管理
"""

from data.sources.base import DataSource, StockData, ScreenerResult
from data.sources.baostock_source import BaostockSource
from data.sources.ifind_source import IfindSource
from data.source_manager import DataSourceManager, DataSourceUnavailable

__all__ = [
    'DataSource',
    'StockData',
    'ScreenerResult',
    'BaostockSource',
    'IfindSource',
    'DataSourceManager',
    'DataSourceUnavailable'
]