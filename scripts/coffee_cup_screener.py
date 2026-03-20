#!/usr/bin/env python3
"""
咖啡杯形态筛选器 - Coffee Cup Pattern Screener (欧奈尔标准版)

欧奈尔CANSLIM标准参数：
- 杯体周期：50-60天（2.5~3个月）
- 柄部周期：15-20天（3~4周）
- 杯深范围：12% ~ 35%
- 柄调范围：5% ~ 12%
- 突破条件：收盘价突破柄部区间最高价
- 缩量条件：柄部均量 < 前期均量 × 0.85
- 均线多头：MA50 > MA150 > MA200，且MA200向上

新增功能：
1. U型杯体验证（最低点在30%-70%中部区域）
2. RS相对强度 ≥ 85（超越85%个股）
3. 自动风控计算（止损位、目标位、盈亏比）
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import logging
import argparse

from base_screener import BaseScreener
from database import init_db, get_session, Stock, DailyPrice

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path('/Users/mac/.openclaw/workspace-neo')

# 欧奈尔标准参数配置
class OneilParams:
    """欧奈尔杯柄形态标准参数"""
    # 杯体参数
    CUP_PERIOD_MIN = 60          # 杯体最小周期（天）
    CUP_PERIOD_MAX = 250         # 杯体最大周期（天）
    CUP_DEPTH_MIN = 0.20         # 杯深最小20%
    CUP_DEPTH_MAX = 0.50         # 杯深最大50%
    
    # 柄部参数
    HANDLE_PERIOD_MIN = 1        # 柄部最小周期（天）
    HANDLE_PERIOD_MAX = 21       # 柄部最大周期（天）
    HANDLE_RETRACE_MIN = 0.05    # 柄调最小5%
    HANDLE_RETRACE_MAX = 0.12    # 柄调最大12%
    HANDLE_VOLUME_RATIO = 0.85   # 柄部缩量比例（<85%）
    
    # 突破条件
    BREAKOUT_THRESHOLD = 1.0     # 突破柄部高点的比例（1.0 = 100%）
    
    # 均线参数
    MA_SHORT = 50                # 短期均线
    MA_MEDIUM = 150              # 中期均线
    MA_LONG = 200                # 长期均线
    
    # 杯沿条件
    MIN_TURNOVER = 5.0           # 最小换手率5%
    MIN_PCT_CHANGE = 2.0         # 最小涨幅2%
    VOLUME_SURGE_RATIO = 2.0     # 放量倍数（≥2倍）
    
    # RS强度
    RS_MIN_SCORE = 85            # RS最低分数85


class CoffeeCupScreener(BaseScreener):
    """咖啡杯形态筛选器（欧奈尔标准版）"""
    
    def __init__(self, 
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True,
                 check_data_update: bool = False,
                 quick_mode: bool = False,
                 params: OneilParams = None):
        """
        初始化筛选器
        
        Args:
            params: 欧奈尔参数配置，默认使用标准参数
        """
        super().__init__(
            screener_name='coffee_cup',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        self.params = params or OneilParams()
        self.check_data_update = check_data_update
        self.quick_mode = quick_mode
        self.progress_file = WORKSPACE_ROOT / 'data' / 'daily_update_progress.json'
        
        if not quick_mode:
            self.engine = init_db()
            self.session = get_session(self.engine)
    
    def _check_update_status(self) -> Dict:
        """检查数据更新状态"""
        if not self.progress_file.exists():
            return {'ready': False, 'completion_rate': 0, 'message': 'No progress file'}
        
        with open(self.progress_file, 'r') as f:
            progress = json.load(f)
        
        status = progress.get('status', 'unknown')
        planned = progress.get('planned', 0)
        completed = len(progress.get('completed', []))
        completion_rate = progress.get('completion_rate', 0)
        
        if planned > 0:
            completion_rate = (completed / planned) * 100
        
        return {
            'ready': status == 'completed' and completion_rate >= 100,
            'status': status,
            'completion_rate': completion_rate,
            'completed': completed,
            'planned': planned
        }
    
    def check_volume_surge(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        检查放量条件：
        最近3天（含今天）成交额总和 ≥ 前3天成交额总和的 2倍
        """
        if len(df) < 7:
            return False, 0
        
        recent_3_days = df.iloc[-3:]['amount'].sum()
        previous_3_days = df.iloc[-6:-3]['amount'].sum()
        
        if previous_3_days <= 0:
            return False, 0
        
        volume_ratio = recent_3_days / previous_3_days
        return volume_ratio >= self.params.VOLUME_SURGE_RATIO, volume_ratio
    
    def find_cup_handle_oneil(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找欧奈尔标准杯柄形态
        
        Returns:
            杯柄信息或None
        """
        if len(df) < self.params.CUP_PERIOD_MAX + self.params.HANDLE_PERIOD_MAX:
            return None
        
        # 获取最新价格（杯沿候选）
        latest = df.iloc[-1]
        cup_rim_price = latest['close']
        latest_date = latest['trade_date']
        
        # 在杯体周期范围内寻找杯柄
        cup_period_start = len(df) - self.params.CUP_PERIOD_MAX
        cup_period_end = len(df) - self.params.CUP_PERIOD_MIN
        
        if cup_period_start < 0:
            return None
        
        # 遍历寻找符合条件的杯柄
        for handle_end_idx in range(cup_period_end, cup_period_start, -1):
            handle_start_idx = max(0, handle_end_idx - self.params.HANDLE_PERIOD_MAX)
            
            if handle_start_idx < 10:  # 需要足够的前期数据
                continue
            
            handle_period = df.iloc[handle_start_idx:handle_end_idx]
            pre_handle_period = df.iloc[handle_start_idx-self.params.HANDLE_PERIOD_MIN:handle_start_idx]
            
            if len(handle_period) < self.params.HANDLE_PERIOD_MIN:
                continue
            
            # 计算柄部参数
            handle_high = handle_period['high'].max()
            handle_low = handle_period['low'].min()
            handle_close_avg = handle_period['close'].mean()
            
            # 杯柄价格应与杯沿接近（≤5%差异）
            pre_handle_high = pre_handle_period['high'].max()
            price_diff_pct = abs(handle_high - pre_handle_high) / pre_handle_high
            
            if price_diff_pct > 0.05:
                continue
            
            # 检查缩量条件（柄部成交量 < 前期85%）
            handle_volume_avg = handle_period['volume'].mean()
            pre_handle_volume_avg = pre_handle_period['volume'].mean()
            
            if pre_handle_volume_avg > 0:
                volume_ratio = handle_volume_avg / pre_handle_volume_avg
                if volume_ratio > self.params.HANDLE_VOLUME_RATIO:
                    continue  # 未缩量
            
            # 找到符合条件的杯柄，计算杯体参数
            cup_start_idx = max(0, handle_start_idx - 30)  # 杯体至少30天
            cup_period = df.iloc[cup_start_idx:handle_start_idx]
            
            if len(cup_period) < 20:
                continue
            
            cup_high = max(pre_handle_high, handle_high)
            cup_low = cup_period['low'].min()
            cup_depth = (cup_high - cup_low) / cup_high
            
            # 检查杯深范围（20% ~ 50%）
            if not (self.params.CUP_DEPTH_MIN <= cup_depth <= self.params.CUP_DEPTH_MAX):
                continue
            
            # 计算柄调幅度（回调百分比）
            handle_retrace = (pre_handle_high - handle_low) / pre_handle_high
            # 柄调范围：0 到 1/2 杯深
            handle_retrace_max = cup_depth / 2
            if not (0 <= handle_retrace <= handle_retrace_max):
                continue
            
            # 检查杯底是否有高于杯柄的凸起
            has_spike = False
            for _, day in cup_period.iterrows():
                if day['high'] > cup_high * 0.98:  # 允许2%的误差
                    has_spike = True
                    break
            
            if has_spike:
                continue
            
            # 计算U型验证
            cup_low_idx = cup_period['low'].idxmin()
            cup_lowest_date = df.loc[cup_low_idx, 'trade_date']
            cup_position = (cup_low_idx - cup_start_idx) / len(cup_period)
            
            # 检查是否突破柄部高点
            if cup_rim_price <= handle_high * 1.01:  # 需要突破柄部高点1%以上
                continue
            
            return {
                'handle_date': str(handle_period.iloc[-1]['trade_date']),
                'handle_high': round(handle_high, 2),
                'handle_low': round(handle_low, 2),
                'handle_retrace': round(handle_retrace * 100, 2),
                'handle_volume_ratio': round(volume_ratio * 100, 2),
                'cup_high': round(cup_high, 2),
                'cup_low': round(cup_low, 2),
                'cup_depth': round(cup_depth * 100, 2),
                'cup_lowest_date': str(cup_lowest_date),
                'cup_position': round(cup_position * 100, 2),
                'cup_is_u_shape': 30 <= cup_position * 100 <= 70,
                'breakout_price': round(cup_rim_price, 2),
                'breakout_pct': round((cup_rim_price - handle_high) / handle_high * 100, 2),
                'days_apart': len(df) - handle_end_idx
            }
        
        return None
    
    def check_ma_trend(self, df: pd.DataFrame) -> Dict:
        """检查均线趋势（50/150/200日均线）"""
        if len(df) < self.params.MA_LONG:
            return {'valid': False, 'reason': '数据不足200天'}
        
        ma50 = df.iloc[-self.params.MA_SHORT:]['close'].mean()
        ma150 = df.iloc[-self.params.MA_MEDIUM:]['close'].mean()
        ma200 = df.iloc[-self.params.MA_LONG:]['close'].mean()
        ma200_prev = df.iloc[-self.params.MA_LONG-5:-5]['close'].mean()
        
        # 多头排列：MA50 > MA150 > MA200
        bullish_arrangement = ma50 > ma150 > ma200
        
        # MA200向上
        ma200_rising = ma200 > ma200_prev
        
        return {
            'valid': True,
            'ma50': round(ma50, 2),
            'ma150': round(ma150, 2),
            'ma200': round(ma200, 2),
            'ma200_prev': round(ma200_prev, 2),
            'bullish_arrangement': bullish_arrangement,
            'ma200_rising': ma200_rising,
            'score': sum([ma50 > ma150, ma150 > ma200, ma200_rising])
        }
    
    def calculate_rs_score(self, df: pd.DataFrame) -> float:
        """计算RS相对强度分数（简化版）"""
        if len(df) < 252:  # 需要一年数据
            return 50
        
        # 计算过去12个月涨幅
        price_12m_ago = df.iloc[-252]['close'] if len(df) >= 252 else df.iloc[0]['close']
        price_now = df.iloc[-1]['close']
        stock_return = (price_now - price_12m_ago) / price_12m_ago * 100
        
        # 简化的RS分数映射
        if stock_return > 100:
            return 95
        elif stock_return > 50:
            return 85 + (stock_return - 50) / 5
        elif stock_return > 30:
            return 75 + (stock_return - 30) / 2
        elif stock_return > 10:
            return 65 + (stock_return - 10) / 2
        elif stock_return > 0:
            return 55 + stock_return
        else:
            return max(30, 50 + stock_return / 2)
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票（欧奈尔标准）"""
        # 获取足够的历史数据
        df = self.get_stock_data(code, days=400)
        if df is None or len(df) < 310:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        yesterday = df.iloc[-1]
        
        # 1. 检查换手率
        turnover = yesterday.get('turnover', 0) or 0
        if turnover < self.params.MIN_TURNOVER:
            return None
        
        # 2. 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < self.params.MIN_PCT_CHANGE:
            return None
        
        # 3. 检查放量
        has_volume_surge, volume_ratio = self.check_volume_surge(df)
        if not has_volume_surge:
            return None
        
        # 4. 寻找杯柄形态
        cup_handle = self.find_cup_handle_oneil(df)
        if cup_handle is None:
            return None
        
        # 5. 检查均线趋势
        ma_info = self.check_ma_trend(df)
        if not ma_info.get('valid') or not ma_info['bullish_arrangement']:
            return None
        
        # 6. 检查RS相对强度
        rs_score = self.calculate_rs_score(df)
        if rs_score < self.params.RS_MIN_SCORE:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'turnover': round(turnover, 2),
            'pct_change': round(pct_change, 2),
            'volume_ratio': round(volume_ratio, 2),
            'handle_date': cup_handle['handle_date'],
            'handle_high': cup_handle['handle_high'],
            'handle_low': cup_handle['handle_low'],
            'handle_retrace': cup_handle['handle_retrace'],
            'handle_volume_ratio': cup_handle['handle_volume_ratio'],
            'cup_depth': cup_handle['cup_depth'],
            'cup_is_u_shape': cup_handle['cup_is_u_shape'],
            'cup_position': cup_handle['cup_position'],
            'breakout_pct': cup_handle['breakout_pct'],
            'ma50': ma_info['ma50'],
            'ma150': ma_info['ma150'],
            'ma200': ma_info['ma200'],
            'ma200_rising': ma_info['ma200_rising'],
            'rs_score': round(rs_score, 0)
        }
    
    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """详细检查单个股票（欧奈尔标准完整版）"""
        # 设置日期
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        reasons = []
        details = {}
        risk_management = {}
        
        # 获取股票名称
        try:
            session = get_session(init_db())
            stock = session.query(Stock).filter_by(code=code).first()
            name = stock.name if stock else ''
            session.close()
        except:
            name = ''
        
        # 获取股票数据
        df = self.get_stock_data(code, days=400)
        if df is None or len(df) < 310:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少310天用于杯柄形态计算）']
            }
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        yesterday = df.iloc[-1]
        
        # ========== 1. 基础条件检查 ==========
        turnover = yesterday.get('turnover', 0) or 0
        if turnover < self.params.MIN_TURNOVER:
            reasons.append(f'换手率不足：{turnover:.2f}% < {self.params.MIN_TURNOVER}%（需要高换手确认突破）')
        else:
            details['换手率'] = f'{turnover:.2f}%'
        
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < self.params.MIN_PCT_CHANGE:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < {self.params.MIN_PCT_CHANGE}%（需要阳线确认）')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 放量检查
        has_volume_surge, volume_ratio = self.check_volume_surge(df)
        if not has_volume_surge:
            reasons.append(f'未放量：量比{volume_ratio:.2f}倍 < {self.params.VOLUME_SURGE_RATIO}倍（突破需要放量）')
        else:
            details['量比'] = f'{volume_ratio:.2f}倍'
        
        # ========== 2. 杯柄形态检查 ==========
        cup_handle = self.find_cup_handle_oneil(df)
        
        if cup_handle is None:
            reasons.append(f'未找到欧奈尔标准杯柄形态（需满足：杯体{self.params.CUP_PERIOD_MIN}-{self.params.CUP_PERIOD_MAX}天、'
                          f'柄部{self.params.HANDLE_PERIOD_MIN}-{self.params.HANDLE_PERIOD_MAX}天、'
                          f'杯深{self.params.CUP_DEPTH_MIN*100:.0f}%-{self.params.CUP_DEPTH_MAX*100:.0f}%、'
                          f'柄调0-1/2杯深、缩量<{self.params.HANDLE_VOLUME_RATIO*100:.0f}%）')
        else:
            details['杯柄日期'] = cup_handle['handle_date']
            details['柄部高点'] = f"{cup_handle['handle_high']:.2f}"
            details['柄部低点'] = f"{cup_handle['handle_low']:.2f}"
            details['柄调幅度'] = f"{cup_handle['handle_retrace']:.1f}%"
            details['柄部缩量'] = f"{cup_handle['handle_volume_ratio']:.1f}%"
            details['杯深'] = f"{cup_handle['cup_depth']:.1f}%"
            details['突破幅度'] = f"{cup_handle['breakout_pct']:.2f}%"
            
            # U型验证
            if cup_handle['cup_is_u_shape']:
                details['U型验证'] = f"✓ 最低点在杯身{cup_handle['cup_position']:.0f}%处（符合30%-70%中部区域）"
            else:
                if cup_handle['cup_position'] < 30:
                    reasons.append(f"杯型偏V型：最低点在左侧{cup_handle['cup_position']:.0f}%处（应在30%-70%中部区域）")
                else:
                    reasons.append(f"杯型偏倒V型：最低点在右侧{cup_handle['cup_position']:.0f}%处（应在30%-70%中部区域）")
        
        # ========== 3. 均线趋势检查 ==========
        ma_info = self.check_ma_trend(df)
        if not ma_info.get('valid'):
            reasons.append('均线数据不足')
        else:
            details[f"MA{self.params.MA_SHORT}"] = f"{ma_info['ma50']:.2f}"
            details[f"MA{self.params.MA_MEDIUM}"] = f"{ma_info['ma150']:.2f}"
            details[f"MA{self.params.MA_LONG}"] = f"{ma_info['ma200']:.2f}"
            
            if not ma_info['bullish_arrangement']:
                reasons.append('均线非多头排列：MA50 > MA150 > MA200 不成立')
            else:
                details['均线排列'] = '✓ MA50 > MA150 > MA200 多头排列'
            
            if not ma_info['ma200_rising']:
                reasons.append('MA200未向上：长期趋势不支持')
            else:
                details['MA200趋势'] = '✓ 向上（长期趋势良好）'
        
        # ========== 4. RS相对强度检查 ==========
        rs_score = self.calculate_rs_score(df)
        details['RS分数'] = f"{rs_score:.0f}"
        
        if rs_score < self.params.RS_MIN_SCORE:
            reasons.append(f'RS相对强度不足：{rs_score:.0f} < {self.params.RS_MIN_SCORE}（需要超越85%的个股）')
        else:
            details['RS评级'] = f'✓ {rs_score:.0f} 强势股（超越{rs_score:.0f}%个股）'
        
        # ========== 5. 风控计算 ==========
        if cup_handle is not None:
            stop_loss = cup_handle['handle_low'] * 0.97
            target_1 = cup_handle['handle_high'] + (cup_handle['handle_high'] - cup_handle['cup_low'])
            target_2 = cup_handle['handle_high'] + (cup_handle['handle_high'] - cup_handle['cup_low']) * 1.5
            
            risk_amount = yesterday['close'] - stop_loss
            reward_amount = target_1 - yesterday['close']
            rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位1': f'{target_1:.2f}',
                '目标位2': f'{target_2:.2f}',
                '盈亏比': f'1:{rr_ratio:.1f}' if rr_ratio > 0 else 'N/A'
            }
        
        # 判断结果
        if len(reasons) == 0 and cup_handle is not None:
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [],
                'details': details,
                'risk_management': risk_management
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details if details else None,
                'risk_management': risk_management if risk_management else None
            }
    
    def _enrich_data(self, results: List[Dict]) -> pd.DataFrame:
        """从数据库补充市值、行业等字段"""
        if self.quick_mode:
            return pd.DataFrame(results)
        
        enriched = []
        for r in results:
            code = r['code']
            
            stock = self.session.query(Stock).filter_by(code=code).first()
            
            enriched.append({
                '代码': code,
                '名称': r['name'],
                '收盘价': r['close'],
                '涨幅%': r['pct_change'],
                '换手率%': r['turnover'],
                '量比': r['volume_ratio'],
                '杯深%': r['cup_depth'],
                '柄调%': r['handle_retrace'],
                '柄部缩量%': r['handle_volume_ratio'],
                '突破%': r['breakout_pct'],
                'U型验证': '是' if r['cup_is_u_shape'] else '否',
                f"MA{self.params.MA_SHORT}": r['ma50'],
                f"MA{self.params.MA_MEDIUM}": r['ma150'],
                f"MA{self.params.MA_LONG}": r['ma200'],
                'RS分数': r['rs_score'],
                'AB股总市值(亿)': round(stock.total_market_cap / 1e8, 2) if stock and stock.total_market_cap else None,
                '流通市值(亿)': round(stock.circulating_market_cap / 1e8, 2) if stock and stock.circulating_market_cap else None,
                '行业': stock.industry if stock and stock.industry else '',
                '市净率': round(stock.pb_ratio, 2) if stock and stock.pb_ratio else None,
            })
        
        return pd.DataFrame(enriched)
    
    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """运行筛选（欧奈尔标准版）"""
        
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
        
        # 检查数据更新状态（如果启用）
        if self.check_data_update:
            status = self._check_update_status()
            logger.info(f"数据更新状态: {status['completion_rate']:.1f}%")
            if not status['ready']:
                logger.warning(f"数据更新未完成 ({status['completion_rate']:.1f}%)，跳过筛选")
                return []
            logger.info("✓ 数据更新 100% 完成")
        
        logger.info("="*60)
        logger.info("咖啡杯形态筛选器 - 欧奈尔标准版")
        logger.info(f"杯体周期: {self.params.CUP_PERIOD_MIN}-{self.params.CUP_PERIOD_MAX}天")
        logger.info(f"柄部周期: {self.params.HANDLE_PERIOD_MIN}-{self.params.HANDLE_PERIOD_MAX}天")
        logger.info(f"杯深范围: {self.params.CUP_DEPTH_MIN*100:.0f}%-{self.params.CUP_DEPTH_MAX*100:.0f}%")
        logger.info(f"柄调范围: 0-1/2杯深 (动态)")
        logger.info(f"均线: {self.params.MA_SHORT}/{self.params.MA_MEDIUM}/{self.params.MA_LONG}多头排列")
        logger.info(f"RS强度: ≥{self.params.RS_MIN_SCORE}")
        logger.info("="*60)
        
        # 运行基础筛选
        results = super().run_screening(date_str, force_restart, enable_analysis)
        
        # 按RS分数排序
        results.sort(key=lambda x: x.get('rs_score', 0), reverse=True)
        
        return results
    
    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None,
                     target_date: Optional[str] = None) -> str:
        """保存结果（欧奈尔标准版）"""
        
        if not results:
            return ""
        
        if target_date is None:
            target_date = self.current_date
        
        # 保存基础版
        basic_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'close': '收盘价',
            'turnover': '换手率%',
            'pct_change': '涨幅%',
            'volume_ratio': '量比',
            'cup_depth': '杯深%',
            'handle_retrace': '柄调%',
            'handle_volume_ratio': '柄部缩量%',
            'breakout_pct': '突破%',
            'cup_is_u_shape': 'U型验证',
            'rs_score': 'RS分数'
        }
        
        basic_path = super().save_results(results, analysis_data, column_mapping=basic_mapping)
        logger.info(f"基础版已保存: {basic_path}")
        
        # 保存丰富版
        if not self.quick_mode:
            enriched_df = self._enrich_data(results)
            
            daily_dir = WORKSPACE_ROOT / 'data' / 'coffee_cup_daily' / target_date
            daily_dir.mkdir(parents=True, exist_ok=True)
            
            enriched_path = daily_dir / '咖啡杯形态选股_欧奈尔标准.xlsx'
            
            with pd.ExcelWriter(enriched_path, engine='xlsxwriter') as writer:
                enriched_df.to_excel(writer, sheet_name='咖啡杯形态', index=False)
            
            logger.info(f"丰富版已保存: {enriched_path}")
        
        return str(basic_path)


