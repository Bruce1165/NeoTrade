#!/usr/bin/env python3
"""
输出管理模块 - Output Manager

功能：
- 统一管理Excel输出
- 支持新增字段（上涨原因、行业分类、相关概念、新闻摘要）
- 图表生成管理
- 目录结构管理
"""

import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging
import shutil

logger = logging.getLogger(__name__)

# 基础输出目录
BASE_OUTPUT_DIR = "data/screeners"


class OutputManager:
    """输出管理器"""
    
    def __init__(self, screener_name: str, base_dir: str = BASE_OUTPUT_DIR):
        """
        初始化输出管理器
        
        Args:
            screener_name: 筛选器名称（英文，用于目录名）
            base_dir: 基础输出目录
        """
        self.screener_name = screener_name
        self.base_dir = base_dir
        
        # 创建目录结构
        self.screener_dir = os.path.join(base_dir, screener_name)
        self.charts_dir = os.path.join(self.screener_dir, "charts")
        
        os.makedirs(self.screener_dir, exist_ok=True)
        os.makedirs(self.charts_dir, exist_ok=True)
    
    def get_output_path(self, date_str: Optional[str] = None, 
                        suffix: str = "") -> str:
        """
        获取输出文件路径
        
        Args:
            date_str: 日期字符串，默认为今天
            suffix: 文件名后缀
        
        Returns:
            完整的文件路径
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        filename = f"{date_str}"
        if suffix:
            filename += f"_{suffix}"
        filename += ".xlsx"
        
        return os.path.join(self.screener_dir, filename)
    
    def get_charts_dir(self, date_str: Optional[str] = None) -> str:
        """
        获取图表目录
        
        Args:
            date_str: 日期字符串
        
        Returns:
            图表目录路径
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        charts_subdir = os.path.join(self.charts_dir, date_str)
        os.makedirs(charts_subdir, exist_ok=True)
        
        return charts_subdir
    
    def save_results(self, results: List[Dict], date_str: Optional[str] = None,
                     suffix: str = "", column_mapping: Optional[Dict[str, str]] = None) -> str:
        """
        保存筛选结果到Excel
        
        Args:
            results: 结果列表
            date_str: 日期字符串
            suffix: 文件名后缀
            column_mapping: 列名映射（英文->中文）
        
        Returns:
            保存的文件路径
        """
        if not results:
            logger.warning("No results to save")
            return ""
        
        df = pd.DataFrame(results)
        
        # 应用列名映射
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        output_path = self.get_output_path(date_str, suffix)
        
        try:
            df.to_excel(output_path, index=False, engine='xlsxwriter')
            logger.info(f"Results saved to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return ""
    
    def save_with_analysis(self, results: List[Dict], analysis_data: Dict[str, Dict],
                          date_str: Optional[str] = None, suffix: str = "",
                          column_mapping: Optional[Dict[str, str]] = None) -> str:
        """
        保存筛选结果（包含LLM分析数据）
        
        Args:
            results: 结果列表
            analysis_data: LLM分析数据 {code: analysis_dict}
            date_str: 日期字符串
            suffix: 文件名后缀
            column_mapping: 列名映射
        
        Returns:
            保存的文件路径
        """
        if not results:
            logger.warning("No results to save")
            return ""
        
        # 合并分析数据
        enriched_results = []
        for result in results:
            enriched = result.copy()
            code = result.get('code', result.get('股票代码', ''))
            
            if code in analysis_data:
                analysis = analysis_data[code]
                enriched['上涨原因'] = analysis.get('上涨原因', '')
                enriched['行业分类'] = analysis.get('行业分类', '')
                enriched['相关概念'] = analysis.get('相关概念', '')
                enriched['新闻摘要'] = analysis.get('新闻摘要', '')
                enriched['分析置信度'] = analysis.get('分析置信度', '')
            else:
                enriched['上涨原因'] = ''
                enriched['行业分类'] = ''
                enriched['相关概念'] = ''
                enriched['新闻摘要'] = ''
                enriched['分析置信度'] = ''
            
            enriched_results.append(enriched)
        
        return self.save_results(enriched_results, date_str, suffix, column_mapping)
    
    def load_previous_results(self, date_str: Optional[str] = None, 
                              days_back: int = 7) -> Optional[pd.DataFrame]:
        """
        加载之前的结果
        
        Args:
            date_str: 参考日期
            days_back: 向前查找的天数
        
        Returns:
            DataFrame或None
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        ref_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        for i in range(1, days_back + 1):
            check_date = (ref_date - pd.Timedelta(days=i)).strftime('%Y-%m-%d')
            filepath = self.get_output_path(check_date)
            
            if os.path.exists(filepath):
                try:
                    return pd.read_excel(filepath)
                except Exception as e:
                    logger.warning(f"Error loading previous results: {e}")
        
        return None
    
    def list_results(self, limit: int = 30) -> List[str]:
        """
        列出所有结果文件
        
        Args:
            limit: 最大返回数量
        
        Returns:
            文件路径列表
        """
        try:
            files = [f for f in os.listdir(self.screener_dir) if f.endswith('.xlsx')]
            files.sort(reverse=True)  # 最新的在前
            return [os.path.join(self.screener_dir, f) for f in files[:limit]]
        except Exception as e:
            logger.error(f"Error listing results: {e}")
            return []
    
    def cleanup_old_files(self, days_to_keep: int = 30):
        """
        清理旧文件
        
        Args:
            days_to_keep: 保留天数
        """
        cutoff_date = datetime.now() - pd.Timedelta(days=days_to_keep)
        
        try:
            for filename in os.listdir(self.screener_dir):
                if not filename.endswith('.xlsx'):
                    continue
                
                filepath = os.path.join(self.screener_dir, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_mtime < cutoff_date:
                    os.remove(filepath)
                    logger.debug(f"Removed old file: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
    
    def get_stats(self) -> Dict:
        """获取输出统计信息"""
        try:
            files = self.list_results(limit=1000)
            
            total_files = len(files)
            total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
            
            # 统计图表数量
            chart_count = 0
            if os.path.exists(self.charts_dir):
                for date_dir in os.listdir(self.charts_dir):
                    date_path = os.path.join(self.charts_dir, date_dir)
                    if os.path.isdir(date_path):
                        chart_count += len([f for f in os.listdir(date_path) if f.endswith(('.png', '.jpg'))])
            
            return {
                'screener_name': self.screener_name,
                'total_files': total_files,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'chart_count': chart_count,
                'output_dir': self.screener_dir
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                'screener_name': self.screener_name,
                'error': str(e)
            }


# 便捷函数
def get_output_manager(screener_name: str, base_dir: str = BASE_OUTPUT_DIR) -> OutputManager:
    """便捷函数：获取输出管理器"""
    return OutputManager(screener_name, base_dir)


def save_results(screener_name: str, results: List[Dict], 
                 date_str: Optional[str] = None) -> str:
    """便捷函数：保存结果"""
    manager = OutputManager(screener_name)
    return manager.save_results(results, date_str)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试输出管理器
    manager = OutputManager('test_screener')
    
    # 测试数据
    test_results = [
        {'code': '600519', 'name': '贵州茅台', 'close': 1800.0, 'pct_change': 2.5},
        {'code': '000001', 'name': '平安银行', 'close': 12.5, 'pct_change': 1.8},
    ]
    
    # 测试保存
    output_path = manager.save_results(test_results)
    print(f"\nSaved to: {output_path}")
    
    # 测试带分析数据保存
    analysis_data = {
        '600519': {
            '上涨原因': '业绩超预期',
            '行业分类': '白酒',
            '相关概念': '消费、白酒',
            '新闻摘要': '茅台发布年报，净利润增长15%',
            '分析置信度': '高'
        },
        '000001': {
            '上涨原因': '银行板块走强',
            '行业分类': '银行',
            '相关概念': '金融、银行',
            '新闻摘要': '银行业绩改善',
            '分析置信度': '中'
        }
    }
    
    output_path2 = manager.save_with_analysis(test_results, analysis_data, suffix='with_analysis')
    print(f"Saved with analysis to: {output_path2}")
    
    # 测试统计
    print("\nStats:")
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
