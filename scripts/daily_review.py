#!/usr/bin/env python3
"""
每日复盘主程序 - Neo量化研究体系 (AKShare版本)
整合情绪分析、板块分析，生成每日复盘报告
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

from akshare_fetcher import AKShareDataFetcher
from emotion_analyzer import EmotionAnalyzer
from sector_analyzer import SectorAnalyzer
from keyword_library import KeywordLibrary

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/mac/.openclaw/workspace-neo/logs/daily_review.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyReview:
    """每日复盘主类"""
    
    def __init__(self):
        """初始化"""
        self.fetcher = AKShareDataFetcher()
        self.emotion_analyzer = EmotionAnalyzer(self.fetcher)
        self.sector_analyzer = SectorAnalyzer(self.fetcher)
        self.keyword_library = KeywordLibrary()
        
        self.data_dir = Path('/Users/mac/.openclaw/workspace-neo/data')
        self.report_dir = self.data_dir / 'reports'
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self, trade_date: str = None) -> dict:
        """
        执行每日复盘
        
        Args:
            trade_date: 交易日期 (YYYYMMDD)，默认为最新交易日
            
        Returns:
            复盘结果字典
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"="*60)
        logger.info(f"开始执行 {trade_date} 每日复盘")
        logger.info(f"="*60)
        
        results = {
            'trade_date': trade_date,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        try:
            # 1. 情绪周期分析
            logger.info("[1/5] 情绪周期分析...")
            emotion_report = self.emotion_analyzer.generate_daily_report(trade_date)
            results['emotion'] = emotion_report.to_dict('records')[0]
            
            # 2. 涨幅分布分析
            logger.info("[2/5] 涨幅分布分析...")
            top_sectors = self.sector_analyzer.analyze_top_sectors(trade_date)
            results['top_sectors'] = top_sectors.to_dict('records')
            
            # 3. 成交额集中度分析
            logger.info("[3/5] 成交额集中度分析...")
            concentration = self.sector_analyzer.analyze_sector_concentration(trade_date)
            results['concentration'] = concentration.to_dict('records')
            
            # 4. 放量个股分析
            logger.info("[4/5] 放量个股分析...")
            volume_surge = self.sector_analyzer.analyze_volume_surge(trade_date)
            if not volume_surge.empty:
                results['volume_surge'] = volume_surge.head(20).to_dict('records')
            else:
                results['volume_surge'] = []
            
            # 5. 涨停关键词分析
            logger.info("[5/5] 涨停关键词分析...")
            
            # 获取涨停股
            import akshare as ak
            limit_df = ak.stock_zt_pool_em(date=trade_date)
            
            if not limit_df.empty:
                # 提取每只股票的关键词
                stocks_data = []
                for _, row in limit_df.iterrows():
                    code = row['代码']
                    name = row['名称']
                    ts_code = code + ('.SH' if code.startswith('6') else '.SZ')
                    limit_days = row['连板数']
                    industry = row.get('所属行业', '')
                    
                    # 使用关键词库提取
                    keywords = self.keyword_library.extract_keywords(name, ts_code, industry)
                    
                    stocks_data.append({
                        'ts_code': ts_code,
                        'name': name,
                        'limit_days': limit_days,
                        'keywords': keywords,
                    })
                
                # 更新关键词库统计
                self.keyword_library.update_stats(trade_date, stocks_data)
                
                # 生成关键词报告
                keyword_report = self.keyword_library.export_report(trade_date)
                
                # 按关键词分组股票
                keyword_groups = {}
                for kw, _ in keyword_report['hot_keywords'][:10]:
                    related = self.keyword_library.get_related_stocks(kw)
                    # 只保留今日涨停的
                    today_stocks = [s for s in related if trade_date in s.get('dates', [])]
                    if today_stocks:
                        keyword_groups[kw] = today_stocks[:5]  # 每关键词最多5只
                
                results['keywords'] = {
                    'hot_keywords': keyword_report['hot_keywords'][:15],
                    'category_stats': keyword_report['category_stats'],
                    'keyword_groups': keyword_groups,
                }
            
            # 保存报告
            self._save_report(results)
            
            logger.info(f"="*60)
            logger.info(f"复盘完成！报告已保存")
            logger.info(f"="*60)
            
            return results
            
        except Exception as e:
            logger.error(f"复盘失败: {e}")
            raise
    
    def _save_report(self, results: dict):
        """保存复盘报告"""
        trade_date = results['trade_date']
        
        # 保存为JSON
        import json
        report_file = self.report_dir / f'daily_review_{trade_date}.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已保存: {report_file}")
    
    def print_report(self, results: dict):
        """打印复盘报告"""
        print("\n" + "="*70)
        print(f"每日复盘报告 - {results['trade_date']}")
        print(f"生成时间: {results['timestamp']}")
        print("="*70)
        
        # 情绪周期
        emotion = results.get('emotion', {})
        print(f"\n【情绪周期】")
        print(f"  涨停数量: {emotion.get('涨停数量', 'N/A')}")
        print(f"  溢价率: {emotion.get('溢价率(%)', 'N/A')}%")
        print(f"  连板数量: {emotion.get('连板数量', 'N/A')}")
        print(f"  空间高度: {emotion.get('空间高度', 'N/A')}板")
        print(f"  情绪阶段: {emotion.get('情绪阶段', 'N/A')}")
        
        # 涨幅分布
        print(f"\n【涨幅前400分布】")
        for item in results.get('top_sectors', []):
            print(f"  {item.get('排名区间', 'N/A')}: 平均涨幅 {item.get('平均涨幅', 'N/A'):.2f}%, 涨停 {item.get('涨停数', 'N/A')}只")
        
        # 成交额集中度
        print(f"\n【成交额集中度 TOP5】")
        for i, item in enumerate(results.get('concentration', [])[:5], 1):
            print(f"  {i}. {item.get('市值区间', 'N/A')}")
            print(f"     个股数: {item.get('个股数', 'N/A')}只")
            print(f"     成交额占比: {item.get('占比(%)', 'N/A')}%")
        
        # 放量个股
        volume_surge = results.get('volume_surge', [])
        if volume_surge:
            print(f"\n【放量个股 TOP5】")
            for i, stock in enumerate(volume_surge[:5], 1):
                print(f"  {i}. {stock.get('name', 'N/A')} ({stock.get('ts_code', 'N/A')})")
                print(f"     类型: {stock.get('放量类型', 'N/A')}")
                print(f"     涨幅: {stock.get('pct_chg', 'N/A'):.2f}%")
                print(f"     量比: {stock.get('量比', 'N/A'):.2f}")
        
        # 涨停关键词
        keywords = results.get('keywords', {})
        if keywords:
            print(f"\n【热门关键词 TOP10】")
            for i, (keyword, count) in enumerate(keywords.get('hot_keywords', [])[:10], 1):
                print(f"  {i}. {keyword}: {count}次")
            
            # 分类统计
            print(f"\n【分类统计】")
            for cat_name, items in keywords.get('category_stats', {}).items():
                print(f"\n  【{cat_name}】")
                for kw, count in items[:5]:
                    print(f"    {kw}: {count}次")
            
            # 关键词-股票映射
            print(f"\n【关键词-涨停股映射】")
            for kw, stocks in list(keywords.get('keyword_groups', {}).items())[:5]:
                print(f"\n  [{kw}]")
                for s in stocks[:3]:
                    print(f"    - {s.get('name', 'N/A')}")
        
        print("\n" + "="*70)


def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        trade_date = sys.argv[1]
    else:
        trade_date = None
    
    try:
        review = DailyReview()
        results = review.run(trade_date)
        review.print_report(results)
    except Exception as e:
        logger.error(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
