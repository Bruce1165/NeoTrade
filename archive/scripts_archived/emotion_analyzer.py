#!/usr/bin/env python3
"""
情绪周期分析器 - Neo量化研究体系 (AKShare版本)
基于 AKShare 数据计算情绪四要素，判定情绪周期阶段
"""

import os
import sys

# 必须在导入akshare之前清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# 添加脚本路径
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')
from sina_fetcher import SinaDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmotionAnalyzer:
    """情绪周期分析器"""
    
    def __init__(self, fetcher: Optional[SinaDataFetcher] = None):
        """
        初始化分析器
        
        Args:
            fetcher: SinaDataFetcher 实例
        """
        if fetcher is None:
            fetcher = SinaDataFetcher()
        self.fetcher = fetcher
        
        # 情绪四要素阈值定义
        self.thresholds = {
            'limit_up_count': {'high': 70, 'mid': 40, 'low': 20},
            'premium_rate': {'high': 4.0, 'mid': 3.0, 'low': -3.0},
            'consecutive_limit': {'high': 20, 'mid': 10, 'low': 0},
        }
    
    def calculate_four_elements(self, trade_date: Optional[str] = None) -> Dict:
        """
        计算情绪周期四要素
        
        Args:
            trade_date: 交易日期 (YYYYMMDD)
            
        Returns:
            包含四要素的字典
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"计算 {trade_date} 情绪四要素...")
        
        # 1. 涨停数量
        limit_df = self.fetcher.get_limit_up_data(trade_date)
        limit_up_count = len(limit_df) if not limit_df.empty else 0
        
        # 2. 溢价率（昨日涨停股今日表现）
        premium_rate = self._calculate_premium_rate(trade_date)
        
        # 3. 连板数（2板及以上）
        consecutive_limit = self._calculate_consecutive_limit(limit_df)
        
        # 4. 空间高度（最高连板数）
        space_height = self._calculate_space_height(limit_df)
        
        result = {
            'trade_date': trade_date,
            'limit_up_count': limit_up_count,
            'premium_rate': premium_rate,
            'consecutive_limit': consecutive_limit,
            'space_height': space_height,
        }
        
        logger.info(f"情绪四要素: 涨停={limit_up_count}, 溢价={premium_rate:.2f}%, 连板={consecutive_limit}, 高度={space_height}")
        
        return result
    
    def _calculate_premium_rate(self, trade_date: str) -> float:
        """
        计算溢价率（昨日涨停股今日平均收益）
        
        AKShare 限制：无法直接获取昨日涨停数据
        替代方案：使用今日行情中的昨日涨停股（如果有标识）或简化处理
        
        Args:
            trade_date: 今日日期
            
        Returns:
            溢价率 (%)
        """
        try:
            # 获取今日全部行情
            today_df = self.fetcher.get_daily_data(trade_date)
            if today_df.empty:
                return 0.0
            
            # AKShare 的 spot 数据不包含昨日涨停标识
            # 简化处理：使用今日高开且涨幅较高的股票估算
            # 实际应用中可能需要保存历史涨停数据
            
            # 替代方案：计算今日涨停股的平均涨幅（作为市场情绪参考）
            limit_up_today = today_df[today_df['pct_chg'] >= 9.9]
            if len(limit_up_today) == 0:
                return 0.0
            
            # 返回今日涨停股的平均涨幅作为参考
            avg_chg = limit_up_today['pct_chg'].mean()
            return avg_chg
            
        except Exception as e:
            logger.error(f"计算溢价率失败: {e}")
            return 0.0
    
    def _calculate_consecutive_limit(self, limit_df: pd.DataFrame) -> int:
        """
        计算连板数（2板及以上股票数量）
        
        Args:
            limit_df: 涨停数据
            
        Returns:
            连板股票数量
        """
        if limit_df.empty or 'limit_days' not in limit_df.columns:
            return 0
        
        # 筛选连板股（limit_days >= 2）
        consecutive = limit_df[limit_df['limit_days'] >= 2]
        return len(consecutive)
    
    def _calculate_space_height(self, limit_df: pd.DataFrame) -> int:
        """
        计算空间高度（最高连板数）
        
        Args:
            limit_df: 涨停数据
            
        Returns:
            最高连板数
        """
        if limit_df.empty or 'limit_days' not in limit_df.columns:
            return 0
        
        max_height = limit_df['limit_days'].max()
        return int(max_height) if not pd.isna(max_height) else 0
    
    def determine_emotion_stage(self, elements: Dict, history: Optional[List[Dict]] = None) -> str:
        """
        判定情绪周期阶段
        
        Args:
            elements: 当前四要素
            history: 历史四要素列表（用于趋势判断）
            
        Returns:
            情绪阶段: '退潮期'/'冰点期'/'混沌期'/'回暖期'/'主升期'/'高潮期'
        """
        limit_up = elements['limit_up_count']
        premium = elements['premium_rate']
        consecutive = elements['consecutive_limit']
        
        # 基于阈值判断
        # 涨停数量判断
        if limit_up >= self.thresholds['limit_up_count']['high']:
            limit_level = 'high'
        elif limit_up >= self.thresholds['limit_up_count']['mid']:
            limit_level = 'mid'
        else:
            limit_level = 'low'
        
        # 溢价率判断（简化版）
        if premium >= 9.5:  # 涨停股平均涨幅接近涨停
            premium_level = 'high'
        elif premium >= 5.0:
            premium_level = 'mid'
        else:
            premium_level = 'low'
        
        # 连板数判断
        if consecutive >= self.thresholds['consecutive_limit']['high']:
            consecutive_level = 'high'
        elif consecutive >= self.thresholds['consecutive_limit']['mid']:
            consecutive_level = 'mid'
        else:
            consecutive_level = 'low'
        
        # 综合判定（简化版）
        levels = [limit_level, premium_level, consecutive_level]
        high_count = levels.count('high')
        low_count = levels.count('low')
        
        if high_count >= 2:
            return '高潮期'
        elif low_count >= 2:
            return '冰点期'
        elif limit_level == 'mid' and premium_level == 'mid':
            return '混沌期'
        elif limit_level == 'high' or premium_level == 'high':
            return '主升期'
        elif limit_level == 'low' and premium_level == 'mid':
            return '退潮期'
        else:
            return '回暖期'
    
    def generate_daily_report(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        生成每日情绪分析报告
        
        Args:
            trade_date: 交易日期
            
        Returns:
            报告 DataFrame
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        # 计算四要素
        elements = self.calculate_four_elements(trade_date)
        
        # 判定阶段
        stage = self.determine_emotion_stage(elements)
        
        # 生成报告
        report = pd.DataFrame([{
            '日期': trade_date,
            '涨停数量': elements['limit_up_count'],
            '溢价率(%)': round(elements['premium_rate'], 2),
            '连板数量': elements['consecutive_limit'],
            '空间高度': elements['space_height'],
            '情绪阶段': stage,
        }])
        
        return report


def main():
    """主函数 - 测试情绪分析"""
    try:
        analyzer = EmotionAnalyzer()
        
        # 生成今日报告
        report = analyzer.generate_daily_report()
        
        print("\n" + "="*60)
        print("每日情绪分析报告")
        print("="*60)
        print(report.to_string(index=False))
        print("="*60)
        
        # 保存报告
        today = datetime.now().strftime('%Y%m%d')
        report_file = f'emotion_report_{today}.csv'
        analyzer.fetcher.save_data(report, report_file, 'emotion')
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
