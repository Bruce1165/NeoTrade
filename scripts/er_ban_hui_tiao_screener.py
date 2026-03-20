#!/usr/bin/env python3
"""
二板回调筛选器 - Er Ban Hui Tiao Screener (V2)

核心逻辑（三个信号同时具备才算启动确认）：

信号一：二连涨停板
- 连续2日涨幅≥9.9%
- 第1个涨停板成交额 ≥ 前1日成交额的2倍

信号二：回调不破首板开盘价
- 二连板后任何交易日的最低价 ≥ 首板开盘价
- 在34天范围内

信号三：启动确认
- 单日收涨（涨幅>0）
- 成交额环比上升（当日成交额 > 前1日成交额）
- 当日最高价创近期新高（比前后几天都高）
- 在34天范围内，且有环比空间

输出：当天回溯，三个信号都具备即输出
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

LIMIT_DAYS = 34  # 最近34个交易日


class ErBanHuiTiaoScreener(BaseScreener):
    """二板回调筛选器 V2"""
    
    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='er_ban_hui_tiao',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
    
    def is_limit_up(self, pct_change: float) -> bool:
        """判断是否涨停"""
        return pct_change >= 9.9
    
    def find_signal_one(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找信号一：二连涨停板 + 首板成交额≥前1日2倍
        
        返回: {
            'first_idx': 首板索引,
            'second_idx': 二板索引,
            'first_open': 首板开盘价,
            'first_high': 首板最高价,
            'first_low': 首板最低价,
            'first_close': 首板收盘价,
            'first_amount': 首板成交额,
            'prev_amount': 首板前一日成交额,
            'second_high': 二板最高价,
            'er_ban_date': 二板日期
        }
        """
        if len(df) < 3:  # 至少需要前1日 + 二连板
            return None
        
        for i in range(len(df) - 2, 0, -1):  # 从后往前找，i是首板索引
            # 检查二连涨停
            first_pct = df.iloc[i]['pct_change'] or 0
            second_pct = df.iloc[i + 1]['pct_change'] or 0
            
            if not (self.is_limit_up(first_pct) and self.is_limit_up(second_pct)):
                continue
            
            # 检查首板成交额 ≥ 前1日成交额的2倍
            first_amount = df.iloc[i]['amount']
            prev_amount = df.iloc[i - 1]['amount']
            
            if prev_amount <= 0 or first_amount < prev_amount * 2:
                continue
            
            return {
                'first_idx': i,
                'second_idx': i + 1,
                'first_open': df.iloc[i]['open'],
                'first_high': df.iloc[i]['high'],
                'first_low': df.iloc[i]['low'],
                'first_close': df.iloc[i]['close'],
                'first_amount': first_amount,
                'prev_amount': prev_amount,
                'second_high': df.iloc[i + 1]['high'],
                'er_ban_date': df.iloc[i + 1]['trade_date']
            }
        
        return None
    
    def check_signal_two(self, df: pd.DataFrame, signal_one: Dict, current_idx: int) -> bool:
        """
        检查信号二：二连板后到当前日，所有交易日最低价 ≥ 首板开盘价
        
        Args:
            df: 完整数据
            signal_one: 信号一信息
            current_idx: 当前检查的日期索引（信号三发生的日期）
        """
        second_idx = signal_one['second_idx']
        first_open = signal_one['first_open']
        
        # 检查二连板后一天到current_idx（不包括current_idx本身）
        for i in range(second_idx + 1, current_idx):
            if i >= len(df):
                break
            day_low = df.iloc[i]['low']
            if day_low < first_open * 0.99:  # 允许1%误差
                return False
        
        return True
    
    def check_signal_three(self, df: pd.DataFrame, idx: int, second_idx: int) -> bool:
        """
        检查信号三：启动确认
        - 单日收涨
        - 当日最高价创二连板以来的新高（比二连板两天的最高价都高）
        
        Args:
            idx: 当前日期索引（信号三发生的日期）
            second_idx: 二板索引（二连板的第二天）
        """
        if idx <= 0 or idx >= len(df):
            return False
        
        current = df.iloc[idx]
        
        # 1. 单日收涨
        if current['pct_change'] <= 0:
            return False
        
        # 2. 当日最高价创二连板以来的新高
        # 获取二连板两天的最高价
        first_board_high = df.iloc[second_idx - 1]['high']  # 首板最高价
        second_board_high = df.iloc[second_idx]['high']      # 二板最高价
        max_er_ban_high = max(first_board_high, second_board_high)
        
        current_high = current['high']
        
        # 当前最高价必须大于二连板两天的最高最高价
        if current_high <= max_er_ban_high:
            return False
        
        return True
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        # 获取足够的数据（34天 + 前后几天用于信号三的判断）
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < 10:
            return None
        
        # 确保数据按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 找信号一
        signal_one = self.find_signal_one(df)
        if signal_one is None:
            return None
        
        second_idx = signal_one['second_idx']
        
        # 检查信号一是否在34天范围内
        latest_date = df.iloc[-1]['trade_date']
        er_ban_date = signal_one['er_ban_date']
        days_since_er_ban = (latest_date - er_ban_date).days
        
        if days_since_er_ban > self.limit_days:
            return None
        
        # 从二连板后一天开始，逐日检查信号三
        for i in range(second_idx + 1, len(df)):
            # 检查信号三
            if not self.check_signal_three(df, i, second_idx):
                continue
            
            # 检查信号二（从二连板后到信号三当天，不破首板开盘价）
            if not self.check_signal_two(df, signal_one, i):
                continue
            
            # 三个信号都满足，输出结果
            current = df.iloc[i]
            
            # 计算最高价创新高的信息
            first_board_high = df.iloc[second_idx - 1]['high']  # 首板最高价
            second_board_high = df.iloc[second_idx]['high']      # 二板最高价
            max_er_ban_high = max(first_board_high, second_board_high)
            current_high = current['high']
            
            return {
                'code': code,
                'name': name,
                'er_ban_date': er_ban_date.strftime('%Y-%m-%d'),
                'signal_three_date': current['trade_date'].strftime('%Y-%m-%d'),
                'days_after_er_ban': i - second_idx,
                'first_open': round(signal_one['first_open'], 2),
                'first_amount': round(signal_one['first_amount'] / 10000, 2),  # 万元
                'prev_amount': round(signal_one['prev_amount'] / 10000, 2),
                'amount_ratio': round(signal_one['first_amount'] / signal_one['prev_amount'], 2),
                'close': round(current['close'], 2),
                'current_price': round(current['close'], 2),
                'pct_change': round(current['pct_change'], 2),
                'turnover': round(current.get('turnover', 0) or 0, 2),
                'current_high': round(current_high, 2),
                'er_ban_max_high': round(max_er_ban_high, 2),
                'high_breakout_ratio': round(current_high / max_er_ban_high, 2),
                'signal_three_confirmed': True
            }
        
        return None
    
    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """运行筛选"""
        if date_str:
            self.current_date = date_str

        # 检查数据是否可用
        if not self.check_data_availability(self.current_date):
            logger.warning(f"⚠️  无可用数据 ({self.current_date}) - 市场尚未收盘或数据未下载")
            return [{
                'code': 'STATUS',
                'name': 'No Data',
                'message': f'无可用数据 ({self.current_date})，市场尚未收盘或数据未下载',
                'error': 'no_data'
            }]

        logger.info("="*60)
        logger.info("二板回调筛选器 V2 - Er Ban Hui Tiao Screener")
        logger.info(f"时间范围: 最近{self.limit_days}个交易日")
        logger.info("筛选条件:")
        logger.info("  信号一: 二连涨停 + 首板成交额≥前1日2倍")
        logger.info("  信号二: 回调不破首板开盘价")
        logger.info("  信号三: 收涨+放量+最高价创新高")
        logger.info("="*60)
        
        # 获取股票列表（排除北交所等）
        stocks = self.get_all_stocks()
        stocks = [
            s for s in stocks
            if not s.code.startswith('8')
            and not s.code.startswith('4')
        ]
        
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
        
        if self.progress_tracker:
            self.progress_tracker.start(
                total_stocks=total_stocks,
                metadata={'date': date_str or self.current_date, 'screener': self.screener_name}
            )
        
        results = []
        analysis_data = {}
        
        for i, stock in enumerate(stocks[start_idx:], start=start_idx):
            try:
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(
                        processed=i+1,
                        matched=len(results),
                        current_code=stock.code
                    )
                
                result = self.screen_stock(stock.code, stock.name)
                
                if result:
                    results.append(result)
                    
                    if enable_analysis and self.news_fetcher:
                        news = self.fetch_news(stock.code)
                        price_data = {
                            'close': result['current_price'],
                            'pct_change': result['pct_change'],
                            'turnover': result['turnover']
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"二板:{result['er_ban_date']}, "
                                   f"启动:{result['signal_three_date']}, "
                                   f"行业:{analysis.get('行业分类', 'N/A')}")
                    else:
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"二板:{result['er_ban_date']}, "
                                   f"启动:{result['signal_three_date']}")
                
                if (i + 1) % 500 == 0:
                    logger.info(f"Progress: {i+1}/{total_stocks}, Found: {len(results)}")
                    
            except Exception as e:
                logger.error(f"Error screening {stock.code}: {e}")
                continue
        
        if self.progress_tracker:
            self.progress_tracker.complete(success=True)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"筛选完成!")
        logger.info(f"检查: {total_stocks} 只股票")
        logger.info(f"匹配: {len(results)} 只股票")
        logger.info(f"{'='*60}")
        
        return results
    
    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'er_ban_date': '二板日期',
            'signal_three_date': '启动确认日期',
            'days_after_er_ban': '二板后天数',
            'first_open': '首板开盘价',
            'first_amount': '首板成交额(万)',
            'prev_amount': '前日成交额(万)',
            'amount_ratio': '首板成交额倍数',
            'current_price': '当前价格',
            'pct_change': '启动日涨幅%',
            'turnover': '换手率%',
            'current_high': '启动日最高价',
            'er_ban_max_high': '二板最高最高价',
            'high_breakout_ratio': '最高价突破倍数',
            'signal_three_confirmed': '信号三确认'
        }

        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='二板回调筛选器 V2')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='时间范围（交易日）')
    parser.add_argument('--no-news', action='store_true', help='禁用新闻抓取')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM分析')
    parser.add_argument('--no-progress', action='store_true', help='禁用进度跟踪')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    screener = ErBanHuiTiaoScreener(
        limit_days=args.limit_days,
        db_path=args.db_path,
        enable_news=False,  # 禁用新闻
        enable_llm=False,   # 禁用LLM
        enable_progress=not args.no_progress
    )
    
    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=False  # 禁用LLM分析
    )
    
    # Handle different return formats
    if result is None:
        results, analysis_data = [], {}
    elif isinstance(result, tuple) and len(result) == 2:
        results, analysis_data = result
    else:
        results, analysis_data = result, {}
    
    if results:
        output_path = screener.save_results(results, analysis_data)
        print(f"\n结果已保存至: {output_path}")
        
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            analysis = analysis_data.get(r['code'], {})
            industry = analysis.get('行业分类', 'N/A')
            print(f"{r['code']} {r['name']} [{industry}]: "
                  f"二板{r['er_ban_date']}, 启动{r['signal_three_date']}, "
                  f"首板成交{r['first_amount']:.0f}万({r['amount_ratio']:.1f}x), "
                  f"启动新高{r['current_high']:.2f}({r['high_breakout_ratio']:.2f}x), "
                  f"当前{r['current_price']:.2f}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'er_ban_hui_tiao_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
