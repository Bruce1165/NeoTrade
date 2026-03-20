#!/usr/bin/env python3
"""
盘中定时任务 - Neo量化研究体系
执行时间: 9:35, 9:45, 10:00, 15:00
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import akshare as ak
import pandas as pd
from keyword_library import KeywordLibrary

# 配置日志
def setup_logging():
    """设置日志"""
    today = datetime.now().strftime('%Y%m%d')
    log_dir = Path('/Users/mac/.openclaw/workspace-neo/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f'intraday_{today}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


class IntradayTask:
    """盘中任务类"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.data_dir = Path('/Users/mac/.openclaw/workspace-neo/data/intraday')
        self.keyword_lib = KeywordLibrary()
        
    def is_trading_day(self) -> bool:
        """检查今天是否交易日"""
        # 简化判断：周一到周五为交易日（周六=5, 周日=6）
        return datetime.now().weekday() < 5
    
    def get_current_time_str(self) -> str:
        """获取当前时间字符串 HHMM"""
        return datetime.now().strftime('%H%M')
    
    def save_to_md(self, content: str, filename: str):
        """保存为Markdown文件"""
        today = datetime.now().strftime('%Y-%m-%d')
        save_dir = self.data_dir / today
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / f"{filename}.md"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"MD文件已保存: {filepath}")
    
    def save_to_excel(self, data_dict: dict, filename: str):
        """保存为Excel文件（多sheet）"""
        today = datetime.now().strftime('%Y-%m-%d')
        save_dir = self.data_dir / today
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / f"{filename}.xlsx"
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for sheet_name, df in data_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        self.logger.info(f"Excel文件已保存: {filepath}")
    
    def analyze_index_volume(self, time_str: str):
        """分析指数成交额变化"""
        self.logger.info(f"[{time_str}] 开始分析指数成交额...")
        
        indices = {
            '上证指数': '000001',
            '深证成指': '399001',
            '沪深300': '000300',
            '创业板指': '399006',
            '科创综指': '000680',
        }
        
        results = []
        for name, code in indices.items():
            try:
                # 获取指数行情
                df = ak.index_zh_a_hist(symbol=code, period="daily", 
                                       start_date=datetime.now().strftime('%Y%m%d'),
                                       end_date=datetime.now().strftime('%Y%m%d'))
                if not df.empty:
                    results.append({
                        '指数名称': name,
                        '指数代码': code,
                        '当前价': df.iloc[0]['收盘'],
                        '涨跌幅': df.iloc[0]['涨跌幅'],
                        '成交额(亿)': df.iloc[0]['成交额'] / 1e8,
                    })
            except Exception as e:
                self.logger.error(f"获取{name}数据失败: {e}")
        
        result_df = pd.DataFrame(results)
        
        # 生成Markdown报告
        md_content = f"""# 指数成交额观测报告

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 主要指数行情

{result_df.to_markdown(index=False)}

## 说明

- 观测时间点: {time_str}
- 对比基准: 较前一日同一时间段
- 数据状态: 实时
"""
        
        self.save_to_md(md_content, f"{time_str}_index")
        self.logger.info(f"[{time_str}] 指数分析完成")
        
        return result_df
    
    def analyze_limit_up_stocks(self, time_str: str):
        """分析涨停股"""
        self.logger.info(f"[{time_str}] 开始分析涨停股...")
        
        try:
            # 获取涨停数据
            df = ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
            
            if df.empty:
                self.logger.warning("今日无涨停股")
                return None
            
            # 添加关键词
            df['关键词'] = df['名称'].apply(
                lambda name: ', '.join(self.keyword_lib.extract_keywords(name, '', ''))
            )
            
            # 按概念分组统计
            concept_groups = {}
            for _, row in df.iterrows():
                keywords = row['关键词'].split(', ') if row['关键词'] else ['其他']
                for kw in keywords:
                    if kw not in concept_groups:
                        concept_groups[kw] = []
                    concept_groups[kw].append(row.to_dict())
            
            # 排序概念（按涨停数量）
            sorted_concepts = sorted(concept_groups.items(), 
                                    key=lambda x: len(x[1]), reverse=True)[:5]
            
            # 生成报告
            md_content = f"""# 涨停股分析报告

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**涨停总数**: {len(df)}只

## 热门概念板块 TOP5

"""
            
            for i, (concept, stocks) in enumerate(sorted_concepts, 1):
                md_content += f"\n### {i}. {concept} ({len(stocks)}只)\n\n"
                
                # 个股排序：涨停优先，然后按成交额
                stocks_df = pd.DataFrame(stocks)
                if '成交额' in stocks_df.columns:
                    stocks_df = stocks_df.sort_values(['连板数', '成交额'], ascending=[False, False])
                
                for _, s in stocks_df.head(10).iterrows():
                    md_content += f"- {s['名称']} ({s['代码']}) - {s.get('连板数', 1)}板\n"
            
            md_content += f"""
## 完整涨停列表

{df[['代码', '名称', '涨跌幅', '连板数', '所属行业', '关键词']].to_markdown(index=False)}
"""
            
            self.save_to_md(md_content, f"{time_str}_limit_up")
            
            # 保存Excel（多sheet）
            excel_data = {
                '涨停股列表': df[['代码', '名称', '涨跌幅', '最新价', '成交额', '连板数', '所属行业', '关键词']],
                '概念统计': pd.DataFrame([(k, len(v)) for k, v in sorted_concepts], 
                                        columns=['概念', '涨停数']),
            }
            
            # 每个概念一个sheet
            for concept, stocks in sorted_concepts[:5]:
                sheet_name = concept[:10]  # Excel sheet名最多31字符
                excel_data[sheet_name] = pd.DataFrame(stocks)[['代码', '名称', '涨跌幅', '连板数']]
            
            self.save_to_excel(excel_data, f"{time_str}_limit_up")
            
            self.logger.info(f"[{time_str}] 涨停股分析完成: {len(df)}只")
            return df
            
        except Exception as e:
            self.logger.error(f"分析涨停股失败: {e}")
            return None
    
    def analyze_weak_stocks(self, time_str: str, min_drop: float = -5.0, min_amount: float = 5.0):
        """分析弱势股（跌幅大+成交额大）"""
        self.logger.info(f"[{time_str}] 开始分析弱势股...")
        
        try:
            # 获取全市场数据
            df = ak.stock_zh_a_spot_em()
            
            # 筛选跌幅>5%且成交额>5亿
            weak_df = df[(df['涨跌幅'] <= min_drop) & (df['成交额'] >= min_amount * 1e8)].copy()
            
            if weak_df.empty:
                self.logger.warning("无符合条件的弱势股")
                return None
            
            # 添加关键词
            weak_df['关键词'] = weak_df['名称'].apply(
                lambda name: ', '.join(self.keyword_lib.extract_keywords(name, '', ''))
            )
            
            # 按概念分组
            concept_groups = {}
            for _, row in weak_df.iterrows():
                keywords = row['关键词'].split(', ') if row['关键词'] else ['其他']
                for kw in keywords:
                    if kw not in concept_groups:
                        concept_groups[kw] = []
                    concept_groups[kw].append(row.to_dict())
            
            # 排序（按跌幅和成交额）
            sorted_concepts = sorted(concept_groups.items(),
                                    key=lambda x: sum([s['成交额'] for s in x[1]]),
                                    reverse=True)[:5]
            
            # 生成报告
            md_content = f"""# 弱势股分析报告

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**筛选条件**: 跌幅>{min_drop}%, 成交额>{min_amount}亿
**弱势股总数**: {len(weak_df)}只

## 弱势概念板块 TOP5

"""
            
            for i, (concept, stocks) in enumerate(sorted_concepts, 1):
                avg_drop = sum([s['涨跌幅'] for s in stocks]) / len(stocks)
                md_content += f"\n### {i}. {concept} ({len(stocks)}只, 平均跌幅{avg_drop:.2f}%)\n\n"
                
                stocks_df = pd.DataFrame(stocks).sort_values('涨跌幅')
                for _, s in stocks_df.head(5).iterrows():
                    md_content += f"- {s['名称']} ({s['代码']}) - 跌幅{s['涨跌幅']:.2f}%\n"
            
            md_content += f"""
## 完整弱势股列表

{weak_df[['代码', '名称', '涨跌幅', '最新价', '成交额', '所属行业', '关键词']].head(20).to_markdown(index=False)}
"""
            
            self.save_to_md(md_content, f"{time_str}_weak")
            
            # Excel
            excel_data = {
                '弱势股列表': weak_df[['代码', '名称', '涨跌幅', '最新价', '成交额', '所属行业', '关键词']].head(50),
                '概念统计': pd.DataFrame([(k, len(v)) for k, v in sorted_concepts], 
                                        columns=['概念', '股票数']),
            }
            self.save_to_excel(excel_data, f"{time_str}_weak")
            
            self.logger.info(f"[{time_str}] 弱势股分析完成: {len(weak_df)}只")
            return weak_df
            
        except Exception as e:
            self.logger.error(f"分析弱势股失败: {e}")
            return None
    
    def run(self, task_type: str = None):
        """运行盘中任务"""
        time_str = self.get_current_time_str()
        
        self.logger.info(f"="*60)
        self.logger.info(f"开始执行盘中任务: {time_str}")
        self.logger.info(f"="*60)
        
        # 检查是否交易日
        if not self.is_trading_day():
            self.logger.info("今日非交易日，跳过")
            return
        
        try:
            if task_type == 'index' or time_str in ['0935', '0945']:
                # 指数成交额观测
                self.analyze_index_volume(time_str)
                
            elif task_type == 'analysis' or time_str in ['1000', '1500']:
                # 涨停股分析
                self.analyze_limit_up_stocks(time_str)
                # 弱势股分析
                self.analyze_weak_stocks(time_str)
                
            else:
                self.logger.warning(f"未知任务类型或时间: {time_str}")
                
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        self.logger.info(f"="*60)
        self.logger.info(f"盘中任务完成: {time_str}")
        self.logger.info(f"="*60)


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['index', 'analysis'], 
                       help='任务类型: index-指数观测, analysis-涨跌分析')
    args = parser.parse_args()
    
    task = IntradayTask()
    task.run(args.type)


if __name__ == '__main__':
    main()