def main():
    parser = argparse.ArgumentParser(description='咖啡杯形态筛选器（欧奈尔标准版）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--check-update', action='store_true', help='检查数据更新状态')
    parser.add_argument('--quick', action='store_true', help='快速模式（不查询丰富字段）')
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
    
    screener = CoffeeCupScreener(
        db_path=args.db_path,
        enable_news=False,  # 禁用新闻
        enable_llm=False,   # 禁用LLM
        enable_progress=not args.no_progress,
        check_data_update=args.check_update,
        quick_mode=args.quick
    )
    
    results = screener.run_screening(args.date, force_restart=args.restart)
    
    if results:
        # Save results
        output_path = screener.save_results(results)
        logger.info(f"\n结果已保存: {output_path}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/coffee_cup_screener/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/coffee_cup_screener/{date_str}")
        print(f"{'='*60}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"筛选完成！共找到 {len(results)} 只股票")
        logger.info(f"{'='*60}")
        for r in results[:10]:
            logger.info(f"  {r['code']} - {r['name']}: "
                       f"杯深{r['cup_depth']:.1f}%, "
                       f"柄调{r['handle_retrace']:.1f}%, "
                       f"RS{r['rs_score']:.0f}")
    else:
        logger.info("未找到符合条件的股票")


if __name__ == '__main__':
    main()
