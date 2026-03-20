#!/usr/bin/env python3
"""
涨停倍量阴筛选器 - Zhang Ting Bei Liang Yin Screener (V2)

核心逻辑（五个信号同时具备才算启动确认）：

信号一：阳线实体涨停，且实体长度为下引线长度3倍以上
- 涨幅≥9.9%
- (收盘价-开盘价) ≥ 3 × (开盘价-最低价)

信号二：次日高开收阴，阴线实体长度为上引+下引之和的2倍以上
- 高开（开盘价 > 前收盘价）
- 收阴（收盘价 < 开盘价）
- (开盘价-收盘价) ≥ 2 × [(最高价-开盘价) + (收盘价-最低价)]

信号三：信号二当日成交额 > 信号一当日成交额 × 2

信号四：X日（信号二当日）后出现地量，成交额 < X日成交额 × 0.5

信号五：T日（地量日）后出现启动信号
- 单日收涨
- 成交额 > 前一日成交额 × 2

输出：五个信号都满足即输出
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

LIMIT_DAYS = 34  # 最近34个交易日


class ZhangTingBeiLiangYinScreener(BaseScreener):
    """涨停倍量阴筛选器 V2"""
    
    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='zhang_ting_bei_liang_yin',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
    
    def is_limit_up(self, pct_change: float) -> bool:
        """判断是否涨停"""
        return pct_change >= 9.9
    
    def check_signal_one(self, df: pd.DataFrame, idx: int) -> bool:
        """
        检查信号一：阳线实体涨停，且实体长度为下引线长度3倍以上
        
        Args:
            idx: 涨停日索引
        """
        if idx < 0 or idx >= len(df):
            return False
        
        row = df.iloc[idx]
        
        # 1. 涨停
        if not self.is_limit_up(row['pct_change'] or 0):
            return False
        
        # 2. 阳线（收盘价 > 开盘价）
        if row['close'] <= row['open']:
            return False
        
        # 3. 实体长度为下引线长度3倍以上
        # 实体长度 = 收盘价 - 开盘价
        # 下引线长度 = 开盘价 - 最低价
        body_length = row['close'] - row['open']
        lower_shadow = row['open'] - row['low']
        
        if lower_shadow <= 0:
            return False
        
        if body_length < lower_shadow * 3:
            return False
        
        return True
    
    def check_signal_two(self, df: pd.DataFrame, idx: int) -> bool:
        """
        检查信号二：次日高开收阴，阴线实体长度为上引+下引之和的2倍以上
        
        Args:
            idx: 信号二当日索引（涨停日的次日）
        """
        if idx <= 0 or idx >= len(df):
            return False
        
        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]
        
        # 1. 高开（开盘价 > 前收盘价）
        if row['open'] <= prev_row['close']:
            return False
        
        # 2. 收阴（收盘价 < 开盘价）
        if row['close'] >= row['open']:
            return False
        
        # 3. 阴线实体长度为上引+下引之和的2倍以上
        # 阴线实体长度 = 开盘价 - 收盘价
        # 上引线长度 = 最高价 - 开盘价
        # 下引线长度 = 收盘价 - 最低价
        body_length = row['open'] - row['close']
        upper_shadow = row['high'] - row['open']
        lower_shadow = row['close'] - row['low']
        
        total_shadow = upper_shadow + lower_shadow
        
        if total_shadow <= 0:
            return False
        
        if body_length < total_shadow * 2:
            return False
        
        return True
    
    def check_signal_three(self, df: pd.DataFrame, signal_one_idx: int, signal_two_idx: int) -> bool:
        """
        检查信号三：信号二当日成交额 > 信号一当日成交额 × 2
        """
        if signal_one_idx < 0 or signal_two_idx >= len(df):
            return False
        
        signal_one_amount = df.iloc[signal_one_idx]['amount']
        signal_two_amount = df.iloc[signal_two_idx]['amount']
        
        return signal_two_amount > signal_one_amount * 2
    
    def find_signal_four(self, df: pd.DataFrame, signal_two_idx: int) -> Optional[int]:
        """
        寻找信号四：X日（信号二当日）后出现地量，成交额 < X日成交额 × 0.5
        
        Returns:
            地量日的索引，或None
        """
        if signal_two_idx < 0 or signal_two_idx >= len(df):
            return None
        
        signal_two_amount = df.iloc[signal_two_idx]['amount']
        threshold = signal_two_amount * 0.5
        
        # 从信号二后一天开始找
        for i in range(signal_two_idx + 1, len(df)):
            if df.iloc[i]['amount'] < threshold:
                return i
        
        return None
    
    def find_signal_five(self, df: pd.DataFrame, signal_four_idx: int) -> Optional[int]:
        """
        寻找信号五：T日（地量日）后出现启动信号
        - 单日收涨
        - 成交额 > 前一日成交额 × 2
        
        Returns:
            启动日的索引，或None
        """
        if signal_four_idx < 0 or signal_four_idx >= len(df):
            return None
        
        # 从地量日后一天开始找
        for i in range(signal_four_idx + 1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            
            # 1. 单日收涨
            if row['pct_change'] <= 0:
                continue
            
            # 2. 成交额 > 前一日成交额 × 2
            if row['amount'] <= prev_row['amount'] * 2:
                continue
            
            return i
        
        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < 10:
            return None
        
        # 确保数据按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 找信号一（涨停日）
        for i in range(len(df) - 1, -1, -1):
            # 检查信号一
            if not self.check_signal_one(df, i):
                continue
            
            signal_one_idx = i
            
            # 检查是否在34天范围内
            latest_date = df.iloc[-1]['trade_date']
            signal_one_date = df.iloc[signal_one_idx]['trade_date']
            days_since = (latest_date - signal_one_date).days
            
            if days_since > self.limit_days:
                continue
            
            # 检查信号二（次日）
            signal_two_idx = signal_one_idx + 1
            if signal_two_idx >= len(df):
                continue
            
            if not self.check_signal_two(df, signal_two_idx):
                continue
            
            # 检查信号三
            if not self.check_signal_three(df, signal_one_idx, signal_two_idx):
                continue
            
            # 找信号四（地量日）
            signal_four_idx = self.find_signal_four(df, signal_two_idx)
            if signal_four_idx is None:
                continue
            
            # 找信号五（启动日）
            signal_five_idx = self.find_signal_five(df, signal_four_idx)
            if signal_five_idx is None:
                continue
            
            # 五个信号都满足，输出结果
            signal_one = df.iloc[signal_one_idx]
            signal_two = df.iloc[signal_two_idx]
            signal_four = df.iloc[signal_four_idx]
            signal_five = df.iloc[signal_five_idx]
            
            # 计算K线特征
            s1_body = signal_one['close'] - signal_one['open']
            s1_lower = signal_one['open'] - signal_one['low']
            s1_ratio = round(s1_body / s1_lower, 2) if s1_lower > 0 else 0
            
            s2_body = signal_two['open'] - signal_two['close']
            s2_upper = signal_two['high'] - signal_two['open']
            s2_lower = signal_two['close'] - signal_two['low']
            s2_ratio = round(s2_body / (s2_upper + s2_lower), 2) if (s2_upper + s2_lower) > 0 else 0
            
            return {
                'code': code,
                'name': name,
                'signal_one_date': signal_one['trade_date'].strftime('%Y-%m-%d'),
                'signal_two_date': signal_two['trade_date'].strftime('%Y-%m-%d'),
                'signal_four_date': signal_four['trade_date'].strftime('%Y-%m-%d'),
                'signal_five_date': signal_five['trade_date'].strftime('%Y-%m-%d'),
                'days_to_launch': signal_five_idx - signal_one_idx,
                
                # 信号一特征
                's1_open': round(signal_one['open'], 2),
                's1_close': round(signal_one['close'], 2),
                's1_low': round(signal_one['low'], 2),
                's1_body_ratio': s1_ratio,
                's1_amount': round(signal_one['amount'] / 10000, 2),
                
                # 信号二特征
                's2_open': round(signal_two['open'], 2),
                's2_close': round(signal_two['close'], 2),
                's2_high': round(signal_two['high'], 2),
                's2_low': round(signal_two['low'], 2),
                's2_body_ratio': s2_ratio,
                's2_amount': round(signal_two['amount'] / 10000, 2),
                
                # 信号三：成交额倍数
                'amount_ratio_s2_s1': round(signal_two['amount'] / signal_one['amount'], 2),
                
                # 信号四：地量
                's4_amount': round(signal_four['amount'] / 10000, 2),
                'di_liang_ratio': round(signal_four['amount'] / signal_two['amount'], 2),
                
                # 信号五：启动
                's5_close': round(signal_five['close'], 2),
                's5_pct_change': round(signal_five['pct_change'], 2),
                's5_amount': round(signal_five['amount'] / 10000, 2),
                's5_amount_ratio': round(signal_five['amount'] / df.iloc[signal_five_idx - 1]['amount'], 2),
                
                'all_signals_confirmed': True
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
        logger.info("涨停倍量阴筛选器 V2 - Zhang Ting Bei Liang Yin Screener")
        logger.info(f"时间范围: 最近{self.limit_days}个交易日")
        logger.info("筛选条件:")
        logger.info("  信号一: 阳线实体涨停，实体/下引≥3")
        logger.info("  信号二: 次日高开收阴，实体/(上引+下引)≥2")
        logger.info("  信号三: 信号二成交额 > 信号一×2")
        logger.info("  信号四: 地量，成交额 < 信号二×0.5")
        logger.info("  信号五: 启动，收涨+成交额翻倍")
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
                            'close': result['s5_close'],
                            'pct_change': result['s5_pct_change'],
                            'turnover': 0
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"涨停:{result['signal_one_date']}, "
                                   f"启动:{result['signal_five_date']}, "
                                   f"行业:{analysis.get('行业分类', 'N/A')}")
                    else:
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"涨停:{result['signal_one_date']}, "
                                   f"启动:{result['signal_five_date']}")
                
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
            'signal_one_date': '涨停日期',
            'signal_two_date': '倍量阴日期',
            'signal_four_date': '地量日期',
            'signal_five_date': '启动日期',
            'days_to_launch': '涨停到启动天数',
            's1_body_ratio': '信号一实体/下引',
            's2_body_ratio': '信号二实体/(上引+下引)',
            'amount_ratio_s2_s1': '倍量阴/涨停成交额',
            'di_liang_ratio': '地量/倍量阴成交额',
            's5_pct_change': '启动日涨幅%',
            's5_amount_ratio': '启动日成交额环比',
            'all_signals_confirmed': '五信号确认'
        }
        
        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='涨停倍量阴筛选器 V2')
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
    
    screener = ZhangTingBeiLiangYinScreener(
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
                  f"涨停{r['signal_one_date']}, 倍量阴{r['signal_two_date']}, "
                  f"启动{r['signal_five_date']}, "
                  f"实体/下引{r['s1_body_ratio']:.1f}x, "
                  f"倍量{r['amount_ratio_s2_s1']:.1f}x")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'zhang_ting_bei_liang_yin_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
