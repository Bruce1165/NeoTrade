#!/usr/bin/env python3
"""
数据源管理器
管理多个数据源，提供自动切换和统一接口
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

from data.sources.base import DataSource, StockData, ScreenerResult

logger = logging.getLogger(__name__)


class DataSourceManager:
    """管理多个数据源，提供自动切换"""
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.primary_source: Optional[str] = None
        self.fallback_source: Optional[str] = None
        self._cache: Dict[str, Any] = {}
    
    def register(self, source: DataSource, primary: bool = False, fallback: bool = False):
        """注册数据源
        
        Args:
            source: 数据源实例
            primary: 是否设为主数据源
            fallback: 是否设为备用数据源
        """
        self.sources[source.name] = source
        
        if primary:
            self.primary_source = source.name
            logger.info(f"设置主数据源: {source.name}")
        
        if fallback:
            self.fallback_source = source.name
            logger.info(f"设置备用数据源: {source.name}")
    
    def get_primary(self) -> Optional[DataSource]:
        """获取主数据源"""
        if self.primary_source and self.primary_source in self.sources:
            return self.sources[self.primary_source]
        return None
    
    def get_fallback(self) -> Optional[DataSource]:
        """获取备用数据源"""
        if self.fallback_source and self.fallback_source in self.sources:
            return self.sources[self.fallback_source]
        return None
    
    def get_stock_data(self, code: str, date: Optional[str] = None, 
                       allow_fallback: bool = True) -> StockData:
        """获取单只股票数据（自动处理降级）
        
        Args:
            code: 股票代码
            date: 日期，默认今天
            allow_fallback: 是否允许降级到备用数据源
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 先尝试主数据源
        primary = self.get_primary()
        if primary and primary.is_available():
            try:
                return primary.get_stock_data(code, date)
            except Exception as e:
                logger.warning(f"主数据源 {primary.name} 获取 {code} 失败: {e}")
        
        # 降级到备用数据源
        if allow_fallback:
            fallback = self.get_fallback()
            if fallback and fallback.is_available():
                try:
                    return fallback.get_stock_data(code, date)
                except Exception as e:
                    logger.error(f"备用数据源 {fallback.name} 获取 {code} 失败: {e}")
        
        raise DataSourceUnavailable(f"无法获取股票 {code} 数据，所有数据源均不可用")
    
    def get_all_stocks(self, codes: Optional[List[str]] = None, 
                       date: Optional[str] = None,
                       allow_fallback: bool = True) -> List[StockData]:
        """获取所有股票数据（自动处理降级）
        
        Args:
            codes: 股票代码列表（iFind 需要此参数）
            date: 日期，默认今天
            allow_fallback: 是否允许降级
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 先尝试主数据源
        primary = self.get_primary()
        if primary and primary.is_available():
            try:
                if primary.name == 'ifind' and codes is not None:
                    return primary.get_all_stocks(codes, date)
                else:
                    return primary.get_all_stocks(date)
            except Exception as e:
                logger.warning(f"主数据源 {primary.name} 获取全部数据失败: {e}")
        
        # 降级到备用数据源
        if allow_fallback:
            fallback = self.get_fallback()
            if fallback and fallback.is_available():
                try:
                    if fallback.name == 'ifind' and codes is not None:
                        return fallback.get_all_stocks(codes, date)
                    else:
                        return fallback.get_all_stocks(date)
                except Exception as e:
                    logger.error(f"备用数据源 {fallback.name} 获取全部数据失败: {e}")
        
        raise DataSourceUnavailable("无法获取全市场数据，所有数据源均不可用")
    
    def health_check_all(self) -> Dict[str, Dict]:
        """检查所有数据源健康状态"""
        results = {}
        for name, source in self.sources.items():
            results[name] = source.health_check()
        return results
    
    def switch_primary(self, source_name: str) -> bool:
        """切换主数据源
        
        Args:
            source_name: 数据源名称
            
        Returns:
            是否切换成功
        """
        if source_name not in self.sources:
            logger.error(f"数据源 {source_name} 未注册")
            return False
        
        source = self.sources[source_name]
        if not source.is_available():
            logger.error(f"数据源 {source_name} 不可用，无法切换")
            return False
        
        self.primary_source = source_name
        logger.info(f"主数据源已切换到: {source_name}")
        return True


class DataSourceUnavailable(Exception):
    """数据源不可用异常"""
    pass