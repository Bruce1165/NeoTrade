#!/usr/bin/env python3
"""
Keyword Expander Screener - 关键词库扩充任务
定时任务：每天 16:00-17:00 运行
自动从网络获取热门概念，扩充关键词库
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from keyword_expander import KeywordExpander


class KeywordExpanderScreener:
    """
    Keyword Expander Screener - 关键词库扩充任务
    
    定时任务：每天 16:00-17:00 自动运行
    功能：
    - 从东方财富、同花顺抓取热门概念
    - 自动推理生成相关关键词
    - 扩充 keyword_library.json
    
    输出：扩充报告
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.expander = KeywordExpander()
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('keyword_expander_screener')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """
        运行关键词库扩充
        
        Args:
            trade_date: 日期，默认今天
            
        Returns:
            list: 扩充结果摘要
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info("="*60)
        self.logger.info(f"开始关键词库扩充: {trade_date}")
        self.logger.info("="*60)
        
        try:
            # 执行扩充（非预览模式，直接执行）
            report = self.expander.expand_library(dry_run=False)
            
            # 生成摘要
            results = []
            
            # 新概念
            for concept in report.get('new_concepts', []):
                results.append({
                    'code': 'NEW',
                    'name': concept['name'],
                    'keyword_count': len(concept['keywords']),
                    'source': concept.get('source', 'unknown'),
                    'type': 'new_concept'
                })
            
            # 扩展现有
            for name, keywords in report.get('expanded_keywords', {}).items():
                results.append({
                    'code': 'EXPAND',
                    'name': name,
                    'keyword_count': len(keywords),
                    'source': 'auto',
                    'type': 'expanded'
                })
            
            # 建议
            for suggestion in report.get('suggestions', []):
                results.append({
                    'code': 'SUGGEST',
                    'name': suggestion.get('name', ''),
                    'keyword_count': 0,
                    'source': 'manual_needed',
                    'type': 'suggestion'
                })
            
            total_new = len(report.get('new_concepts', []))
            total_expanded = len(report.get('expanded_keywords', {}))
            
            self.logger.info("="*60)
            self.logger.info(f"扩充完成: 新增 {total_new} 个概念, 扩充 {total_expanded} 个现有概念")
            self.logger.info("="*60)
            
            # 如果没有结果，返回状态
            if not results:
                results.append({
                    'code': 'STATUS',
                    'name': 'No Changes',
                    'keyword_count': 0,
                    'source': '-',
                    'type': 'status'
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"关键词库扩充失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise


def main():
    """主函数"""
    screener = KeywordExpanderScreener()
    results = screener.run_screening()
    
    print(f"\n关键词库扩充完成:")
    new_concepts = [r for r in results if r.get('type') == 'new_concept']
    expanded = [r for r in results if r.get('type') == 'expanded']
    
    print(f"  新增概念: {len(new_concepts)} 个")
    for c in new_concepts[:5]:
        print(f"    - {c['name']}: {c['keyword_count']} 个关键词")
    
    print(f"  扩展现有: {len(expanded)} 个")


if __name__ == '__main__':
    main()
