#!/usr/bin/env python3
"""
Keyword Expander - 关键词库扩充器
通过网络搜索获取热门概念，自动扩充关键词库
"""

import os
import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict

# Clear proxy env vars
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import requests
from bs4 import BeautifulSoup

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from keyword_library import KeywordLibrary

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeywordExpander:
    """
    关键词库扩充器
    
    功能：
    1. 从财经网站抓取热门概念
    2. 通过搜索推理生成相关关键词
    3. 自动扩充 keyword_library
    """
    
    def __init__(self):
        self.logger = logging.getLogger('keyword_expander')
        self.keyword_lib = KeywordLibrary()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def fetch_hot_concepts_from_eastmoney(self) -> List[Dict]:
        """
        从东方财富获取热门概念板块
        
        Returns:
            [{name, code, change_pct, related_stocks}, ...]
        """
        concepts = []
        
        try:
            # 东方财富概念板块排行
            url = 'http://quote.eastmoney.com/center/gridlist.html#hs_a_board'
            
            # 使用 AKShare 获取概念板块数据
            import akshare as ak
            
            # 获取概念板块资金流向
            df = ak.stock_board_concept_name_em()
            
            if not df.empty:
                # 按涨幅排序，取前30
                df = df.head(30)
                
                for _, row in df.iterrows():
                    concept_name = row.get('板块名称', '')
                    change_pct = row.get('涨跌幅', 0)
                    
                    if concept_name:
                        concepts.append({
                            'name': concept_name,
                            'change_pct': change_pct,
                            'source': 'eastmoney'
                        })
            
            self.logger.info(f"从东方财富获取 {len(concepts)} 个热门概念")
            
        except Exception as e:
            self.logger.error(f"获取东方财富概念失败: {e}")
        
        return concepts
    
    def fetch_hot_concepts_from_10jqka(self) -> List[Dict]:
        """
        从同花顺获取热门概念
        """
        concepts = []
        
        try:
            import akshare as ak
            
            # 同花顺概念板块
            df = ak.stock_board_concept_hist_ths(symbol="人工智能")
            
            # 获取热门概念列表
            df_list = ak.stock_board_concept_name_ths()
            
            if not df_list.empty:
                for _, row in df_list.head(20).iterrows():
                    concept_name = row.get('概念名称', '')
                    
                    if concept_name and concept_name not in [c['name'] for c in concepts]:
                        concepts.append({
                            'name': concept_name,
                            'change_pct': 0,
                            'source': 'ths'
                        })
            
            self.logger.info(f"从同花顺获取 {len(concepts)} 个热门概念")
            
        except Exception as e:
            self.logger.error(f"获取同花顺概念失败: {e}")
        
        return concepts
    
    def search_related_keywords(self, concept: str) -> List[str]:
        """
        通过搜索推理生成相关关键词
        
        Args:
            concept: 概念名称
            
        Returns:
            相关关键词列表
        """
        related = set()
        
        # 预定义的概念-关键词映射（基于行业知识）
        concept_mappings = {
            '人工智能': ['AI', '大模型', '深度学习', '神经网络', '自然语言处理', '计算机视觉', 
                      '机器学习', '算法', '算力', 'AIGC', 'ChatGPT', '多模态', 'Transformer'],
            '机器人': ['人形机器人', '工业机器人', '服务机器人', '减速器', '谐波减速器', 
                      'RV减速器', '丝杠', '传感器', '电机', '伺服系统', '控制器'],
            '芯片': ['半导体', '集成电路', '晶圆', '光刻', 'EDA', '存储芯片', 'CPU', 'GPU',
                    'AI芯片', '先进封装', 'Chiplet', '碳化硅', '氮化镓'],
            '新能源': ['光伏', '风电', '储能', '锂电池', '氢能', '核电', '逆变器', 
                      '钙钛矿', 'TOPCon', 'HJT', '钠离子电池'],
            '算力': ['数据中心', '服务器', '云计算', '边缘计算', '液冷', '光模块', 
                    'CPO', 'DPU', '智算中心', '超算'],
            '低空经济': ['无人机', 'eVTOL', '飞行汽车', '通航', '空管系统', '卫星导航',
                        '航空发动机', '碳纤维'],
            '固态电池': ['固态电解质', '半固态电池', '凝聚态电池', '锂金属负极', 
                        '硫化物电解质', '氧化物电解质'],
            '数据要素': ['数据确权', '数据交易', '数据安全', '隐私计算', '数据治理',
                        '数据资产', '大数据', '数据湖'],
            '智能驾驶': ['自动驾驶', '激光雷达', '毫米波雷达', '高精地图', '车路协同',
                        '智能座舱', '域控制器', '线控底盘'],
            '商业航天': ['卫星互联网', '火箭发射', '卫星制造', '星载芯片', '地面设备',
                        '太空旅游', '卫星通信'],
        }
        
        # 直接匹配
        if concept in concept_mappings:
            related.update(concept_mappings[concept])
        
        # 模糊匹配
        for key, keywords in concept_mappings.items():
            if key in concept or concept in key:
                related.update(keywords)
        
        # 生成派生关键词
        related.update(self._generate_derivatives(concept))
        
        return list(related)
    
    def _generate_derivatives(self, concept: str) -> Set[str]:
        """生成派生关键词"""
        derivatives = set()
        
        # 常见后缀
        suffixes = ['概念', '板块', '产业', '技术', '设备', '材料', '系统', '服务']
        for suffix in suffixes:
            derivatives.add(f"{concept}{suffix}")
        
        # 常见前缀
        prefixes = ['智能', '高端', '新型', '先进', '核心', '关键']
        for prefix in prefixes:
            derivatives.add(f"{prefix}{concept}")
        
        # 相关动词
        verbs = ['制造', '生产', '研发', '应用', '服务', '解决方案']
        for verb in verbs:
            derivatives.add(f"{concept}{verb}")
        
        return derivatives
    
    def extract_keywords_from_news(self, text: str) -> List[str]:
        """
        从新闻文本提取关键词
        
        Args:
            text: 新闻文本
            
        Returns:
            关键词列表
        """
        keywords = []
        
        # 匹配常见模式
        patterns = [
            r'(\w+)(?:概念|板块|题材)',
            r'(\w+)(?:产业|行业|领域)',
            r'(?:关注|看好|布局|进军)(\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)
        
        return list(set(keywords))
    
    def expand_library(self, dry_run: bool = False) -> Dict:
        """
        扩充关键词库
        
        Args:
            dry_run: 如果True，只返回建议不实际修改
            
        Returns:
            扩充结果报告
        """
        self.logger.info("="*60)
        self.logger.info("开始扩充关键词库")
        self.logger.info("="*60)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'new_concepts': [],
            'expanded_keywords': {},
            'suggestions': []
        }
        
        # 1. 获取热门概念
        hot_concepts = []
        hot_concepts.extend(self.fetch_hot_concepts_from_eastmoney())
        hot_concepts.extend(self.fetch_hot_concepts_from_10jqka())
        
        # 去重
        seen = set()
        unique_concepts = []
        for c in hot_concepts:
            if c['name'] not in seen:
                seen.add(c['name'])
                unique_concepts.append(c)
        
        self.logger.info(f"获取到 {len(unique_concepts)} 个唯一热门概念")
        
        # 2. 检查哪些是新的概念
        existing_concepts = set()
        for category in self.keyword_lib.library['categories'].values():
            existing_concepts.update(category.keys())
        
        new_concepts = [c for c in unique_concepts if c['name'] not in existing_concepts]
        
        self.logger.info(f"发现 {len(new_concepts)} 个新概念")
        
        # 3. 为每个新概念生成关键词
        for concept in new_concepts:
            concept_name = concept['name']
            related_keywords = self.search_related_keywords(concept_name)
            
            if related_keywords:
                report['new_concepts'].append({
                    'name': concept_name,
                    'keywords': related_keywords,
                    'source': concept.get('source', 'unknown')
                })
                
                if not dry_run:
                    # 添加到关键词库
                    self.keyword_lib.add_custom_keyword(
                        category='concept',
                        main_keyword=concept_name,
                        sub_keywords=related_keywords
                    )
                    self.logger.info(f"添加新概念: {concept_name} ({len(related_keywords)} 个关键词)")
            else:
                report['suggestions'].append({
                    'type': 'new_concept_no_keywords',
                    'name': concept_name,
                    'suggestion': '需要手动添加相关关键词'
                })
        
        # 4. 扩展现有概念
        for category_name, category_data in self.keyword_lib.library['categories'].items():
            for main_keyword, sub_keywords in category_data.items():
                # 如果子关键词少于5个，尝试扩充
                if len(sub_keywords) < 5:
                    new_keywords = self.search_related_keywords(main_keyword)
                    new_keywords = [k for k in new_keywords if k not in sub_keywords]
                    
                    if new_keywords:
                        report['expanded_keywords'][main_keyword] = new_keywords
                        
                        if not dry_run:
                            self.keyword_lib.add_custom_keyword(
                                category=category_name,
                                main_keyword=main_keyword,
                                sub_keywords=new_keywords
                            )
                            self.logger.info(f"扩展现有概念: {main_keyword} (+{len(new_keywords)} 个关键词)")
        
        # 5. 保存库
        if not dry_run:
            self.keyword_lib._save_library()
        
        self.logger.info("="*60)
        self.logger.info(f"扩充完成: 新增 {len(report['new_concepts'])} 个概念, 扩充 {len(report['expanded_keywords'])} 个现有概念")
        self.logger.info("="*60)
        
        return report
    
    def generate_daily_keywords_report(self) -> str:
        """
        生成每日关键词报告
        
        Returns:
            Markdown 格式报告
        """
        report = self.expand_library(dry_run=True)
        
        lines = [
            "# 关键词库扩充报告",
            f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "\n## 新发现的热门概念",
        ]
        
        if report['new_concepts']:
            for concept in report['new_concepts']:
                lines.append(f"\n### {concept['name']}")
                lines.append(f"来源: {concept['source']}")
                lines.append(f"关键词: {', '.join(concept['keywords'][:10])}")
        else:
            lines.append("\n暂无新概念")
        
        lines.append("\n## 建议扩充的现有概念")
        if report['expanded_keywords']:
            for name, keywords in report['expanded_keywords'].items():
                lines.append(f"\n- **{name}**: {', '.join(keywords[:5])}")
        else:
            lines.append("\n暂无建议")
        
        lines.append("\n## 需要手动处理")
        if report['suggestions']:
            for s in report['suggestions']:
                lines.append(f"\n- {s['name']}: {s['suggestion']}")
        else:
            lines.append("\n无")
        
        return '\n'.join(lines)


def main():
    """主函数"""
    expander = KeywordExpander()
    
    # 先预览
    print("="*80)
    print("关键词库扩充预览 (Dry Run)")
    print("="*80)
    
    report = expander.expand_library(dry_run=True)
    
    print(f"\n发现 {len(report['new_concepts'])} 个新概念:")
    for c in report['new_concepts'][:5]:
        print(f"  - {c['name']}: {', '.join(c['keywords'][:5])}")
    
    print(f"\n建议扩充 {len(report['expanded_keywords'])} 个现有概念")
    
    # 询问是否执行
    print("\n" + "="*80)
    response = input("是否执行扩充? (y/n): ")
    
    if response.lower() == 'y':
        report = expander.expand_library(dry_run=False)
        print(f"\n✓ 扩充完成!")
        print(f"  新增概念: {len(report['new_concepts'])}")
        print(f"  扩展现有: {len(report['expanded_keywords'])}")
    else:
        print("\n已取消")


if __name__ == '__main__':
    main()
