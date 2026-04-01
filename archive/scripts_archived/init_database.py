#!/usr/bin/env python3
"""
初始化数据库并导入6个月历史数据
"""
import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

from update_daily import DataUpdater
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("="*60)
    logger.info("初始化全A股数据库")
    logger.info("="*60)
    
    updater = DataUpdater()
    
    # 执行全量更新（6个月历史）
    updater.full_update()
    
    logger.info("="*60)
    logger.info("初始化完成")
    logger.info("="*60)

if __name__ == '__main__':
    main()
