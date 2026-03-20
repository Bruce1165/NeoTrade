#!/usr/bin/env python3
"""
Post Market Analysis Screener - 盘后深度复盘筛选器
执行内容：深度复盘分析（情绪周期、涨幅分布、成交额集中度、涨停关键词）
"""

import os
import sys
import logging
from datetime import datetime, timedelta
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

# Try to import analyzers
try:
    from sina_fetcher import SinaDataFetcher
    from emotion_analyzer import EmotionAnalyzer
    from sector_analyzer import SectorAnalyzer
    from keyword_library import KeywordLibrary
    ANALYZERS_AVAILABLE = True
except ImportError:
    ANALYZERS_AVAILABLE = False


class PostMarketScreener:
    """
    Post Market Analysis Screener - 盘后深度复盘筛选器
    
    分析内容：
    - 情绪周期分析（涨停数量、溢价率、连板数量、空间高度）
    - 涨幅分布分析
    - 成交额集中度
    - 涨停关键词分析
    
    输出：涨停及大涨股明细（涨幅>9.85%，排除ST和北交所）
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.data_dir = WORKSPACE_ROOT / 'data' / 'postmarket'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if ANALYZERS_AVAILABLE:
            self.fetcher = SinaDataFetcher()
            self.emotion_analyzer = EmotionAnalyzer(self.fetcher)
            self.sector_analyzer = SectorAnalyzer(self.fetcher)
            self.keyword_lib = KeywordLibrary()
        else:
            self.fetcher = None
            self.emotion_analyzer = None
            self.sector_analyzer = None
            self.keyword_lib = None
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('postmarket_screener')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """
        运行筛选
        
        Returns:
            list: 涨停及大涨股列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"="*60)
        self.logger.info(f"开始执行盘后深度复盘: {trade_date}")
        self.logger.info(f"="*60)
        
        try:
            # 获取涨停数据
            self.logger.info("获取涨停数据...")
            limit_df = ak.stock_zt_pool_em(date=trade_date)
            
            if limit_df.empty:
                self.logger.warning("今日无涨停股")
                return []
            
            self.logger.info(f"获取到 {len(limit_df)} 只涨停股")
            
            # 构建结果列表
            results = []
            for _, row in limit_df.iterrows():
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
            
            self.logger.info(f"="*60)
            self.logger.info(f"盘后复盘完成: 找到 {len(results)} 只涨停股")
            self.logger.info(f"="*60)
            
            return results
            
        except Exception as e:
            self.logger.error(f"盘后复盘失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise


def main():
    """主函数"""
    screener = PostMarketScreener()
    results = screener.run_screening()
    
    # 打印结果
    if results:
        print(f"\n找到 {len(results)} 只涨停股:")
        for r in results[:10]:
            print(f"  {r['code']} {r['name']}: {r['limit_days']}板, 涨幅{r['pct_change']:.2f}%")


if __name__ == '__main__':
    main()
