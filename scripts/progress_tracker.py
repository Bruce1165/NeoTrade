#!/usr/bin/env python3
"""
进度跟踪模块 - Progress Tracker

功能：
- 每个筛选器运行前保存进度到JSON
- 中断后能从上次位置继续
- 支持强制重新开始
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
import logging

logger = logging.getLogger(__name__)

# 进度文件目录
PROGRESS_DIR = "data/progress"


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, screener_name: str, progress_dir: str = PROGRESS_DIR):
        """
        初始化进度跟踪器
        
        Args:
            screener_name: 筛选器名称
            progress_dir: 进度文件保存目录
        """
        self.screener_name = screener_name
        self.progress_dir = progress_dir
        os.makedirs(progress_dir, exist_ok=True)
        
        self.progress_file = os.path.join(progress_dir, f"{screener_name}_progress.json")
        self.data = self._load_progress()
    
    def _load_progress(self) -> Dict:
        """加载进度文件"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading progress file: {e}")
        
        return self._create_default_progress()
    
    def _create_default_progress(self) -> Dict:
        """创建默认进度结构"""
        return {
            'screener_name': self.screener_name,
            'status': 'idle',  # idle, running, completed, error
            'start_time': None,
            'end_time': None,
            'last_updated': None,
            'total_stocks': 0,
            'processed_stocks': 0,
            'matched_stocks': 0,
            'current_batch': 0,
            'total_batches': 0,
            'processed_codes': [],  # 已处理的股票代码
            'matched_codes': [],    # 匹配的股票代码
            'last_processed_code': None,
            'error_message': None,
            'metadata': {}  # 额外元数据
        }
    
    def save(self):
        """保存进度"""
        try:
            self.data['last_updated'] = datetime.now().isoformat()
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Progress saved: {self.progress_file}")
        except Exception as e:
            logger.error(f"Error saving progress: {e}")
    
    def start(self, total_stocks: int, total_batches: int = 1, metadata: Optional[Dict] = None):
        """
        开始新的筛选任务
        
        Args:
            total_stocks: 总股票数量
            total_batches: 总批次
            metadata: 额外元数据
        """
        self.data = self._create_default_progress()
        self.data['status'] = 'running'
        self.data['start_time'] = datetime.now().isoformat()
        self.data['total_stocks'] = total_stocks
        self.data['total_batches'] = total_batches
        
        if metadata:
            self.data['metadata'] = metadata
        
        self.save()
        logger.info(f"Progress tracking started for {self.screener_name}: {total_stocks} stocks")
    
    def update(self, processed: int, matched: int, current_code: Optional[str] = None,
               batch: Optional[int] = None, extra_data: Optional[Dict] = None):
        """
        更新进度
        
        Args:
            processed: 已处理数量
            matched: 匹配数量
            current_code: 当前处理的股票代码
            batch: 当前批次
            extra_data: 额外数据
        """
        self.data['processed_stocks'] = processed
        self.data['matched_stocks'] = matched
        
        if current_code:
            self.data['last_processed_code'] = current_code
            if current_code not in self.data['processed_codes']:
                self.data['processed_codes'].append(current_code)
        
        if batch is not None:
            self.data['current_batch'] = batch
        
        if extra_data:
            self.data['metadata'].update(extra_data)
        
        self.save()
    
    def add_matched_code(self, code: str):
        """添加匹配的股票代码"""
        if code not in self.data['matched_codes']:
            self.data['matched_codes'].append(code)
            self.data['matched_stocks'] = len(self.data['matched_codes'])
            self.save()
    
    def complete(self, success: bool = True, error_message: Optional[str] = None):
        """完成任务"""
        self.data['status'] = 'completed' if success else 'error'
        self.data['end_time'] = datetime.now().isoformat()
        
        if error_message:
            self.data['error_message'] = error_message
        
        self.save()
        
        if success:
            logger.info(f"Progress tracking completed for {self.screener_name}")
        else:
            logger.error(f"Progress tracking failed for {self.screener_name}: {error_message}")
    
    def is_resumable(self) -> bool:
        """检查是否可以恢复"""
        if self.data['status'] != 'running':
            return False
        
        # 检查进度是否有效
        if self.data['processed_stocks'] >= self.data['total_stocks']:
            return False
        
        # 检查是否过期（超过24小时）
        if self.data['last_updated']:
            last_updated = datetime.fromisoformat(self.data['last_updated'])
            if datetime.now() - last_updated > timedelta(hours=24):
                logger.warning("Progress is older than 24 hours, starting fresh")
                return False
        
        return True
    
    def get_resume_point(self) -> Optional[str]:
        """获取恢复点（最后处理的股票代码）"""
        if not self.is_resumable():
            return None
        
        return self.data.get('last_processed_code')
    
    def get_processed_codes(self) -> List[str]:
        """获取已处理的股票代码列表"""
        return self.data.get('processed_codes', [])
    
    def get_matched_codes(self) -> List[str]:
        """获取匹配的股票代码列表"""
        return self.data.get('matched_codes', [])
    
    def reset(self):
        """重置进度"""
        self.data = self._create_default_progress()
        self.save()
        logger.info(f"Progress reset for {self.screener_name}")
    
    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        total = self.data.get('total_stocks', 0)
        processed = self.data.get('processed_stocks', 0)
        
        if total == 0:
            return 0.0
        
        return (processed / total) * 100
    
    def get_summary(self) -> Dict:
        """获取进度摘要"""
        return {
            'screener_name': self.screener_name,
            'status': self.data['status'],
            'progress_percentage': self.get_progress_percentage(),
            'processed_stocks': self.data['processed_stocks'],
            'total_stocks': self.data['total_stocks'],
            'matched_stocks': self.data['matched_stocks'],
            'start_time': self.data['start_time'],
            'last_updated': self.data['last_updated']
        }


def get_tracker(screener_name: str, progress_dir: str = PROGRESS_DIR) -> ProgressTracker:
    """便捷函数：获取进度跟踪器"""
    return ProgressTracker(screener_name, progress_dir)


def check_progress(screener_name: str, progress_dir: str = PROGRESS_DIR) -> Optional[Dict]:
    """便捷函数：检查进度"""
    tracker = ProgressTracker(screener_name, progress_dir)
    return tracker.get_summary()


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试进度跟踪器
    tracker = ProgressTracker('test_screener')
    
    # 开始任务
    tracker.start(total_stocks=1000, total_batches=10, metadata={'date': '2026-03-14'})
    
    # 模拟处理
    for i in range(100):
        tracker.update(
            processed=i+1,
            matched=i//10,
            current_code=f'600{i:03d}'
        )
    
    # 完成任务
    tracker.complete(success=True)
    
    # 打印摘要
    print("\nProgress Summary:")
    summary = tracker.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
