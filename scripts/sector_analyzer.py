#!/usr/bin/env python3
"""
板块分析器 - Neo量化研究体系 (AKShare版本)
分析板块阵列、领涨板块、板块拥挤度
"""

import os
import sys

# 必须在导入akshare之前清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')
from sina_fetcher import SinaDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SectorAnalyzer:
    """板块分析器"""
    
    def __init__(self, fetcher: Optional[SinaDataFetcher] = None):
        """初始化"""
        if fetcher is None:
            fetcher = SinaDataFetcher()
        self.fetcher = fetcher
    
    def analyze_top_sectors(self, trade_date: Optional[str] = None, top_n: int = 5) -> pd.DataFrame:
        """
        分析领涨板块（基于涨幅前400个股的行业分布）
        
        AKShare 方案：
        1. 获取当日全部A股行情
        2. 按涨幅排序取前400
        3. 尝试匹配行业信息（AKShare的行业数据有限）
        
        Args:
            trade_date: 交易日期
            top_n: 返回前N个板块
            
        Returns:
            板块统计 DataFrame
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"分析 {trade_date} 领涨板块...")
        
        # 获取当日行情
        daily_df = self.fetcher.get_daily_data(trade_date)
        if daily_df.empty:
            return pd.DataFrame()
        
        # 筛选涨幅前400
        top400 = daily_df.nlargest(400, 'pct_chg')
        
        # AKShare 的行业信息有限，我们使用概念板块来近似
        # 简化处理：直接统计涨幅分布
        sector_stats = pd.DataFrame({
            '排名区间': ['1-50', '51-100', '101-200', '201-300', '301-400'],
            '平均涨幅': [
                top400.iloc[0:50]['pct_chg'].mean(),
                top400.iloc[50:100]['pct_chg'].mean(),
                top400.iloc[100:200]['pct_chg'].mean(),
                top400.iloc[200:300]['pct_chg'].mean(),
                top400.iloc[300:400]['pct_chg'].mean(),
            ],
            '涨停数': [
                (top400.iloc[0:50]['pct_chg'] >= 9.9).sum(),
                (top400.iloc[50:100]['pct_chg'] >= 9.9).sum(),
                (top400.iloc[100:200]['pct_chg'] >= 9.9).sum(),
                (top400.iloc[200:300]['pct_chg'] >= 9.9).sum(),
                (top400.iloc[300:400]['pct_chg'] >= 9.9).sum(),
            ]
        })
        
        return sector_stats
    
    def analyze_sector_performance(self, sector_names: List[str], 
                                   trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        分析指定板块的表现
        
        Args:
            sector_names: 板块名称列表（如['半导体', '人工智能', '新能源']）
            trade_date: 交易日期
            
        Returns:
            板块表现 DataFrame
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"分析板块表现: {sector_names}")
        
        results = []
        all_spot = self.fetcher.get_daily_data(trade_date)
        
        for sector_name in sector_names:
            try:
                # 获取板块成分股
                sector_stocks = self.fetcher.get_sector_stocks(sector_name)
                if sector_stocks.empty:
                    continue
                
                # 获取板块内股票行情
                sector_codes = sector_stocks['代码'].tolist() if '代码' in sector_stocks.columns else []
                sector_spot = all_spot[all_spot['ts_code'].isin(sector_codes)]
                
                if sector_spot.empty:
                    continue
                
                # 统计板块表现
                results.append({
                    '板块名称': sector_name,
                    '成分股数': len(sector_codes),
                    '上涨家数': (sector_spot['pct_chg'] > 0).sum(),
                    '下跌家数': (sector_spot['pct_chg'] < 0).sum(),
                    '涨停家数': (sector_spot['pct_chg'] >= 9.9).sum(),
                    '平均涨幅': sector_spot['pct_chg'].mean(),
                    '最大涨幅': sector_spot['pct_chg'].max(),
                    '成交额(亿)': sector_spot['amount'].sum() / 100000000,
                })
                
            except Exception as e:
                logger.warning(f"分析板块 {sector_name} 失败: {e}")
                continue
        
        if not results:
            return pd.DataFrame()
        
        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values('平均涨幅', ascending=False)
        
        return result_df
    
    def analyze_volume_surge(self, trade_date: Optional[str] = None, top_n: int = 150) -> pd.DataFrame:
        """
        分析放量个股（基于当日行情）
        
        AKShare 限制：无法直接获取多日历史数据对比
        替代方案：使用当日量比指标（volume_ratio）
        
        Args:
            trade_date: 交易日期
            top_n: 成交额前N个股
            
        Returns:
            放量个股 DataFrame
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"分析 {trade_date} 放量个股...")
        
        # 获取当日行情
        daily_df = self.fetcher.get_daily_data(trade_date)
        if daily_df.empty:
            return pd.DataFrame()
        
        # 筛选成交额前150且上涨
        daily_df = daily_df[daily_df['pct_chg'] > 0]
        top150 = daily_df.nlargest(top_n, 'amount')
        
        # 使用量比作为放量指标（量比>3视为放量）
        volume_surge = top150[top150['volume_ratio'] >= 3].copy()
        
        if volume_surge.empty:
            return pd.DataFrame()
        
        # 添加放量类型标记
        volume_surge['放量类型'] = volume_surge['volume_ratio'].apply(
            lambda x: '巨量' if x >= 5 else '明显放量' if x >= 3 else '温和放量'
        )
        
        # 选择输出列
        result = volume_surge[['ts_code', 'name', 'close', 'pct_chg', 'amount', 
                               'volume_ratio', '放量类型', 'turnover']].copy()
        
        result = result.rename(columns={
            'volume_ratio': '量比',
            'turnover': '换手率',
        })
        
        return result
    
    def analyze_sector_concentration(self, trade_date: Optional[str] = None, top_n: int = 100) -> pd.DataFrame:
        """
        分析板块拥挤度（基于成交额前100个股）
        
        AKShare 限制：行业信息有限
        替代方案：按市值区间分析
        
        Args:
            trade_date: 交易日期
            top_n: 成交额前N
            
        Returns:
            拥挤度分析 DataFrame
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"分析 {trade_date} 成交额集中度...")
        
        # 获取当日行情
        daily_df = self.fetcher.get_daily_data(trade_date)
        if daily_df.empty:
            return pd.DataFrame()
        
        # 筛选成交额前100
        top100 = daily_df.nlargest(top_n, 'amount')
        
        # 按市值区间分组（替代行业）
        def categorize_mv(mv):
            if mv >= 1000:  # 1000亿以上
                return '超大盘(>1000亿)'
            elif mv >= 500:
                return '大盘(500-1000亿)'
            elif mv >= 100:
                return '中盘(100-500亿)'
            elif mv >= 50:
                return '小盘(50-100亿)'
            else:
                return '微盘(<50亿)'
        
        top100['市值区间'] = top100['total_mv'].apply(categorize_mv)
        
        # 计算总成交额
        total_amount = top100['amount'].sum()
        
        # 按市值区间统计
        concentration = top100.groupby('市值区间').agg({
            'ts_code': 'count',
            'amount': 'sum',
        }).reset_index()
        
        concentration.columns = ['市值区间', '个股数', '成交额']
        concentration['占比(%)'] = (concentration['成交额'] / total_amount * 100).round(2)
        concentration = concentration.sort_values('占比(%)', ascending=False)
        
        return concentration


def main():
    """测试板块分析"""
    try:
        analyzer = SectorAnalyzer()
        
        # 分析涨幅分布
        print("\n" + "="*60)
        print("涨幅前400分布")
        print("="*60)
        top_sectors = analyzer.analyze_top_sectors()
        print(top_sectors.to_string(index=False))
        
        # 分析放量个股
        print("\n" + "="*60)
        print("放量个股 TOP10")
        print("="*60)
        volume_surge = analyzer.analyze_volume_surge()
        if not volume_surge.empty:
            print(volume_surge.head(10).to_string(index=False))
        else:
            print("今日无放量个股")
        
        # 分析成交额集中度
        print("\n" + "="*60)
        print("成交额集中度（按市值区间）")
        print("="*60)
        concentration = analyzer.analyze_sector_concentration()
        print(concentration.to_string(index=False))
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
