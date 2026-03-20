#!/usr/bin/env python3
"""
基础筛选器类 - Base Screener

所有股票筛选器的基类，提供通用功能：
- 交易日历集成
- 新闻抓取
- LLM分析
- 进度跟踪
- 输出管理
"""

# 清除代理环境变量，避免网络请求失败
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import logging
import argparse

from database import init_db, get_session, Stock, DailyPrice
from trading_calendar import TradingCalendar, get_recent_trading_day
from news_fetcher import NewsFetcher
from llm_analyzer import LLMAnalyzer
from progress_tracker import ProgressTracker
from output_manager import OutputManager

logger = logging.getLogger(__name__)

DB_PATH = "data/stock_data.db"


class BaseScreener:
    """基础筛选器类"""
    
    def __init__(self, 
                 screener_name: str,
                 db_path: str = DB_PATH,
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        """
        初始化基础筛选器
        
        Args:
            screener_name: 筛选器名称
            db_path: 数据库路径
            enable_news: 是否启用新闻抓取
            enable_llm: 是否启用LLM分析
            enable_progress: 是否启用进度跟踪
        """
        self.screener_name = screener_name
        self.db_path = db_path
        
        # 内存数据源（用于 realtime run）
        self.data_df = None
        
        # 初始化数据库
        self.engine = init_db()
        self.session = get_session(self.engine)
        
        # 初始化交易日历
        self.calendar = TradingCalendar(db_path)
        
        # 初始化新闻抓取器
        self.news_fetcher = NewsFetcher() if enable_news else None
        
        # 初始化LLM分析器
        self.llm_analyzer = LLMAnalyzer() if enable_llm else None
        
        # 初始化进度跟踪器
        self.progress_tracker = ProgressTracker(screener_name) if enable_progress else None
        
        # 初始化输出管理器
        self.output_manager = OutputManager(screener_name)
        
        # 当前日期
        self.current_date = get_recent_trading_day(db_path=db_path)
        
        logger.info(f"Initialized {screener_name} screener")
    
    def get_stock_data(self, code: str, days: int = 100) -> Optional[pd.DataFrame]:
        """
        获取股票最近N天的数据
        
        Args:
            code: 股票代码
            days: 天数
        
        Returns:
            DataFrame或None
        """
        # 如果设置了内存数据源，优先使用
        if self.data_df is not None:
            df = self.data_df[self.data_df['code'] == code].copy()
            if df.empty:
                return None
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').tail(days).reset_index(drop=True)
            df['code'] = code
            return df
        
        query = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(query, conn, params=(code, days))
            conn.close()
            
            if df.empty:
                return None
            
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"Error getting stock data for {code}: {e}")
            return None
    
    def is_limit_up(self, row: pd.Series, prev_close: float) -> bool:
        """
        判断是否为涨停板
        
        Args:
            row: 数据行
            prev_close: 前收盘价
        
        Returns:
            是否涨停
        """
        if prev_close <= 0:
            return False
        
        code = str(row.get('code', ''))
        pct_change = row.get('pct_change', 0) or 0
        
        # 创业板/科创板 20%
        if code.startswith(('300', '301', '688', '689')):
            return pct_change >= 19.5
        
        # 北交所 30%
        if code.startswith('8'):
            return pct_change >= 29.5
        
        # 主板/ST 10%
        name = str(row.get('name', ''))
        if 'ST' in name:
            return pct_change >= 4.5
        
        return pct_change >= 9.5
    
    def get_all_stocks(self, exclude_indices: bool = True, 
                       exclude_st: bool = True) -> List[Stock]:
        """
        获取所有股票
        
        Args:
            exclude_indices: 是否排除指数
            exclude_st: 是否排除ST股
        
        Returns:
            股票列表
        """
        stocks = self.session.query(Stock).all()
        
        filtered = []
        for stock in stocks:
            # 排除指数
            if exclude_indices and stock.code.startswith(('399', '000', '899')):
                continue
            
            # 排除ST股
            if exclude_st and stock.name and ('ST' in stock.name or '退' in stock.name):
                continue
            
            filtered.append(stock)
        
        return filtered
    
    def fetch_news(self, stock_code: str, max_news: int = 5) -> str:
        """
        获取股票新闻摘要
        
        Args:
            stock_code: 股票代码
            max_news: 最大新闻数量
        
        Returns:
            新闻摘要
        """
        if self.news_fetcher is None:
            return ""
        
        try:
            return self.news_fetcher.get_news_summary(stock_code, max_news)
        except Exception as e:
            logger.warning(f"Error fetching news for {stock_code}: {e}")
            return ""
    
    def analyze_stock(self, stock_code: str, stock_name: str, 
                      news_summary: str, price_data: Optional[Dict] = None) -> Dict:
        """
        分析股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            news_summary: 新闻摘要
            price_data: 价格数据
        
        Returns:
            分析结果
        """
        if self.llm_analyzer is None:
            return {
                '上涨原因': '',
                '行业分类': '',
                '相关概念': '',
                '新闻摘要': news_summary[:50] if news_summary else '',
                '分析置信度': ''
            }
        
        try:
            return self.llm_analyzer.analyze_stock(
                stock_code, stock_name, news_summary, price_data, 
                date_str=self.current_date
            )
        except Exception as e:
            logger.warning(f"Error analyzing stock {stock_code}: {e}")
            return {
                '上涨原因': '',
                '行业分类': '',
                '相关概念': '',
                '新闻摘要': news_summary[:50] if news_summary else '',
                '分析置信度': ''
            }
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """
        筛选单只股票（子类必须实现）
        
        Args:
            code: 股票代码
            name: 股票名称
        
        Returns:
            筛选结果或None
        """
        raise NotImplementedError("Subclasses must implement screen_stock()")
    
    def check_data_availability(self, trade_date: str) -> bool:
        """检查指定日期的数据是否存在于数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM daily_prices WHERE trade_date = ? LIMIT 1",
            (trade_date,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """
        运行筛选

        Args:
            date_str: 日期字符串
            force_restart: 是否强制重新开始
            enable_analysis: 是否启用LLM分析

        Returns:
            (结果列表, 分析数据字典)
        """
        if date_str:
            self.current_date = date_str

        # 检查数据是否可用（而非简单地检查是否是今天）
        if not self.check_data_availability(self.current_date):
            logger.warning(f"⚠️  无可用数据 ({self.current_date}) - 市场尚未收盘或数据未下载")
            return [{
                'code': 'STATUS',
                'name': 'No Data',
                'message': f'无可用数据 ({self.current_date})，市场尚未收盘或数据未下载',
                'error': 'no_data'
            }]

        logger.info("="*60)
        logger.info(f"{self.screener_name} - 开始筛选")
        logger.info(f"日期: {self.current_date}")
        logger.info("="*60)
        
        # 获取所有股票
        stocks = self.get_all_stocks()
        total_stocks = len(stocks)
        logger.info(f"Total stocks: {total_stocks}")
        
        # 检查进度跟踪
        start_idx = 0
        if self.progress_tracker and not force_restart:
            if self.progress_tracker.is_resumable():
                processed_codes = self.progress_tracker.get_processed_codes()
                start_idx = len(processed_codes)
                logger.info(f"Resuming from stock {start_idx}")
            else:
                self.progress_tracker.reset()
        
        # 开始进度跟踪
        if self.progress_tracker:
            self.progress_tracker.start(
                total_stocks=total_stocks,
                metadata={'date': self.current_date, 'screener': self.screener_name}
            )
        
        results = []
        analysis_data = {}
        
        for i, stock in enumerate(stocks[start_idx:], start=start_idx):
            try:
                # 更新进度
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(
                        processed=i+1,
                        matched=len(results),
                        current_code=stock.code
                    )
                
                # 筛选股票
                result = self.screen_stock(stock.code, stock.name)
                
                if result:
                    results.append(result)
                    
                    # 获取新闻和分析
                    if enable_analysis and self.news_fetcher:
                        news = self.fetch_news(stock.code)
                        price_data = {
                            'close': result.get('close', result.get('current_price', 0)),
                            'pct_change': result.get('pct_change', result.get('current_change', 0)),
                            'turnover': result.get('turnover', 0)
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"行业:{analysis.get('行业分类', 'N/A')}")
                    else:
                        logger.info(f"✓ Found: {stock.code} {stock.name}")
                
                # 每500只股票打印进度
                if (i + 1) % 500 == 0:
                    logger.info(f"Progress: {i+1}/{total_stocks}, Found: {len(results)}")
                    
            except Exception as e:
                logger.error(f"Error screening {stock.code}: {e}")
                continue
        
        # 完成进度跟踪
        if self.progress_tracker:
            self.progress_tracker.complete(success=True)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"筛选完成!")
        logger.info(f"检查: {total_stocks} 只股票")
        logger.info(f"匹配: {len(results)} 只股票")
        logger.info(f"{'='*60}")
        
        return results
    
    def save_results(self, results: List[Dict], analysis_data: Optional[Dict[str, Dict]] = None,
                     suffix: str = "", column_mapping: Optional[Dict[str, str]] = None) -> str:
        """
        保存结果
        
        Args:
            results: 结果列表
            analysis_data: 分析数据
            suffix: 文件名后缀
            column_mapping: 列名映射
        
        Returns:
            保存的文件路径
        """
        if not results:
            logger.warning("No results to save")
            return ""
        
        if analysis_data:
            return self.output_manager.save_with_analysis(
                results, analysis_data, self.current_date, suffix, column_mapping
            )
        else:
            return self.output_manager.save_results(
                results, self.current_date, suffix, column_mapping
            )
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.output_manager.get_stats()
    
    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """
        检查单个股票是否符合筛选条件
        
        Args:
            code: 股票代码
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            {
                'match': True/False,
                'code': 股票代码,
                'name': 股票名称,
                'date': 日期,
                'details': 匹配时的详细信息 (可选),
                'reasons': 不匹配时的原因列表
            }
        """
        # 设置日期
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取股票名称
        try:
            session = get_session(init_db())
            stock = session.query(Stock).filter_by(code=code).first()
            name = stock.name if stock else ''
            session.close()
        except:
            name = ''
        
        # 子类需要实现具体的检查逻辑
        # 这里返回默认实现
        result = self.screen_stock(code, name)
        
        if result:
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'details': result,
                'reasons': []
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'details': None,
                'reasons': ['不符合筛选条件']
            }


if __name__ == '__main__':
    # 测试基类
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试筛选器
    class TestScreener(BaseScreener):
        def screen_stock(self, code: str, name: str) -> Optional[Dict]:
            # 简单的测试逻辑
            df = self.get_stock_data(code, days=5)
            if df is not None and len(df) >= 2:
                latest = df.iloc[-1]
                if latest.get('pct_change', 0) > 5:
                    return {
                        'code': code,
                        'name': name,
                        'close': latest['close'],
                        'pct_change': latest['pct_change']
                    }
            return None
    
    screener = TestScreener('test_screener')
    print(f"\nScreener stats: {screener.get_stats()}")
