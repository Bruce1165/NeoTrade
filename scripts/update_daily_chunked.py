#!/usr/bin/env python3
"""
每日数据更新脚本 - 分块版本
确保数据完整性，支持断点续传
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import json
import os
from datetime import datetime, timedelta
from database import init_db, get_session, Stock, DailyPrice
from fetcher_baostock import BaostockFetcher
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "/Users/mac/.openclaw/workspace-neo/data/stock_data.db"
PROGRESS_FILE = "/Users/mac/.openclaw/workspace-neo/data/daily_update_progress.json"
CHUNK_SIZE = 200  # 每200只保存一次进度

class DailyUpdater:
    """每日数据更新器（分块版本）"""
    
    def __init__(self):
        self.engine = init_db()
        self.session = get_session(self.engine)
        self.fetcher = BaostockFetcher()
        self.progress = self.load_progress()
    
    def load_progress(self):
        """加载更新进度"""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            'completed': [],
            'last_update': None,
            'last_chunk': 0
        }
    
    def save_progress(self):
        """保存更新进度"""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def update_stock_list(self):
        """更新股票基础信息（获取新上市、合并、退市等变更）"""
        logger.info("更新股票基础信息...")
        
        if not self.fetcher.login():
            logger.error("登录失败，无法更新股票列表")
            return False
        
        try:
            stocks = self.fetcher.get_stock_list()
            
            # 获取数据库中现有的股票代码
            existing_codes = {s.code for s in self.session.query(Stock).all()}
            new_codes = set()
            
            for stock_info in stocks:
                code = stock_info['code'].replace('sh.', '').replace('sz.', '')
                name = stock_info['name']
                
                # 跳过北交所、指数、ST、退市股
                if code.startswith('8') or code.startswith('4'):  # 北交所
                    continue
                if code.startswith('399') or code.startswith('000'):  # 指数
                    continue
                if '退' in name or 'ST' in name:  # ST/退市
                    continue
                
                new_codes.add(code)
                
                # 检查是否已存在
                existing = self.session.query(Stock).filter_by(code=code).first()
                if existing:
                    # 更新名称（可能变更）
                    if existing.name != name:
                        logger.info(f"股票更名: {code} {existing.name} -> {name}")
                        existing.name = name
                else:
                    # 新增股票
                    logger.info(f"新增股票: {code} {name}")
                    # 获取上市日期，处理空值
                    list_date_str = stock_info.get('list_date', '')
                    list_date = None
                    if list_date_str and list_date_str.strip():
                        try:
                            list_date = datetime.strptime(list_date_str.strip(), '%Y-%m-%d').date()
                        except ValueError:
                            list_date = None
                    
                    new_stock = Stock(
                        code=code,
                        name=name,
                        industry=stock_info.get('industry', '') or '',
                        area=stock_info.get('area', '') or '',
                        list_date=list_date
                    )
                    self.session.add(new_stock)
            
            # 检查是否有股票退市（在数据库中但不在新列表中）
            removed_codes = existing_codes - new_codes
            for code in removed_codes:
                stock = self.session.query(Stock).filter_by(code=code).first()
                if stock and '退' not in stock.name:
                    logger.info(f"股票可能退市或合并: {code} {stock.name}")
                    # 标记为退市（可选）
                    # stock.name = stock.name + '(退市)'
            
            self.session.commit()
            logger.info(f"股票列表更新完成: 新增 {len(new_codes - existing_codes)} 只")
            return True
            
        finally:
            self.fetcher.logout()
    
    def get_stocks_to_update(self):
        """获取需要更新的股票列表（排除北交所、ST、退市、指数）"""
        stocks = self.session.query(Stock).all()
        # 排除已完成的、北交所、ST、退市、指数
        remaining = [
            s for s in stocks 
            if s.code not in self.progress['completed']
            and not s.code.startswith('8')    # 排除北交所
            and not s.code.startswith('4')    # 排除北交所
            and not s.code.startswith('399')  # 排除指数
            and not s.code.startswith('000')  # 排除指数
            and '退' not in (s.name or '')     # 排除退市股
            and 'ST' not in (s.name or '')     # 排除ST股
        ]
        return remaining
    
    def get_total_active_stocks(self):
        """获取活跃股票总数（排除北交所、ST、退市、指数）"""
        stocks = self.session.query(Stock).all()
        active = [
            s for s in stocks
            if not s.code.startswith('8')
            and not s.code.startswith('4')
            and not s.code.startswith('399')
            and not s.code.startswith('000')
            and '退' not in (s.name or '')
            and 'ST' not in (s.name or '')
        ]
        return len(active)
    
    def update_chunk(self, stocks_chunk, target_date):
        """更新一个chunk的股票数据"""
        if not self.fetcher.login():
            logger.error("登录失败")
            return False
        
        updated = 0
        try:
            for stock in stocks_chunk:
                code = f"sh.{stock.code}" if stock.code.startswith('6') else f"sz.{stock.code}"
                
                try:
                    # 获取最近5天数据（确保包含昨天）
                    end_date = target_date
                    start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
                    
                    df = self.fetcher.get_daily_data(code, start_date, end_date)
                    
                    # 检查是否登录失效
                    if '用户未登录' in str(df):
                        logger.warning(f"登录失效，重新登录...")
                        self.fetcher.logout()
                        if not self.fetcher.login():
                            logger.error("重新登录失败")
                            return False
                        df = self.fetcher.get_daily_data(code, start_date, end_date)
                    
                    if not df.empty:
                        for _, row in df.iterrows():
                            trade_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                            
                            # 检查是否已存在
                            existing = self.session.query(DailyPrice).filter_by(
                                code=stock.code,
                                trade_date=trade_date
                            ).first()
                            
                            if existing:
                                # 更新现有数据
                                existing.open = row.get('open')
                                existing.high = row.get('high')
                                existing.low = row.get('low')
                                existing.close = row.get('close')
                                existing.volume = row.get('volume')
                                existing.amount = row.get('amount')
                                existing.turnover = row.get('turn')
                                existing.preclose = row.get('preclose')
                                existing.pct_change = row.get('pctChg')
                            else:
                                # 新增
                                new_price = DailyPrice(
                                    code=stock.code,
                                    trade_date=trade_date,
                                    open=row.get('open'),
                                    high=row.get('high'),
                                    low=row.get('low'),
                                    close=row.get('close'),
                                    volume=row.get('volume'),
                                    amount=row.get('amount'),
                                    turnover=row.get('turn'),
                                    preclose=row.get('preclose'),
                                    pct_change=row.get('pctChg')
                                )
                                self.session.add(new_price)
                        
                        updated += 1
                        self.progress['completed'].append(stock.code)
                
                except Exception as e:
                    logger.error(f"更新 {stock.code} 失败: {e}")
                    continue
            
            self.session.commit()
            logger.info(f"Chunk 完成: 更新 {updated} 只股票")
            return True
            
        finally:
            self.fetcher.logout()
    
    def run_update(self, target_date=None):
        """运行每日更新 - 必须100%完成"""
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info("="*60)
        logger.info(f"开始每日数据更新: {target_date}")
        logger.info("="*60)
        
        # 第一步：更新股票列表（获取新上市、合并、退市等变更）
        self.update_stock_list()
        
        # 获取活跃股票总数（排除退市、ST、指数）
        total_active = self.get_total_active_stocks()
        
        # 如果是新任务或上次已完成，重置进度
        if self.progress.get('status') == 'completed' or self.progress.get('target_date') != target_date:
            logger.info("新任务或日期变更，重置进度")
            self.progress = {
                'completed': [],
                'last_update': None,
                'last_chunk': 0,
                'planned': total_active,
                'target_date': target_date,
                'status': 'running',
                'completion_rate': 0.0
            }
            self.save_progress()
        
        # 记录计划更新数量
        if 'planned' not in self.progress or self.progress['planned'] == 0:
            self.progress['planned'] = total_active
        if 'target_date' not in self.progress:
            self.progress['target_date'] = target_date
        self.progress['status'] = 'running'
        self.save_progress()
        
        logger.info(f"计划更新: {self.progress['planned']} 只活跃股票（已排除退市/ST/指数）")
        
        # 获取所有活跃股票
        all_active_stocks = self.session.query(Stock).all()
        all_active_stocks = [
            s for s in all_active_stocks
            if not s.code.startswith('399')
            and not s.code.startswith('000')
            and '退' not in (s.name or '')
            and 'ST' not in (s.name or '')
        ]
        
        # 获取未完成的股票
        stocks = [s for s in all_active_stocks if s.code not in self.progress['completed']]
        remaining = len(stocks)
        completed = len(self.progress['completed'])
        
        logger.info(f"已完成: {completed} 只，剩余: {remaining} 只")
        
        if remaining == 0:
            logger.info("所有股票已更新完成 (100%)")
            self.progress['status'] = 'completed'
            self.progress['completion_rate'] = 100.0
            self.save_progress()
            return True
        
        # 分块处理
        total_chunks = (remaining + CHUNK_SIZE - 1) // CHUNK_SIZE
        # 如果剩余股票数量变化导致 chunk 计算不一致，重置 start_chunk
        start_chunk = 0  # 总是从0开始，因为 stocks 列表已经是剩余股票的列表
        
        for chunk_idx in range(start_chunk, total_chunks):
            start = chunk_idx * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, remaining)
            chunk = stocks[start:end]
            
            logger.info(f"\n{'='*60}")
            logger.info(f"处理 Chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} 只股票)")
            logger.info(f"{'='*60}")
            
            success = self.update_chunk(chunk, target_date)
            
            if success:
                self.progress['last_chunk'] = chunk_idx + 1
                self.progress['last_update'] = datetime.now().isoformat()
                self.save_progress()
                current_completed = len(self.progress['completed'])
                planned = self.progress.get('planned', 4663)
                rate = (current_completed / planned) * 100
                logger.info(f"进度: {current_completed}/{planned} ({rate:.1f}%)")
            else:
                logger.error("Chunk 更新失败，任务中断")
                self.progress['status'] = 'failed'
                self.save_progress()
                return False
        
        # 最终检查
        final_completed = len(self.progress['completed'])
        planned = self.progress.get('planned', 4663)
        final_rate = (final_completed / planned) * 100
        
        logger.info("\n" + "="*60)
        logger.info(f"更新结束: {final_completed}/{planned} ({final_rate:.1f}%)")
        logger.info("="*60)
        
        if final_completed >= planned:
            self.progress['status'] = 'completed'
            self.progress['completion_rate'] = 100.0
            self.save_progress()
            logger.info("✓ 任务完成 (100%)")
            # 重置进度（下次全新更新）
            self.progress = {'completed': [], 'last_update': None, 'last_chunk': 0, 'planned': 0}
            self.save_progress()
            return True
        else:
            self.progress['status'] = 'incomplete'
            self.progress['completion_rate'] = final_rate
            self.save_progress()
            logger.error(f"✗ 任务未完成 ({final_rate:.1f}%)，将在下次继续")
            return False

def main():
    updater = DailyUpdater()
    # 更新昨天数据
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    updater.run_update(yesterday)

if __name__ == '__main__':
    main()
