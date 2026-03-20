#!/usr/bin/env python3
"""
突破主升筛选器 - Breakout Main Screener (真突破策略)

策略来源：20天主观多头 - 突破策略实战版
核心逻辑：只做真突破，过滤假突破，做主升惯性

入场条件（必须全满足）：
1. 结构：横盘箱体 ≥ 7天，突破前高/箱体上沿
2. 量能：突破日成交量 = 1.5~2倍5日均量（<3倍防暴量）
3. K线：收盘站稳突破位上方，中阳/大阳（实体饱满）
4. 过滤假突破：无上影线或上影线短（<实体1/3）

出场规则（记录到输出）：
- 止损位：突破位/大阳线开盘价
- 目标1：+8~12%
- 目标2：+15~20%
- 时间止：10天不达标减半，20天强制清

假突破过滤（出现任意一条排除）：
- 长上影（上影线 > 实体1/3）
- 暴量（>3倍5日均量）
- 尾盘回落（收盘 < 最高价×0.97）
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

LIMIT_DAYS = 34  # 回看周期
MIN_CONSOLIDATION_DAYS = 7  # 最小横盘天数
VOLUME_BREAKOUT_MIN = 1.5  # 最小放量倍数
VOLUME_BREAKOUT_MAX = 2.0  # 最大放量倍数（防暴量）
VOLUME_FAKE_THRESHOLD = 3.0  # 暴量阈值（假突破）
MAX_UPPER_SHADOW_RATIO = 0.33  # 最大上影线比例（相对于实体）
MIN_BODY_PCT = 3.0  # 最小阳线实体涨幅


class BreakoutMainScreener(BaseScreener):
    """突破主升筛选器（真突破策略）"""
    
    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 min_consolidation_days: int = MIN_CONSOLIDATION_DAYS,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='breakout_main',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.min_consolidation_days = min_consolidation_days
    
    def find_consolidation_and_breakout(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找横盘整理后的真突破
        
        Returns:
            突破信息或None
        """
        if len(df) < self.min_consolidation_days + 5:
            return None
        
        # 从后往前找突破点
        for i in range(len(df) - 1, self.min_consolidation_days, -1):
            latest = df.iloc[i]
            
            # 检查涨幅（中阳/大阳）
            if latest['pct_change'] < MIN_BODY_PCT:
                continue
            
            # 检查阳线
            if latest['close'] <= latest['open']:
                continue
            
            # 获取横盘期数据
            consolidation_period = df.iloc[i-self.min_consolidation_days:i]
            
            if len(consolidation_period) < self.min_consolidation_days:
                continue
            
            # 计算箱体上沿（横盘期最高价）
            consolidation_high = consolidation_period['high'].max()
            consolidation_low = consolidation_period['low'].min()
            
            # 检查是否突破箱体上沿（突破1%以上）
            if latest['close'] <= consolidation_high * 1.01:
                continue
            
            # 检查横盘期波动幅度（确认是横盘不是趋势）
            consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
            if consolidation_range > 0.15:  # 波动太大不算横盘
                continue
            
            # 计算成交量条件
            avg_volume_5 = df.iloc[i-5:i]['volume'].mean()
            volume_ratio = latest['volume'] / avg_volume_5 if avg_volume_5 > 0 else 0
            
            # 检查放量倍数（1.5-2倍，不能超3倍防假突破）
            if not (VOLUME_BREAKOUT_MIN <= volume_ratio <= VOLUME_BREAKOUT_MAX):
                continue
            
            # 检查假突破：暴量过滤
            if volume_ratio > VOLUME_FAKE_THRESHOLD:
                continue
            
            # 检查K线形态：上影线不能太长
            body_length = latest['close'] - latest['open']
            upper_shadow = latest['high'] - latest['close']
            
            if body_length <= 0:
                continue
            
            upper_shadow_ratio = upper_shadow / body_length if body_length > 0 else 999
            if upper_shadow_ratio > MAX_UPPER_SHADOW_RATIO:
                continue  # 长上影，可能是假突破
            
            # 检查尾盘回落（收盘不应离最高价太远）
            if latest['close'] < latest['high'] * 0.97:
                continue  # 尾盘回落超过3%，可能是假突破
            
            # 计算突破质量
            breakout_quality = (latest['close'] - consolidation_high) / consolidation_high * 100
            
            # 计算止损位和目标位
            stop_loss = consolidation_high  # 跌破箱体上沿止损
            target_1 = latest['close'] * 1.10  # +10%
            target_2 = latest['close'] * 1.18  # +18%
            
            return {
                'consolidation_high': round(consolidation_high, 2),
                'consolidation_low': round(consolidation_low, 2),
                'consolidation_range_pct': round(consolidation_range * 100, 2),
                'breakout_price': round(latest['close'], 2),
                'breakout_high': round(latest['high'], 2),
                'breakout_low': round(latest['low'], 2),
                'breakout_pct': round(latest['pct_change'], 2),
                'body_length': round(body_length, 2),
                'upper_shadow_ratio': round(upper_shadow_ratio, 2),
                'volume_ratio': round(volume_ratio, 2),
                'avg_volume_5': int(avg_volume_5),
                'breakout_quality': round(breakout_quality, 2),
                'consolidation_days': self.min_consolidation_days,
                'stop_loss': round(stop_loss, 2),
                'target_1': round(target_1, 2),
                'target_2': round(target_2, 2),
                'is_true_breakout': True
            }
        
        return None
    
    def check_ma_trend(self, df: pd.DataFrame) -> Dict:
        """检查均线趋势"""
        if len(df) < 20:
            return {'ma5': 0, 'ma10': 0, 'ma20': 0, 'trend': 'unknown'}
        
        ma5 = df.iloc[-5:]['close'].mean()
        ma10 = df.iloc[-10:]['close'].mean()
        ma20 = df.iloc[-20:]['close'].mean()
        
        # 判断趋势
        if ma5 > ma10 > ma20:
            trend = 'bullish'
        elif ma5 < ma10 < ma20:
            trend = 'bearish'
        else:
            trend = 'mixed'
        
        return {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'trend': trend
        }
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < self.limit_days:
            return None
        
        # 确保数据按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 寻找真突破
        breakout_info = self.find_consolidation_and_breakout(df)
        if breakout_info is None:
            return None
        
        # 检查均线趋势（排除空头排列）
        ma_info = self.check_ma_trend(df)
        if ma_info['trend'] == 'bearish':
            return None
        
        latest = df.iloc[-1]
        
        return {
            'code': code,
            'name': name,
            'close': round(breakout_info['breakout_price'], 2),
            'current_price': round(breakout_info['breakout_price'], 2),
            'pct_change': breakout_info['breakout_pct'],
            'turnover': round(latest.get('turnover', 0) or 0, 2),
            'consolidation_high': breakout_info['consolidation_high'],
            'consolidation_low': breakout_info['consolidation_low'],
            'consolidation_range_pct': breakout_info['consolidation_range_pct'],
            'breakout_high': breakout_info['breakout_high'],
            'breakout_low': breakout_info['breakout_low'],
            'breakout_pct': breakout_info['breakout_pct'],
            'body_length': breakout_info['body_length'],
            'upper_shadow_ratio': breakout_info['upper_shadow_ratio'],
            'volume_ratio': breakout_info['volume_ratio'],
            'avg_volume_5': breakout_info['avg_volume_5'],
            'breakout_quality': breakout_info['breakout_quality'],
            'consolidation_days': breakout_info['consolidation_days'],
            'stop_loss': breakout_info['stop_loss'],
            'target_1': breakout_info['target_1'],
            'target_2': breakout_info['target_2'],
            'is_true_breakout': breakout_info['is_true_breakout'],
            'ma5': ma_info['ma5'],
            'ma10': ma_info['ma10'],
            'ma20': ma_info['ma20'],
            'ma_trend': ma_info['trend']
        }
    
    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """
        详细检查单个股票是否符合筛选条件
        返回详细的匹配信息和不符合的原因
        """
        # 设置日期
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        reasons = []
        details = {}
        
        # 获取股票名称
        try:
            session = get_session(init_db())
            stock = session.query(Stock).filter_by(code=code).first()
            name = stock.name if stock else ''
            session.close()
        except:
            name = ''
        
        # 获取股票数据
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取股票数据（可能是退市股或数据不足）']
            }
        
        if len(df) < self.limit_days:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [f'历史数据不足，需要{self.limit_days}天，实际{len(df)}天']
            }
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        latest = df.iloc[-1]
        
        # 检查1：涨幅（中阳/大阳）
        if latest['pct_change'] < MIN_BODY_PCT:
            reasons.append(f'涨幅不足：{latest["pct_change"]:.2f}% < {MIN_BODY_PCT}%（需要中阳/大阳）')
        else:
            details['涨幅'] = f'{latest["pct_change"]:.2f}%'
        
        # 检查2：阳线
        if latest['close'] <= latest['open']:
            reasons.append('K线不是阳线（收盘价必须>开盘价）')
        
        # 获取横盘期数据
        if len(df) < self.min_consolidation_days + 1:
            reasons.append(f'数据不足以分析横盘（需要{self.min_consolidation_days+1}天）')
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details
            }
        
        consolidation_period = df.iloc[-self.min_consolidation_days-1:-1]
        consolidation_high = consolidation_period['high'].max()
        consolidation_low = consolidation_period['low'].min()
        
        # 检查3：突破箱体上沿
        if latest['close'] <= consolidation_high * 1.01:
            reasons.append(f'未突破箱体上沿：收盘价{latest["close"]:.2f} <= 箱体上沿{consolidation_high * 1.01:.2f}')
        else:
            breakout_pct = (latest['close'] - consolidation_high) / consolidation_high * 100
            details['突破幅度'] = f'{breakout_pct:.2f}%'
        
        # 检查4：横盘期波动幅度
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
        if consolidation_range > 0.15:
            reasons.append(f'横盘期波动过大：{consolidation_range*100:.1f}% > 15%（不是有效横盘）')
        else:
            details['横盘波动'] = f'{consolidation_range*100:.1f}%'
        
        # 检查5：成交量
        avg_volume_5 = df.iloc[-6:-1]['volume'].mean()
        volume_ratio = latest['volume'] / avg_volume_5 if avg_volume_5 > 0 else 0
        
        if volume_ratio < VOLUME_BREAKOUT_MIN:
            reasons.append(f'放量不足：{volume_ratio:.2f}倍 < {VOLUME_BREAKOUT_MIN}倍（需要放量突破）')
        elif volume_ratio > VOLUME_BREAKOUT_MAX:
            reasons.append(f'放量过大：{volume_ratio:.2f}倍 > {VOLUME_BREAKOUT_MAX}倍（可能是暴量假突破）')
        elif volume_ratio > VOLUME_FAKE_THRESHOLD:
            reasons.append(f'成交量暴量：{volume_ratio:.2f}倍 > {VOLUME_FAKE_THRESHOLD}倍（疑似假突破）')
        else:
            details['量比'] = f'{volume_ratio:.2f}倍'
        
        # 检查6：K线形态 - 上影线
        body_length = latest['close'] - latest['open']
        upper_shadow = latest['high'] - latest['close']
        if body_length > 0:
            upper_shadow_ratio = upper_shadow / body_length
            if upper_shadow_ratio > MAX_UPPER_SHADOW_RATIO:
                reasons.append(f'上影线过长：{upper_shadow_ratio:.2f} > {MAX_UPPER_SHADOW_RATIO}（可能是假突破）')
            else:
                details['上影线比例'] = f'{upper_shadow_ratio:.2f}'
        
        # 检查7：尾盘回落
        if latest['close'] < latest['high'] * 0.97:
            pullback_pct = (latest['high'] - latest['close']) / latest['high'] * 100
            reasons.append(f'尾盘回落过大：{pullback_pct:.1f}% > 3%（收盘离最高价太远）')
        
        # 判断结果
        if len(reasons) == 0:
            # 所有条件都满足
            ma_info = self.check_ma_trend(df)
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [],
                'details': {
                    **details,
                    '收盘价': f'{latest["close"]:.2f}',
                    '箱体上沿': f'{consolidation_high:.2f}',
                    'MA5': f'{ma_info["ma5"]:.2f}',
                    'MA10': f'{ma_info["ma10"]:.2f}',
                    'MA20': f'{ma_info["ma20"]:.2f}',
                    '趋势': '多头排列' if ma_info['trend'] == 'bullish' else ma_info['trend']
                }
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details if details else None
            }
    
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
        logger.info("突破主升筛选器 - Breakout Main Screener")
        logger.info(f"时间范围: 最近{self.limit_days}个交易日")
        logger.info("入场条件:")
        logger.info(f"  - 横盘≥{self.min_consolidation_days}天")
        logger.info(f"  - 放量{VOLUME_BREAKOUT_MIN}-{VOLUME_BREAKOUT_MAX}倍（<{VOLUME_BREAKOUT_MAX}倍防暴量）")
        logger.info(f"  - 上影线比例<{MAX_UPPER_SHADOW_RATIO}")
        logger.info(f"  - 尾盘回落<3%")
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
                            'pct_change': result.get('pct_change', 0),
                            'turnover': result.get('turnover', 0)
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"突破{result['breakout_quality']:.1f}%, "
                                   f"行业:{analysis.get('行业分类', 'N/A')}")
                    else:
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"突破{result['breakout_quality']:.1f}%")
                
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
    
    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'close': '收盘价',
            'current_price': '当前价格',
            'pct_change': '涨幅%',
            'turnover': '换手率%',
            'consolidation_high': '箱体上沿',
            'consolidation_low': '箱体下沿',
            'consolidation_range_pct': '箱体波动%',
            'breakout_high': '突破最高价',
            'breakout_low': '突破最低价',
            'breakout_pct': '突破涨幅%',
            'body_length': 'K线实体',
            'upper_shadow_ratio': '上影线比例',
            'volume_ratio': '放量倍数',
            'avg_volume_5': '5日均量',
            'breakout_quality': '突破质量%',
            'consolidation_days': '横盘天数',
            'stop_loss': '止损位',
            'target_1': '目标位1(+10%)',
            'target_2': '目标位2(+18%)',
            'is_true_breakout': '真突破确认',
            'ma5': 'MA5',
            'ma10': 'MA10',
            'ma20': 'MA20',
            'ma_trend': '均线趋势'
        }
        
        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='突破主升筛选器（真突破策略）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='回看周期')
    parser.add_argument('--min-consolidation', type=int, default=MIN_CONSOLIDATION_DAYS, help='最小横盘天数')
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
    
    screener = BreakoutMainScreener(
        limit_days=args.limit_days,
        min_consolidation_days=args.min_consolidation,
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
                  f"突破{r['breakout_quality']:.1f}%, "
                  f"放量{r['volume_ratio']:.1f}x, "
                  f"止损{r['stop_loss']:.2f}, "
                  f"目标1{r['target_1']:.2f}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'breakout_main_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
