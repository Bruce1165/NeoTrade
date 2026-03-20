#!/usr/bin/env python3
"""
运行所有股票筛选器 - Run All Screeners

一键运行所有6个筛选器：
1. 咖啡杯形态 (coffee_cup)
2. 涨停金凤凰 (jin_feng_huang)
3. 涨停银凤凰 (yin_feng_huang)
4. 涨停试盘线 (shi_pan_xian)
5. 二板回调 (er_ban_hui_tiao)
6. 涨停倍量阴 (zhang_ting_bei_liang_yin)
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import logging
import argparse
from datetime import datetime
import time

# 导入所有筛选器
from coffee_cup_screener import CoffeeCupScreener
from jin_feng_huang_screener import JinFengHuangScreener
from yin_feng_huang_screener import YinFengHuangScreener
from shi_pan_xian_screener import ShiPanXianScreener
from er_ban_hui_tiao_screener import ErBanHuiTiaoScreener
from zhang_ting_bei_liang_yin_screener import ZhangTingBeiLiangYinScreener

# 导入图表生成器
from plot_coffee_cup_charts import CoffeeCupChartGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 筛选器配置
SCREENERS = {
    'coffee_cup': {
        'class': CoffeeCupScreener,
        'name': '咖啡杯形态',
        'has_charts': True,
    },
    'jin_feng_huang': {
        'class': JinFengHuangScreener,
        'name': '涨停金凤凰',
        'has_charts': False,
    },
    'yin_feng_huang': {
        'class': YinFengHuangScreener,
        'name': '涨停银凤凰',
        'has_charts': False,
    },
    'shi_pan_xian': {
        'class': ShiPanXianScreener,
        'name': '涨停试盘线',
        'has_charts': False,
    },
    'er_ban_hui_tiao': {
        'class': ErBanHuiTiaoScreener,
        'name': '二板回调',
        'has_charts': False,
    },
    'zhang_ting_bei_liang_yin': {
        'class': ZhangTingBeiLiangYinScreener,
        'name': '涨停倍量阴',
        'has_charts': False,
    },
}


def run_screener(screener_key: str, date_str: str = None, 
                 enable_news: bool = True, enable_llm: bool = True,
                 enable_progress: bool = True, force_restart: bool = False,
                 db_path: str = "data/stock_data.db") -> dict:
    """
    运行单个筛选器
    
    Args:
        screener_key: 筛选器键名
        date_str: 日期字符串
        enable_news: 启用新闻抓取
        enable_llm: 启用LLM分析
        enable_progress: 启用进度跟踪
        force_restart: 强制重新开始
        db_path: 数据库路径
    
    Returns:
        运行结果统计
    """
    config = SCREENERS.get(screener_key)
    if not config:
        logger.error(f"Unknown screener: {screener_key}")
        return {'success': False, 'error': 'Unknown screener'}
    
    screener_name = config['name']
    screener_class = config['class']
    
    logger.info("="*80)
    logger.info(f"开始运行: {screener_name} ({screener_key})")
    logger.info("="*80)
    
    start_time = time.time()
    
    try:
        # 创建筛选器实例
        screener = screener_class(
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        
        # 运行筛选
        results, analysis_data = screener.run_screening(
            date_str=date_str,
            force_restart=force_restart,
            enable_analysis=enable_llm
        )
        
        # 保存结果
        output_path = screener.save_results(results, analysis_data)
        
        # 生成图表（仅咖啡杯）
        charts_generated = 0
        if config['has_charts'] and results:
            logger.info(f"Generating charts for {screener_key}...")
            chart_generator = CoffeeCupChartGenerator(db_path=db_path)
            generated = chart_generator.generate_charts_from_results(date_str, max_charts=50)
            charts_generated = len(generated)
        
        elapsed_time = time.time() - start_time
        
        result_stats = {
            'success': True,
            'screener': screener_key,
            'name': screener_name,
            'matches': len(results),
            'output_path': output_path,
            'charts_generated': charts_generated,
            'elapsed_time': round(elapsed_time, 2)
        }
        
        logger.info(f"{screener_name} 完成: 找到 {len(results)} 只股票, "
                   f"耗时 {elapsed_time:.1f}秒")
        
        return result_stats
        
    except Exception as e:
        logger.error(f"Error running {screener_key}: {e}")
        return {
            'success': False,
            'screener': screener_key,
            'name': screener_name,
            'error': str(e)
        }


def run_all_screeners(date_str: str = None,
                      enable_news: bool = True,
                      enable_llm: bool = True,
                      enable_progress: bool = True,
                      force_restart: bool = False,
                      db_path: str = "data/stock_data.db",
                      screeners: list = None) -> list:
    """
    运行所有筛选器
    
    Args:
        date_str: 日期字符串
        enable_news: 启用新闻抓取
        enable_llm: 启用LLM分析
        enable_progress: 启用进度跟踪
        force_restart: 强制重新开始
        db_path: 数据库路径
        screeners: 指定运行的筛选器列表，None表示全部
    
    Returns:
        所有筛选器的运行结果
    """
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    logger.info("="*80)
    logger.info("开始运行所有股票筛选器")
    logger.info(f"日期: {date_str}")
    logger.info(f"新闻抓取: {'启用' if enable_news else '禁用'}")
    logger.info(f"LLM分析: {'启用' if enable_llm else '禁用'}")
    logger.info(f"进度跟踪: {'启用' if enable_progress else '禁用'}")
    logger.info("="*80)
    
    total_start_time = time.time()
    
    results = []
    
    # 确定要运行的筛选器
    screener_keys = screeners if screeners else list(SCREENERS.keys())
    
    for screener_key in screener_keys:
        if screener_key not in SCREENERS:
            logger.warning(f"Unknown screener: {screener_key}, skipping")
            continue
        
        result = run_screener(
            screener_key=screener_key,
            date_str=date_str,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress,
            force_restart=force_restart,
            db_path=db_path
        )
        
        results.append(result)
        
        # 添加短暂延迟避免资源冲突
        time.sleep(1)
    
    total_elapsed = time.time() - total_start_time
    
    # 打印汇总
    logger.info("="*80)
    logger.info("所有筛选器运行完成")
    logger.info("="*80)
    
    total_matches = sum(r.get('matches', 0) for r in results if r.get('success'))
    success_count = sum(1 for r in results if r.get('success'))
    
    logger.info(f"成功: {success_count}/{len(results)}")
    logger.info(f"总匹配: {total_matches} 只股票")
    logger.info(f"总耗时: {total_elapsed:.1f}秒")
    
    for result in results:
        status = "✓" if result.get('success') else "✗"
        name = result.get('name', result.get('screener', 'Unknown'))
        matches = result.get('matches', 0)
        elapsed = result.get('elapsed_time', 0)
        logger.info(f"  {status} {name}: {matches}只 ({elapsed:.1f}s)")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='运行所有股票筛选器')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--screeners', type=str, nargs='+', 
                       choices=list(SCREENERS.keys()) + ['all'],
                       default=['all'],
                       help='要运行的筛选器')
    parser.add_argument('--no-news', action='store_true', help='禁用新闻抓取')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM分析')
    parser.add_argument('--no-progress', action='store_true', help='禁用进度跟踪')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')
    
    args = parser.parse_args()
    
    # 确定要运行的筛选器
    if 'all' in args.screeners:
        screeners_to_run = None  # 运行全部
    else:
        screeners_to_run = args.screeners
    
    # 运行筛选器
    results = run_all_screeners(
        date_str=args.date,
        enable_news=not args.no_news,
        enable_llm=not args.no_llm,
        enable_progress=not args.no_progress,
        force_restart=args.restart,
        db_path=args.db_path,
        screeners=screeners_to_run
    )
    
    # 打印最终结果
    print("\n" + "="*80)
    print("运行结果汇总:")
    print("="*80)
    
    for result in results:
        if result.get('success'):
            print(f"✓ {result['name']}: {result['matches']}只股票")
            print(f"  输出: {result['output_path']}")
        else:
            print(f"✗ {result.get('name', result.get('screener'))}: 失败")
            print(f"  错误: {result.get('error', 'Unknown error')}")


if __name__ == '__main__':
    main()
