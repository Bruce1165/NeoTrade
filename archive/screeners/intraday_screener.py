#!/usr/bin/env python3
"""
Intraday Analysis Screener - 盘中分析筛选器
执行内容：涨停股分析、弱势股分析
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Clear proxy env vars
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import akshare as ak
import pandas as pd

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

# Try to import keyword library
try:
    from keyword_library import KeywordLibrary
    KEYWORD_LIB_AVAILABLE = True
except ImportError:
    KEYWORD_LIB_AVAILABLE = False


class IntradayScreener:
    """
    Intraday Analysis Screener - 盘中分析筛选器
    
    分析内容：
    - 涨停股分析（涨停时间、连板数、所属行业）
    - 弱势股分析（跌幅大+成交额大）
    
    默认输出涨停股列表
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.data_dir = WORKSPACE_ROOT / 'data' / 'intraday'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if KEYWORD_LIB_AVAILABLE:
            self.keyword_lib = KeywordLibrary()
        else:
            self.keyword_lib = None
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('intraday_screener')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None, analysis_type: str = 'limit_up'):
        """
        运行筛选
        
        Args:
            trade_date: 交易日期，默认今天
            analysis_type: 分析类型 ('limit_up' 涨停股, 'weak' 弱势股)
        
        Returns:
            list: 筛选结果列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"="*60)
        self.logger.info(f"开始执行盘中分析: {trade_date}, 类型: {analysis_type}")
        self.logger.info(f"="*60)
        
        try:
            if analysis_type == 'limit_up':
                return self._analyze_limit_up(trade_date)
            elif analysis_type == 'weak':
                return self._analyze_weak(trade_date)
            else:
                raise ValueError(f"未知的分析类型: {analysis_type}")
                
        except Exception as e:
            self.logger.error(f"盘中分析失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _analyze_limit_up(self, trade_date: str):
        """分析涨停股"""
        self.logger.info("获取涨停数据...")
        df = ak.stock_zt_pool_em(date=trade_date)
        
        if df.empty:
            self.logger.warning("今日无涨停股")
            return []
        
        self.logger.info(f"获取到 {len(df)} 只涨停股")
        
        # 构建结果列表
        results = []
        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            
            # 排除ST股和北交所
            if 'ST' in name:
                continue
            if code.startswith(('8', '9', '4')):
                continue
            
            results.append({
                'code': code,
                'name': name,
                'close': round(pd.to_numeric(row.get('最新价', 0), errors='coerce') or 0, 2),
                'pct_change': round(pd.to_numeric(row.get('涨跌幅', 0), errors='coerce') or 0, 2),
                'limit_days': int(row.get('连板数', 0)),
                'turnover': round(pd.to_numeric(row.get('换手率', 0), errors='coerce') or 0, 2),
                'industry': row.get('所属行业', ''),
                'limit_time': row.get('首次封板时间', '') if not pd.isna(row.get('首次封板时间', '')) else ''
            })
        
        # 按连板数降序，然后按涨幅降序
        results = sorted(results, key=lambda x: (x['limit_days'], x['pct_change']), reverse=True)
        
        self.logger.info(f"涨停股分析完成: {len(results)} 只")
        return results
    
    def _analyze_weak(self, trade_date: str, min_drop: float = -5.0, min_amount: float = 5.0):
        """分析弱势股（跌幅大+成交额大）"""
        self.logger.info(f"分析弱势股: 跌幅<{min_drop}%, 成交额>{min_amount}亿...")
        
        # 获取全市场数据
        df = ak.stock_zh_a_spot_em()
        
        # 数据清洗
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
        df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
        df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')
        
        # 筛选跌幅>5%且成交额>5亿
        weak_df = df[
            (df['涨跌幅'] <= min_drop) & 
            (df['成交额'] >= min_amount * 1e8)
        ].copy()
        
        if weak_df.empty:
            self.logger.warning("无符合条件的弱势股")
            return []
        
        self.logger.info(f"找到 {len(weak_df)} 只弱势股")
        
        # 构建结果列表
        results = []
        for _, row in weak_df.iterrows():
            code = row['代码']
            name = row['名称']
            
            # 排除ST股
            if 'ST' in name:
                continue
            
            results.append({
                'code': code,
                'name': name,
                'close': round(row['最新价'], 2) if pd.notna(row['最新价']) else 0,
                'pct_change': round(row['涨跌幅'], 2),
                'turnover': round(row['换手率'], 2) if pd.notna(row['换手率']) else 0,
                'amount': round(row['成交额'] / 1e8, 2),  # 成交额(亿)
                'industry': row.get('所属行业', '')
            })
        
        # 按跌幅升序（跌幅最大的在前）
        results = sorted(results, key=lambda x: x['pct_change'])
        
        self.logger.info(f"弱势股分析完成: {len(results)} 只")
        return results


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['limit_up', 'weak'], default='limit_up',
                       help='分析类型: limit_up-涨停股, weak-弱势股')
    args = parser.parse_args()
    
    screener = IntradayScreener()
    results = screener.run_screening(analysis_type=args.type)
    
    # 打印结果
    if results:
        print(f"\n找到 {len(results)} 只股票:")
        for r in results[:10]:
            print(f"  {r['code']} {r['name']}: 涨幅{r['pct_change']:.2f}%")


if __name__ == '__main__':
    main()
