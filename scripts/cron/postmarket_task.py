#!/usr/bin/env python3
"""
盘后定时任务 - Neo量化研究体系
执行时间: 15:30
执行内容: 深度复盘分析（整合原有daily_review）
"""

import os
import sys

# 必须在导入akshare之前清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import akshare as ak
import pandas as pd
from sina_fetcher import SinaDataFetcher
from emotion_analyzer import EmotionAnalyzer
from sector_analyzer import SectorAnalyzer
from keyword_library import KeywordLibrary

# 配置日志
def setup_logging():
    """设置日志"""
    today = datetime.now().strftime('%Y%m%d')
    log_dir = Path('/Users/mac/.openclaw/workspace-neo/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f'postmarket_{today}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


class PostmarketTask:
    """盘后任务类"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.data_dir = Path('/Users/mac/.openclaw/workspace-neo/data/postmarket')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.fetcher = SinaDataFetcher()
        self.emotion_analyzer = EmotionAnalyzer(self.fetcher)
        self.sector_analyzer = SectorAnalyzer(self.fetcher)
        self.keyword_lib = KeywordLibrary()
    
    def is_trading_day(self) -> bool:
        """检查今天是否交易日"""
        # 简化判断：周一到周五为交易日（周六=5, 周日=6）
        return datetime.now().weekday() < 5
    
    def save_to_md(self, content: str, filename: str):
        """保存为Markdown"""
        today = datetime.now().strftime('%Y-%m-%d')
        save_dir = self.data_dir / today
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / f"{filename}.md"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"MD文件已保存: {filepath}")
    
    def save_to_excel(self, data_dict: dict, filename: str):
        """保存为Excel（多sheet）"""
        today = datetime.now().strftime('%Y-%m-%d')
        save_dir = self.data_dir / today
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / f"{filename}.xlsx"
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for sheet_name, df in data_dict.items():
                # 限制sheet名长度
                sheet_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        self.logger.info(f"Excel文件已保存: {filepath}")
    
    def run(self):
        """执行盘后深度复盘"""
        today = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"="*60)
        self.logger.info(f"开始执行盘后深度复盘: {today}")
        self.logger.info(f"="*60)
        
        # 检查交易日
        if not self.is_trading_day():
            self.logger.info("今日非交易日，跳过")
            return
        
        try:
            # 1. 情绪周期分析
            self.logger.info("[1/5] 情绪周期分析...")
            emotion_report = self.emotion_analyzer.generate_daily_report(today)
            
            # 2. 涨幅分布分析
            self.logger.info("[2/5] 涨幅分布分析...")
            top_sectors = self.sector_analyzer.analyze_top_sectors(today)
            
            # 3. 成交额集中度
            self.logger.info("[3/5] 成交额集中度分析...")
            concentration = self.sector_analyzer.analyze_sector_concentration(today)
            
            # 4. 放量个股
            self.logger.info("[4/5] 放量个股分析...")
            volume_surge = self.sector_analyzer.analyze_volume_surge(today)
            
            # 5. 关键词分析
            self.logger.info("[5/5] 涨停关键词分析...")
            limit_df = ak.stock_zt_pool_em(date=today)
            
            stocks_data = []
            if not limit_df.empty:
                for _, row in limit_df.iterrows():
                    code = row['代码']
                    name = row['名称']
                    ts_code = code + ('.SH' if code.startswith('6') else '.SZ')
                    industry = row.get('所属行业', '')
                    
                    keywords = self.keyword_lib.extract_keywords(name, ts_code, industry)
                    stocks_data.append({
                        'ts_code': ts_code,
                        'name': name,
                        'limit_days': row['连板数'],
                        'keywords': keywords,
                    })
                
                self.keyword_lib.update_stats(today, stocks_data)
                keyword_report = self.keyword_lib.export_report(today)
            else:
                keyword_report = {'hot_keywords': [], 'category_stats': {}}
            
            # 生成综合报告
            self._generate_comprehensive_report(
                today, emotion_report, top_sectors, concentration, 
                volume_surge, limit_df, keyword_report, stocks_data
            )
            
            self.logger.info(f"="*60)
            self.logger.info(f"盘后复盘完成: {today}")
            self.logger.info(f"="*60)
            
        except Exception as e:
            self.logger.error(f"盘后复盘失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _get_stock_detail_data(self, date: str, limit_df: pd.DataFrame) -> pd.DataFrame:
        """
        获取涨幅>10%个股的详细数据（包括涨停股和未涨停的大涨股）
        排除ST股
        排序：上涨原因相似度分类 -> 连板数降序 -> 涨幅降序
        """
        self.logger.info("获取涨幅>10%个股详细数据...")
        
        # 获取当日全部行情（包含详细信息）
        daily_df = self.fetcher.get_daily_data(date)
        
        # 筛选涨幅>9.85%且排除ST股和北交所股票
        # ST股名称特征：包含"ST"或"*ST"
        # 北交所股票代码特征：以8、9或4开头（如83xxxx, 87xxxx, 92xxxx, 43xxxx等）
        
        # 先筛选涨幅和排除ST
        surge_df = daily_df[
            (daily_df['pct_chg'] > 9.85) & 
            (~daily_df['name'].str.contains('ST', na=False))
        ].copy()
        
        # 排除北交所股票（代码以8、9或4开头）
        surge_df = surge_df[~surge_df['ts_code'].astype(str).str.match(r'^[894]', na=False)]
        
        self.logger.info(f"涨幅>9.85%个股（排除ST和北交所）: {len(surge_df)} 只")
        
        if surge_df.empty:
            return pd.DataFrame()
        
        # 获取基础信息（包含上市日期）
        try:
            stock_basic = ak.stock_info_a_code_name()
            stock_basic = stock_basic.rename(columns={
                'code': 'ts_code',
                'name': 'name_basic'
            })
        except:
            stock_basic = pd.DataFrame()
        
        # 创建涨停股映射（用于获取连板数和涨停时间）
        limit_up_map = {}
        if not limit_df.empty:
            for _, row in limit_df.iterrows():
                code = row['代码']
                limit_up_map[code] = {
                    'limit_days': row.get('连板数', 0),
                    'limit_time': row.get('首次封板时间', '') if not pd.isna(row.get('首次封板时间', '')) else '',
                    'industry': row.get('所属行业', '')
                }
        
        result_rows = []
        
        for _, spot in surge_df.iterrows():
            code = spot['ts_code']
            name = spot['name']
            
            # 从涨停映射获取连板数、涨停时间、行业
            limit_info = limit_up_map.get(code, {})
            limit_days = limit_info.get('limit_days', 0)
            limit_time = limit_info.get('limit_time', '')
            industry = limit_info.get('industry', spot.get('industry', ''))
            
            # 计算多周期涨幅
            change_5d = None
            change_10d = None
            change_20d = None
            
            try:
                # 获取历史数据计算多周期涨幅
                hist = self.fetcher.get_stock_hist(code, start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'))
                if not hist.empty and len(hist) >= 2:
                    hist = hist.sort_values('trade_date', ascending=False).reset_index(drop=True)
                    current_close = hist.iloc[0]['close']
                    
                    if len(hist) > 5:
                        change_5d = round((current_close / hist.iloc[5]['close'] - 1) * 100, 2)
                    if len(hist) > 10:
                        change_10d = round((current_close / hist.iloc[10]['close'] - 1) * 100, 2)
                    if len(hist) > 20:
                        change_20d = round((current_close / hist.iloc[20]['close'] - 1) * 100, 2)
            except Exception as e:
                self.logger.warning(f"获取 {code} 历史数据失败: {e}")
            
            # 获取上市日期
            list_date = ''
            if not stock_basic.empty:
                basic_match = stock_basic[stock_basic['ts_code'] == code]
                if not basic_match.empty:
                    list_date = basic_match.iloc[0].get('list_date', '')
            
            # 上涨原因（从关键词库获取）
            ts_code = code + ('.SH' if code.startswith('6') else '.SZ')
            keywords = self.keyword_lib.extract_keywords(name, ts_code, industry)
            reason = ', '.join(keywords) if keywords else ''
            
            result_rows.append({
                '股票代码': code,
                '股票名称': name,
                '连板数': limit_days,
                '涨幅': round(spot.get('pct_chg', 0), 2),
                '涨停时间': limit_time,
                '上涨原因': reason,
                '总金额(万)': round(spot.get('amount', 0) / 10000, 2) if spot.get('amount') else 0,
                '换手率': round(spot.get('turnover', 0), 2),
                '总市值(亿)': round(spot.get('total_mv', 0) / 100000000, 2) if spot.get('total_mv') else 0,
                '行业': industry,
                '市盈率(TTM)': round(spot.get('pe', 0), 2) if spot.get('pe') else None,
                '市净率': round(spot.get('pb', 0), 2) if spot.get('pb') else None,
                '五日涨幅': change_5d,
                '十日涨幅': change_10d,
                '二十日涨幅': change_20d,
                '上市日期': list_date,
            })
        
        result_df = pd.DataFrame(result_rows)
        
        # 排序：上涨原因相似度分类 -> 连板数降序 -> 涨幅降序
        if not result_df.empty:
            # 为上涨原因创建分类键（相同的上涨原因排在一起）
            result_df['原因分类'] = result_df['上涨原因'].apply(
                lambda x: x.split(',')[0] if x and ',' in x else (x if x else '其他')
            )
            
            # 排序：原因分类 -> 连板数降序 -> 涨幅降序
            result_df = result_df.sort_values(
                by=['原因分类', '连板数', '涨幅'],
                ascending=[True, False, False]
            ).reset_index(drop=True)
            
            # 删除临时分类列
            result_df = result_df.drop(columns=['原因分类'])
        
        self.logger.info(f"获取详细数据完成: {len(result_df)} 只股票")
        return result_df
    
    def _generate_comprehensive_report(self, date, emotion, sectors, concentration, 
                                       volume_surge, limit_df, keyword_report, stocks_data):
        """生成综合复盘报告"""
        
        # 获取涨停股详细数据
        stock_detail_df = self._get_stock_detail_data(date, limit_df)
        
        # Markdown报告
        md_content = f"""# 每日深度复盘报告

**日期**: {date}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、情绪周期分析

### 情绪四要素

| 指标 | 数值 | 阶段判断 |
|------|------|----------|
| 涨停数量 | {emotion.iloc[0]['涨停数量'] if not emotion.empty else 'N/A'} | - |
| 溢价率 | {emotion.iloc[0]['溢价率(%)'] if not emotion.empty else 'N/A'}% | - |
| 连板数量 | {emotion.iloc[0]['连板数量'] if not emotion.empty else 'N/A'} | - |
| 空间高度 | {emotion.iloc[0]['空间高度'] if not emotion.empty else 'N/A'}板 | - |
| **情绪阶段** | **{emotion.iloc[0]['情绪阶段'] if not emotion.empty else 'N/A'}** | - |

---

## 二、涨幅分布分析

{sectors.to_markdown(index=False) if not sectors.empty else '无数据'}

---

## 三、成交额集中度

{concentration.head(10).to_markdown(index=False) if not concentration.empty else '无数据'}

---

## 四、涨停关键词分析

### 热门关键词 TOP15

"""
        
        for i, (kw, count) in enumerate(keyword_report.get('hot_keywords', [])[:15], 1):
            md_content += f"{i}. **{kw}**: {count}次\n"
        
        md_content += "\n### 分类统计\n\n"
        
        for cat_name, items in keyword_report.get('category_stats', {}).items():
            md_content += f"**{cat_name}**:\n"
            for kw, count in items[:5]:
                md_content += f"- {kw}: {count}次\n"
            md_content += "\n"
        
        md_content += "\n---\n\n## 五、涨停及大涨股明细（涨幅>9.85%，排除ST和北交所）\n\n"

        if not stock_detail_df.empty:
            md_content += stock_detail_df.to_markdown(index=False)
        else:
            md_content += "今日无涨幅>9.85%个股"
        
        md_content += f"""

---

*报告由Neo量化研究系统自动生成*
"""
        
        self.save_to_md(md_content, 'daily_review')
        
        # Excel报告（多sheet）
        excel_data = {
            '情绪分析': emotion,
            '涨幅分布': sectors,
            '成交额集中度': concentration.head(20),
            '放量个股': volume_surge.head(30) if not volume_surge.empty else pd.DataFrame(),
            '涨停及大涨股明细': stock_detail_df if not stock_detail_df.empty else pd.DataFrame(),
            '热门关键词': pd.DataFrame(keyword_report.get('hot_keywords', []), columns=['关键词', '次数']),
        }
        
        self.save_to_excel(excel_data, 'daily_review')


def main():
    """主函数"""
    task = PostmarketTask()
    task.run()


if __name__ == '__main__':
    main()
