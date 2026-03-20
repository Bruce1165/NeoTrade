#!/usr/bin/env python3
"""
iFinD 历史数据接口
支持获取股票历史日线数据
"""

import pandas as pd
from typing import List, Optional
from datetime import datetime, timedelta
from ifind_client import IfindClient
import logging

logger = logging.getLogger(__name__)


class IfindHistory:
    """iFinD 历史数据接口"""
    
    ENDPOINT = "cmd_history_quotation"  # 正确的端点
    
    # 字段映射：iFinD返回的字段 -> 标准字段名
    FIELD_MAP = {
        'thscode': 'code',
        'close': 'close',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'volume': 'volume',
        'amount': 'amount',
        'turnover': 'turnover',
        'change': 'change',
        'changeRatio': 'pct_change',
        'preClose': 'pre_close',
    }
    
    def __init__(self, client: IfindClient = None):
        self.client = client or IfindClient()
    
    def to_ifind_code(self, code: str) -> str:
        """转换为 iFinD 格式"""
        code = str(code).strip()
        return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
    
    def from_ifind_code(self, ifind_code: str) -> str:
        """从 iFinD 格式转换"""
        return ifind_code.split('.')[0] if '.' in ifind_code else ifind_code
    
    def fetch_history(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        indicators: str = None
    ) -> pd.DataFrame:
        """
        获取历史日线数据
        
        Args:
            codes: 股票代码列表（如 ['600000', '000001']）
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            indicators: 指标字符串，默认全部
            
        Returns:
            DataFrame 包含历史数据
        """
        if indicators is None:
            indicators = "open,high,low,close,volume,amount,turnover,change,changeRatio,preClose"
        
        # 转换为 iFinD 格式
        ifind_codes = [self.to_ifind_code(c) for c in codes]
        codes_str = ",".join(ifind_codes)
        
        params = {
            "codes": codes_str,
            "indicators": indicators,
            "startdate": start_date.replace('-', ''),
            "enddate": end_date.replace('-', '')
        }
        
        try:
            logger.info(f"📊 获取 {len(codes)} 只股票历史数据 ({start_date} ~ {end_date})")
            data = self.client.post(self.ENDPOINT, params)
            df = self._parse_response(data)
            logger.info(f"✅ 获取历史数据成功: {len(df)} 条记录")
            return df
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败: {e}")
            raise
    
    def _parse_response(self, data: dict) -> pd.DataFrame:
        """解析 API 响应"""
        if not data or 'data' not in data:
            return pd.DataFrame()
        
        records = []
        for item in data['data']:
            record = {}
            for ifind_field, standard_field in self.FIELD_MAP.items():
                if ifind_field in item:
                    record[standard_field] = item[ifind_field]
            
            # 添加日期
            if 'date' in item:
                record['trade_date'] = item['date']
            elif 'time' in item:
                record['trade_date'] = item['time']
            
            records.append(record)
        
        df = pd.DataFrame(records)
        
        # 转换数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 
                       'turnover', 'change', 'pct_change', 'pre_close']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def fetch_for_screener(
        self,
        codes: List[str],
        days: int = 250
    ) -> pd.DataFrame:
        """
        为筛选器获取历史数据（自动计算日期范围）
        
        Args:
            codes: 股票代码列表
            days: 需要的天数（默认250天，适合杯柄形态）
            
        Returns:
            DataFrame 包含所需历史数据
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
        
        return self.fetch_history(codes, start_date, end_date)
