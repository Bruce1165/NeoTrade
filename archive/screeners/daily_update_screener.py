#!/usr/bin/env python3
"""
Daily Data Update Task - 每日数据更新任务（修复版）
使用小批量、多次、断点续传方式
"""

import os
import sys
import json
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Baostock import
import baostock as bs

DB_PATH = WORKSPACE_ROOT / 'data' / 'stock_data.db'
PROGRESS_FILE = WORKSPACE_ROOT / 'data' / 'daily_update_progress_v2.json'
BATCH_SIZE = 100  # 每批100只


class DailyUpdateScreener:
    """每日数据更新任务"""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.progress = self._load_progress()
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('daily_update_task')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _load_progress(self):
        """加载更新进度 - 使用Set结构去重"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                data = json.load(f)
                return {
                    'completed': list(set(data.get('completed', []))),  # 去重
                    'failed': data.get('failed', {}),  # 改为dict记录失败次数
                    'target_date': data.get('target_date'),
                    'status': data.get('status', 'idle'),
                    'last_updated': data.get('last_updated', datetime.now().isoformat())
                }
        return {
            'completed': [], 
            'failed': {},  # dict: {code: fail_count}
            'target_date': None, 
            'status': 'idle',
            'last_updated': datetime.now().isoformat()
        }
    
    def _save_progress(self):
        """保存更新进度 - 确保Set转换为List，更新时间戳"""
        save_data = {
            'completed': sorted(list(set(self.progress['completed']))),  # 去重并排序
            'failed': self.progress.get('failed', {}),
            'target_date': self.progress.get('target_date'),
            'status': self.progress.get('status', 'idle'),
            'last_updated': datetime.now().isoformat()
        }
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(save_data, f, indent=2)
    
    def _get_all_stocks(self):
        """获取所有股票代码"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT code FROM stocks')
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def _get_existing_data(self, target_date):
        """获取已有数据的股票"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT code FROM daily_prices WHERE trade_date = ?', (target_date,))
        existing = {row[0] for row in cursor.fetchall()}
        conn.close()
        return existing
    
    def run_screening(self, target_date: str = None):
        """
        运行每日数据更新
        
        Args:
            target_date: 目标日期，默认昨天
        """
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 检查是否为当天（无数据）
        today = datetime.now().strftime('%Y-%m-%d')
        if target_date == today:
            self.logger.warning(f"⚠️  无法下载当天数据 ({today}) - 市场尚未收盘")
            return [{'code': 'STATUS', 'name': 'No Data', 'message': f'无法下载当天数据 ({today})，市场尚未收盘'}]
        
        self.logger.info("="*60)
        self.logger.info(f"每日数据更新: {target_date}")
        self.logger.info("="*60)
        
        # 获取所有股票
        all_stocks = self._get_all_stocks()
        self.logger.info(f"数据库股票总数: {len(all_stocks)}")
        
        # 获取已有数据
        existing = self._get_existing_data(target_date)
        self.logger.info(f"已有数据: {len(existing)} 只")
        
        # 检查是否需要重置进度（新日期）
        if self.progress.get('target_date') != target_date:
            self.logger.info(f"新日期 {target_date}，重置进度")
            self.progress = {
                'completed': list(existing),  # 已有数据视为已完成
                'failed': {},  # 重置为空dict
                'target_date': target_date,
                'status': 'running',
                'last_updated': datetime.now().isoformat()
            }
            self._save_progress()
        
        # 需要下载的股票
        stocks_to_download = [s for s in all_stocks if s not in self.progress['completed']]
        completed_count = len(self.progress['completed'])
        
        self.logger.info(f"已完成: {completed_count} 只")
        self.logger.info(f"待下载: {len(stocks_to_download)} 只")
        
        if not stocks_to_download:
            self.logger.info("✅ 所有数据已下载完成！")
            self.progress['status'] = 'completed'
            self._save_progress()
            return [{
                'code': 'STATUS',
                'name': 'Completed',
                'message': f'{target_date} 数据更新完成',
                'completion_rate': 100.0,
                'completed': completed_count,
                'total': len(all_stocks)
            }]
        
        # 登录 Baostock
        lg = bs.login()
        if lg.error_code != '0':
            self.logger.error(f"登录失败: {lg.error_msg}")
            return [{'code': 'STATUS', 'name': 'Error', 'message': '登录失败'}]
        
        self.logger.info(f"登录成功: {lg.error_msg}")
        
        try:
            # 只处理一批
            batch = stocks_to_download[:BATCH_SIZE]
            self.logger.info(f"\n处理批次: {len(batch)} 只股票")
            
            batch_data = []
            failed_in_batch = []
            
            for i, code in enumerate(batch):
                try:
                    # 添加交易所前缀
                    if code.startswith('6'):
                        bs_code = f"sh.{code}"
                    else:
                        bs_code = f"sz.{code}"
                    
                    rs = bs.query_history_k_data_plus(
                        code=bs_code,
                        fields='date,code,open,high,low,close,preclose,volume,amount,turn,pctChg',
                        start_date=target_date,
                        end_date=target_date,
                        frequency='d',
                        adjustflag='2'
                    )
                    
                    data_found = False
                    while (rs.error_code == '0') & rs.next():
                        row = rs.get_row_data()
                        batch_data.append({
                            'trade_date': row[0],
                            'code': code,
                            'open': float(row[2]) if row[2] else None,
                            'high': float(row[3]) if row[3] else None,
                            'low': float(row[4]) if row[4] else None,
                            'close': float(row[5]) if row[5] else None,
                            'preclose': float(row[6]) if row[6] else None,
                            'volume': int(float(row[7])) if row[7] else None,
                            'amount': float(row[8]) if row[8] else None,
                            'turnover': float(row[9]) if row[9] else None,
                            'pct_change': float(row[10]) if row[10] else None
                        })
                        data_found = True
                    
                    if data_found:
                        if code not in self.progress['completed']:
                            self.progress['completed'].append(code)
                        # 成功后从失败记录中移除
                        if code in self.progress['failed']:
                            del self.progress['failed'][code]
                    else:
                        # 无数据可能是退市股
                        failed_in_batch.append(code)
                        # 记录失败次数
                        self.progress['failed'][code] = self.progress['failed'].get(code, 0) + 1
                    
                    if (i + 1) % 20 == 0:
                        self.logger.info(f"  进度: {i+1}/{len(batch)}, 成功: {len(batch_data)}, 失败: {len(failed_in_batch)}")
                    
                    time.sleep(0.03)  # 小延迟
                    
                except Exception as e:
                    self.logger.warning(f"  {code} 错误: {e}")
                    failed_in_batch.append(code)
                    # 记录失败次数
                    self.progress['failed'][code] = self.progress['failed'].get(code, 0) + 1
            
            # 保存进度
            self._save_progress()
            
            # 插入数据库 - 使用INSERT OR REPLACE确保幂等性
            if batch_data:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                inserted = 0
                replaced = 0
                
                for record in batch_data:
                    try:
                        cursor.execute('''
                            INSERT INTO daily_prices 
                            (trade_date, code, open, high, low, close, preclose, volume, amount, turnover, pct_change, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (
                            record['trade_date'], record['code'], record['open'], record['high'],
                            record['low'], record['close'], record['preclose'], record['volume'],
                            record['amount'], record['turnover'], record['pct_change']
                        ))
                        inserted += 1
                    except sqlite3.IntegrityError:
                        # 记录已存在，使用REPLACE更新
                        cursor.execute('''
                            REPLACE INTO daily_prices 
                            (trade_date, code, open, high, low, close, preclose, volume, amount, turnover, pct_change, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ''', (
                            record['trade_date'], record['code'], record['open'], record['high'],
                            record['low'], record['close'], record['preclose'], record['volume'],
                            record['amount'], record['turnover'], record['pct_change']
                        ))
                        replaced += 1
                
                conn.commit()
                conn.close()
                self.logger.info(f"\n✅ 成功插入 {inserted} 条记录, 更新 {replaced} 条记录")
            
            # 识别退市股票（连续多次失败的）
            # 如果某只股票失败超过3次，可能是退市股，标记为完成但记录为退市
            delisted = [c for c, count in self.progress['failed'].items() if count >= 3]
            
            # 将退市股票加入完成列表
            for code in delisted:
                if code not in self.progress['completed']:
                    self.progress['completed'].append(code)
            
            # 重新计算完成率
            completed_count = len(self.progress['completed'])
            total = len(all_stocks)
            rate = (completed_count / total) * 100
            remaining = total - completed_count
            
            self.logger.info(f"\n累计完成: {completed_count}/{total} ({rate:.1f}%)")
            self.logger.info(f"剩余: {remaining} 只")
            if delisted:
                self.logger.info(f"退市股: {len(delisted)} 只")
            
            if remaining == 0:
                self.progress['status'] = 'completed'
                self._save_progress()
                self.logger.info("✅ 全部完成！")
            else:
                self.logger.info(f"⏳ 还有 {remaining} 只待下载，再次运行继续...")
            
            return [{
                'code': 'STATUS',
                'name': 'Running' if remaining > 0 else 'Completed',
                'message': f'{target_date} 更新进度: {rate:.1f}%',
                'completion_rate': rate,
                'completed': completed_count,
                'total': total,
                'remaining': remaining
            }]
            
        finally:
            bs.logout()
            self.logger.info("已登出")


def run_all_screeners(trade_date: str):
    """
    数据下载完成后自动运行所有筛选器
    由Neo (PM)配置，数据更新后自动执行
    """
    import subprocess
    from datetime import datetime
    
    logger = logging.getLogger('daily_update_task')
    logger.info(f"\n{'='*60}")
    logger.info(f"🚀 数据下载完成，开始运行所有筛选器 - {trade_date}")
    logger.info(f"{'='*60}\n")
    
    # 11个筛选器列表
    screeners = [
        ('coffee_cup_screener', '咖啡杯形态'),
        ('jin_feng_huang_screener', '涨停金凤凰'),
        ('yin_feng_huang_screener', '涨停银凤凰'),
        ('shi_pan_xian_screener', '涨停试盘线'),
        ('er_ban_hui_tiao_screener', '二板回调'),
        ('zhang_ting_bei_liang_yin_screener', '涨停倍量阴'),
        ('breakout_20day_screener', '20日突破'),
        ('breakout_main_screener', '主升突破'),
        ('daily_hot_cold_screener', '每日热冷股'),
        ('shuang_shou_ban_screener', '双收板'),
        ('ashare_21_screener', 'A股21选股'),
    ]
    
    results_summary = []
    failed_screeners = []
    
    for screener_id, screener_name in screeners:
        script_path = WORKSPACE_ROOT / 'scripts' / f'{screener_id}.py'
        
        if not script_path.exists():
            logger.warning(f"⚠️  {screener_name}: 脚本不存在 - {script_path}")
            failed_screeners.append((screener_id, '脚本不存在'))
            continue
        
        logger.info(f"🏃 运行: {screener_name} ({screener_id})")
        
        try:
            # 运行筛选器
            result = subprocess.run(
                ['python3', str(script_path), '--date', trade_date],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {screener_name}: 成功")
                results_summary.append({
                    'id': screener_id,
                    'name': screener_name,
                    'status': 'success'
                })
            else:
                error_msg = result.stderr[-200:] if result.stderr else '未知错误'
                logger.error(f"❌ {screener_name}: 失败 - {error_msg}")
                failed_screeners.append((screener_id, error_msg))
                results_summary.append({
                    'id': screener_id,
                    'name': screener_name,
                    'status': 'failed',
                    'error': error_msg
                })
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️  {screener_name}: 超时 (>5分钟)")
            failed_screeners.append((screener_id, '超时'))
            results_summary.append({
                'id': screener_id,
                'name': screener_name,
                'status': 'timeout'
            })
        except Exception as e:
            logger.error(f"❌ {screener_name}: 异常 - {str(e)}")
            failed_screeners.append((screener_id, str(e)))
            results_summary.append({
                'id': screener_id,
                'name': screener_name,
                'status': 'error',
                'error': str(e)
            })
    
    # 生成运行报告
    success_count = sum(1 for r in results_summary if r['status'] == 'success')
    total_count = len(screeners)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 筛选器运行报告 - {trade_date}")
    logger.info(f"{'='*60}")
    logger.info(f"总计: {total_count} 个")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {len(failed_screeners)} 个")
    logger.info(f"成功率: {success_count/total_count*100:.1f}%")
    
    if failed_screeners:
        logger.warning(f"\n⚠️  失败的筛选器:")
        for screener_id, error in failed_screeners:
            logger.warning(f"  - {screener_id}: {error}")
    
    logger.info(f"{'='*60}\n")
    
    # 如果失败数量超过3个，需要告警
    if len(failed_screeners) >= 3:
        # 记录严重告警
        alert_file = WORKSPACE_ROOT / 'alerts' / f'screener_batch_{datetime.now().strftime("%Y-%m-%d")}.json'
        import json
        alert_data = {
            'timestamp': datetime.now().isoformat(),
            'level': 'CRITICAL',
            'message': f'{len(failed_screeners)}个筛选器运行失败',
            'date': trade_date,
            'failed': failed_screeners,
            'summary': results_summary
        }
        with open(alert_file, 'w') as f:
            json.dump(alert_data, f, indent=2, ensure_ascii=False)
        logger.error(f"🚨 严重告警已记录: {alert_file}")
    
    return results_summary


def main():
    """主函数 - 支持命令行参数指定日期"""
    import argparse
    
    parser = argparse.ArgumentParser(description='每日数据更新任务')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)，默认昨天')
    parser.add_argument('--loop', action='store_true', help='循环运行直到完成')
    args = parser.parse_args()
    
    screener = DailyUpdateScreener()
    
    # 确定目标日期
    if args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    if args.loop:
        # 循环运行直到完成
        max_iterations = 100
        for i in range(max_iterations):
            results = screener.run_screening(target_date)
            if results and results[0].get('name') == 'Completed':
                print(f"\n✅ {target_date} 数据更新完成！")
                break
            print(f"\n⏳ 第 {i+1} 轮完成，还有数据待下载，继续...\n")
            time.sleep(2)
        else:
            print(f"\n⚠️ 达到最大迭代次数 ({max_iterations})，停止")
        
        # 数据下载完成后，自动运行所有筛选器
        if results and results[0].get('name') == 'Completed':
            run_all_screeners(target_date)
    else:
        # 单次运行
        results = screener.run_screening(target_date)
        if results:
            print(f"\n结果: {results[0]}")
            
        # 如果完成了，运行所有筛选器
        if results and results[0].get('name') == 'Completed':
            run_all_screeners(target_date)


if __name__ == '__main__':
    main()
