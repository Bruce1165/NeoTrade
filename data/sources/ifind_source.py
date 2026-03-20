#!/usr/bin/env python3
"""
iFind 实时数据源实现
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'dashboard'))

import pandas as pd
from data.sources.base import DataSource, StockData
from ifind_realtime import RealtimeFeed
from ifind_client import IfindClient

logger = logging.getLogger(__name__)


class IfindSource(DataSource):
    """iFind 实时数据源"""
    
    def __init__(self):
        self.feed = RealtimeFeed()
        self._all_codes = None
        
    @property
    def name(self) -> str:
        return "ifind"
    
    def to_ifind_code(self, code: str) -> str:
        """转换为 iFind 格式"""
        code = str(code).strip()
        return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
    
    def from_ifind_code(self, ifind_code: str) -> str:
        """从 iFind 格式转换"""
        return ifind_code.split('.')[0] if '.' in ifind_code else ifind_code
    
    def is_available(self) -> bool:
        """检查 iFind API 是否可用"""
        try:
            # 尝试获取单只股票测试
            df = self.feed.fetch(['000001.SZ'], indicators="latest")
            return not df.empty
        except Exception as e:
            logger.error(f"iFind 数据源不可用: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查 token 有效性
            import requests
            from ifind_client import IfindConfig
            
            config = IfindConfig()
            auth = IfindClient(config).auth
            token = auth.get_access_token()
            
            return {
                "status": "healthy",
                "token_valid": True,
                "source": "ifind"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_date_range(self) -> tuple:
        """iFind 只提供实时数据，返回今天"""
        today = datetime.now().strftime('%Y-%m-%d')
        return (today, today)
    
    def get_stock_data(self, code: str, date: Optional[str] = None) -> StockData:
        """获取单只股票数据"""
        ifind_code = self.to_ifind_code(code)
        
        df = self.feed.fetch(
            [ifind_code],
            indicators="open,high,low,latest,change,changeRatio,volume,amount,preClose,turnoverRatio"
        )
        
        if df.empty:
            raise ValueError(f"Stock {code} not found")
        
        row = df.iloc[0]
        return self._row_to_stock_data(row, date or datetime.now().strftime('%Y-%m-%d'))
    
    def get_all_stocks(self, codes: Optional[List[str]] = None, date: Optional[str] = None) -> List[StockData]:
        """获取所有股票数据
        
        Args:
            codes: 股票代码列表，如果为 None 则获取全市场
            date: 日期（iFind 忽略此参数，返回实时数据）
        """
        if codes is None:
            raise ValueError("iFind 需要提供股票代码列表，请从数据库获取代码列表后传入")
        
        # 分批获取（每次最多100只）
        ifind_codes = [self.to_ifind_code(c) for c in codes]
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
            except Exception as e:
                logger.error(f"获取批次失败: {e}")
                continue
        
        if not all_data:
            return []
        
        df = pd.concat(all_data, ignore_index=True)
        
        # 过滤停牌股票
        df = df[df['latest'].notna() & (pd.to_numeric(df['latest'], errors='coerce') != 0)]
        
        trade_date = date or datetime.now().strftime('%Y-%m-%d')
        return [self._row_to_stock_data(row, trade_date) for _, row in df.iterrows()]
    
    def _row_to_stock_data(self, row: pd.Series, date: str) -> StockData:
        """将 iFind 数据行转换为 StockData"""
        ifind_code = row['thscode']
        code = self.from_ifind_code(ifind_code)
        
        return StockData(
            code=code,
            name='',  # iFind 不返回名称，需要另外查询
            close=float(row.get('latest', 0)) if pd.notna(row.get('latest')) else 0.0,
            change=float(row.get('change', 0)) if pd.notna(row.get('change')) else 0.0,
            change_ratio=float(row.get('changeRatio', 0)) if pd.notna(row.get('changeRatio')) else 0.0,
            volume=float(row.get('volume', 0)) if pd.notna(row.get('volume')) else 0.0,
            amount=float(row.get('amount', 0)) if pd.notna(row.get('amount')) else 0.0,
            timestamp=datetime.strptime(date, '%Y-%m-%d'),
            source='ifind',
            open=float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
            high=float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
            low=float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
            turnover=float(row.get('turnoverRatio', 0)) if pd.notna(row.get('turnoverRatio')) else None,
            preclose=float(row.get('preClose', 0)) if pd.notna(row.get('preClose')) else None
        )