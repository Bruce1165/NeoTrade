#!/usr/bin/env python3
"""
AKShare 数据抓取框架 - Neo量化研究体系
负责从 AKShare 获取股票数据
"""

import os
import sys

# 必须在导入akshare之前清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import akshare as ak

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/mac/.openclaw/workspace-neo/logs/akshare.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AKShareDataFetcher:
    """AKShare 数据获取器"""
    
    def __init__(self):
        """初始化 AKShare 连接"""
        self.data_dir = Path(os.getenv('DATA_DIR', '/Users/mac/.openclaw/workspace-neo/data'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 缓存股票基础信息
        self._stock_basic_cache = None
        self._cache_time = None
        
        logger.info("AKShare 数据获取器初始化完成")
    
    def get_stock_basic(self) -> pd.DataFrame:
        """
        获取股票基础信息
        
        Returns:
            DataFrame 包含股票代码、名称、行业等信息
        """
        # 缓存1小时
        if self._stock_basic_cache is not None and self._cache_time is not None:
            if (datetime.now() - self._cache_time).seconds < 3600:
                return self._stock_basic_cache
        
        try:
            # 使用新浪接口获取当日行情（包含基础信息）
            df = ak.stock_zh_a_spot()
            
            # 新浪接口列名映射
            column_mapping = {
                'symbol': 'ts_code',
                'name': 'name',
                'trade': 'close',
                'pricechange': 'change',
                'changepercent': 'pct_chg',
                'settlement': 'pre_close',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'volume': 'volume',
                'amount': 'amount',
                'per': 'pe',
                'pb': 'pb',
                'mktcap': 'total_mv',
                'nmc': 'circ_mv',
                'turnoverratio': 'turnover',
            }
            
            existing_cols = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=existing_cols)
            
            if 'ts_code' not in df.columns and 'code' in df.columns:
                df['ts_code'] = df['code']
            
            # 添加行业信息（需要另外获取）
            try:
                industry_df = self._get_industry_info()
                if industry_df is not None:
                    df = df.merge(industry_df[['ts_code', 'industry']], on='ts_code', how='left')
            except Exception as e:
                logger.warning(f"获取行业信息失败: {e}")
                df['industry'] = '未知'
            
            self._stock_basic_cache = df
            self._cache_time = datetime.now()
            
            logger.info(f"获取股票基础信息: {len(df)} 只股票")
            return df
            
        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            raise
    
    def _get_industry_info(self) -> Optional[pd.DataFrame]:
        """获取行业分类信息"""
        try:
            # 获取行业板块数据
            df = ak.stock_board_industry_name_ths()
            # 这里简化处理，实际需要遍历每个板块获取成分股
            return None
        except:
            return None
    
    def get_daily_data(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取当日全部A股行情数据
        
        Args:
            trade_date: 交易日期 (YYYYMMDD)，AKShare实时数据不支持历史日期查询
            
        Returns:
            DataFrame 包含开盘价、收盘价、涨跌幅、成交量等
        """
        try:
            # 使用新浪接口（更稳定）
            df = ak.stock_zh_a_spot()
            
            # 新浪接口列名已经是英文，需要映射
            column_mapping = {
                'symbol': 'ts_code',
                'name': 'name',
                'trade': 'close',
                'pricechange': 'change',
                'changepercent': 'pct_chg',
                'buy': 'buy',
                'sell': 'sell',
                'settlement': 'pre_close',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'volume': 'volume',
                'amount': 'amount',
                'ticktime': 'ticktime',
                'per': 'pe',
                'pb': 'pb',
                'mktcap': 'total_mv',
                'nmc': 'circ_mv',
                'turnoverratio': 'turnover',
            }
            
            # 只保留存在的列
            existing_cols = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=existing_cols)
            
            # 确保必要列存在
            if 'ts_code' not in df.columns and 'code' in df.columns:
                df['ts_code'] = df['code']
            
            # 添加交易日期
            if trade_date:
                df['trade_date'] = trade_date
            else:
                df['trade_date'] = datetime.now().strftime('%Y%m%d')
            
            logger.info(f"获取日线数据: {len(df)} 只股票")
            return df
            
        except Exception as e:
            logger.error(f"获取日线数据失败: {e}")
            raise
    
    def get_limit_up_data(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取涨停股票数据（包含连板信息）
        
        Args:
            trade_date: 交易日期 (YYYYMMDD)
            
        Returns:
            DataFrame 包含涨停股票及连板天数
        """
        try:
            # AKShare 的涨停池接口
            df = ak.stock_zt_pool_em(date=trade_date)
            
            # 重命名列
            df = df.rename(columns={
                '代码': 'ts_code',
                '名称': 'name',
                '涨跌幅': 'pct_chg',
                '最新价': 'close',
                '成交额': 'amount',
                '流通市值': 'circ_mv',
                '总市值': 'total_mv',
                '换手率': 'turnover',
                '封板资金': 'seal_amount',
                '首次封板时间': 'first_seal_time',
                '最后封板时间': 'last_seal_time',
                '炸板次数': 'open_count',
                '涨停统计': 'limit_stats',
                '连板数': 'limit_days',
            })
            
            # 添加交易日期
            df['trade_date'] = trade_date if trade_date else datetime.now().strftime('%Y%m%d')
            
            logger.info(f"获取涨停数据: {len(df)} 只涨停股")
            return df
            
        except Exception as e:
            logger.error(f"获取涨停数据失败: {e}")
            # 如果接口失败，返回空DataFrame
            return pd.DataFrame()
    
    def get_sector_stocks(self, sector_name: str, sector_type: str = 'industry') -> pd.DataFrame:
        """
        获取板块成分股
        
        Args:
            sector_name: 板块名称（如'半导体'、'人工智能'）
            sector_type: 板块类型（'industry'行业/'concept'概念）
            
        Returns:
            DataFrame 板块成分股列表
        """
        try:
            if sector_type == 'industry':
                # 行业板块
                df = ak.stock_board_industry_cons_em(symbol=sector_name)
            else:
                # 概念板块
                df = ak.stock_board_concept_cons_em(symbol=sector_name)
            
            logger.info(f"获取板块 {sector_name} 成分股: {len(df)} 只")
            return df
            
        except Exception as e:
            logger.error(f"获取板块 {sector_name} 成分股失败: {e}")
            return pd.DataFrame()
    
    def get_sector_list(self, sector_type: str = 'industry') -> pd.DataFrame:
        """
        获取板块列表
        
        Args:
            sector_type: 'industry'行业/'concept'概念
            
        Returns:
            DataFrame 板块列表
        """
        try:
            if sector_type == 'industry':
                df = ak.stock_board_industry_name_ths()
            else:
                df = ak.stock_board_concept_name_ths()
            
            logger.info(f"获取板块列表: {len(df)} 个板块")
            return df
            
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")
            return pd.DataFrame()
    
    def get_stock_hist(self, symbol: str, period: str = "daily", 
                       start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取个股历史行情
        
        Args:
            symbol: 股票代码（如'000001'）
            period: 周期（daily/weekly/monthly）
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            DataFrame 历史行情数据
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'trade_date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_chg',
                '涨跌额': 'change',
                '换手率': 'turnover',
            })
            
            logger.info(f"获取 {symbol} 历史数据: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()
    
    def get_latest_trade_date(self) -> str:
        """
        获取最新交易日
        
        Returns:
            最新交易日 (YYYYMMDD)
        """
        # AKShare 返回的是实时数据，用当前日期
        # 如果是周末，返回最近一个交易日需要额外处理
        today = datetime.now()
        
        # 简单处理：如果是周末，返回周五
        if today.weekday() == 5:  # 周六
            latest = today - timedelta(days=1)
        elif today.weekday() == 6:  # 周日
            latest = today - timedelta(days=2)
        else:
            latest = today
        
        return latest.strftime('%Y%m%d')
    
    def save_data(self, df: pd.DataFrame, filename: str, subdir: str = ""):
        """
        保存数据到本地
        
        Args:
            df: DataFrame 数据
            filename: 文件名
            subdir: 子目录
        """
        save_dir = self.data_dir / subdir
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / filename
        
        # 根据文件扩展名选择保存格式
        if filepath.suffix == '.csv':
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
        elif filepath.suffix == '.parquet':
            df.to_parquet(filepath, index=False)
        elif filepath.suffix == '.json':
            df.to_json(filepath, orient='records', force_ascii=False)
        else:
            # 默认 CSV
            filepath = filepath.with_suffix('.csv')
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        logger.info(f"数据已保存: {filepath}")
    
    def load_data(self, filename: str, subdir: str = "") -> Optional[pd.DataFrame]:
        """
        从本地加载数据
        
        Args:
            filename: 文件名
            subdir: 子目录
            
        Returns:
            DataFrame 或 None
        """
        filepath = self.data_dir / subdir / filename
        
        if not filepath.exists():
            logger.warning(f"文件不存在: {filepath}")
            return None
        
        try:
            if filepath.suffix == '.csv':
                return pd.read_csv(filepath)
            elif filepath.suffix == '.parquet':
                return pd.read_parquet(filepath)
            elif filepath.suffix == '.json':
                return pd.read_json(filepath)
            else:
                return pd.read_csv(filepath)
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return None


def test_connection():
    """测试 AKShare 连接"""
    try:
        fetcher = AKShareDataFetcher()
        
        # 测试获取当日行情
        df = fetcher.get_daily_data()
        print(f"\n✅ 连接成功！")
        print(f"获取到 {len(df)} 只股票的当日行情")
        print(f"\n前5只股票:")
        print(df[['ts_code', 'name', 'close', 'pct_chg']].head())
        
        # 测试获取涨停数据
        print(f"\n测试获取涨停数据...")
        limit_df = fetcher.get_limit_up_data()
        if not limit_df.empty:
            print(f"获取到 {len(limit_df)} 只涨停股")
            print(f"\n涨停股示例:")
            print(limit_df[['ts_code', 'name', 'limit_days']].head())
        
        return True
        
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # 测试连接
    test_connection()
