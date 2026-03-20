#!/usr/bin/env python3
"""
涨停关键词提取器 - Neo量化研究体系
提取涨停股的关键词，基于相似度聚类
"""

import os
import sys
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter, defaultdict
import pandas as pd
import numpy as np

sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')
from akshare_fetcher import AKShareDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeywordExtractor:
    """关键词提取器"""
    
    def __init__(self, fetcher: Optional[AKShareDataFetcher] = None):
        """初始化"""
        if fetcher is None:
            fetcher = AKShareDataFetcher()
        self.fetcher = fetcher
        
        # 加载行业关键词库
        self.industry_keywords = self._load_industry_keywords()
        
        # 加载概念关键词库
        self.concept_keywords = self._load_concept_keywords()
        
        # 停用词
        self.stopwords = set(['公司', '股份', '集团', '有限', '科技', '实业', '发展', '投资'])
    
    def _load_industry_keywords(self) -> Dict[str, List[str]]:
        """加载行业关键词映射"""
        return {
            '半导体': ['芯片', '半导体', '集成电路', '晶圆', '光刻', 'EDA', '存储', 'CPU', 'GPU'],
            '新能源': ['光伏', '风电', '储能', '锂电池', '氢能', '核电', '清洁能源'],
            '新能源汽车': ['电动车', '动力电池', '充电桩', '自动驾驶', '智能座舱', '整车'],
            '人工智能': ['AI', '大模型', '算力', '算法', '机器学习', '计算机视觉', 'NLP'],
            '医药': ['创新药', 'CXO', '医疗器械', '生物制药', '中药', '疫苗', '基因'],
            '军工': ['航空航天', '船舶', '兵器', '雷达', '导弹', '军民融合'],
            '金融': ['银行', '保险', '证券', '信托', '金融科技', '数字货币'],
            '地产': ['房地产', '物业管理', '建材', '装修', '家居'],
            '消费': ['白酒', '食品', '家电', '零售', '餐饮', '旅游'],
            '周期': ['煤炭', '钢铁', '有色', '化工', '石油', '航运'],
        }
    
    def _load_concept_keywords(self) -> Dict[str, List[str]]:
        """加载概念关键词映射"""
        return {
            '新质生产力': ['机器人', '工业母机', '3D打印', '智能制造', '工业互联网'],
            '设备更新': ['机床', '工程机械', '农机', '医疗设备', '教育设备'],
            '以旧换新': ['家电', '汽车', '消费电子'],
            '低空经济': ['无人机', 'eVTOL', '通航', '空管', '卫星导航'],
            '固态电池': ['固态电解质', '锂金属', '凝聚态', '快充'],
            '人形机器人': ['减速器', '丝杠', '传感器', '灵巧手', '电机'],
            '数据要素': ['数据确权', '数据交易', '数据安全', '大数据', '云计算'],
            '国产替代': ['信创', '操作系统', '数据库', '办公软件', '工业软件'],
        }
    
    def extract_from_name(self, name: str) -> List[str]:
        """
        从股票名称提取关键词
        
        Args:
            name: 股票名称
            
        Returns:
            关键词列表
        """
        keywords = []
        
        # 直接匹配行业关键词
        for industry, words in self.industry_keywords.items():
            for word in words:
                if word in name:
                    keywords.append(word)
                    keywords.append(industry)
                    break
        
        # 提取名称中的核心业务词（去除停用词）
        for char in name:
            if char not in self.stopwords and len(char) >= 2:
                keywords.append(char)
        
        return list(set(keywords))
    
    def extract_from_business(self, ts_code: str) -> List[str]:
        """
        从主营业务提取关键词
        
        Args:
            ts_code: 股票代码
            
        Returns:
            关键词列表
        """
        try:
            import akshare as ak
            
            # 获取个股信息
            info = ak.stock_individual_info_em(symbol=ts_code.split('.')[0])
            
            keywords = []
            
            # 从主营业务提取
            if '主营业务' in info.columns:
                business = info['主营业务'].values[0]
                if pd.notna(business):
                    # 分词提取（简化版）
                    words = self._segment_text(business)
                    keywords.extend(words)
            
            # 从行业提取
            if '行业' in info.columns:
                industry = info['行业'].values[0]
                if pd.notna(industry):
                    keywords.append(industry)
            
            return list(set(keywords))
            
        except Exception as e:
            logger.warning(f"提取 {ts_code} 主营业务关键词失败: {e}")
            return []
    
    def extract_from_concepts(self, ts_code: str) -> List[str]:
        """
        从所属概念提取关键词
        
        Args:
            ts_code: 股票代码
            
        Returns:
            关键词列表
        """
        keywords = []
        
        try:
            import akshare as ak
            
            symbol = ts_code.split('.')[0]
            
            # 获取概念板块列表
            concept_list = ak.stock_board_concept_name_ths()
            
            # 遍历概念板块，检查股票是否属于该概念
            for concept_name in concept_list['名称'].head(100):  # 只检查前100个概念
                try:
                    concept_stocks = ak.stock_board_concept_cons_em(symbol=concept_name)
                    if symbol in concept_stocks['代码'].values:
                        keywords.append(concept_name)
                        
                        # 同时添加概念对应的关键词
                        if concept_name in self.concept_keywords:
                            keywords.extend(self.concept_keywords[concept_name])
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"提取 {ts_code} 概念关键词失败: {e}")
        
        return list(set(keywords))
    
    def extract_from_limit_up_reason(self, ts_code: str, name: str) -> List[str]:
        """
        从涨停原因提取关键词（需要爬取东方财富涨停页面）
        
        Args:
            ts_code: 股票代码
            name: 股票名称
            
        Returns:
            关键词列表
        """
        # 这里可以实现爬虫逻辑
        # 简化版：返回空列表
        return []
    
    def _segment_text(self, text: str) -> List[str]:
        """
        简单的中文分词
        
        Args:
            text: 文本
            
        Returns:
            分词结果
        """
        # 使用正则提取中文词汇
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        
        # 过滤停用词
        words = [w for w in words if w not in self.stopwords and len(w) >= 2]
        
        return words
    
    def extract_keywords(self, ts_code: str, name: str) -> Dict:
        """
        提取单个股票的所有关键词
        
        Args:
            ts_code: 股票代码
            name: 股票名称
            
        Returns:
            关键词字典
        """
        all_keywords = []
        sources = {}
        
        # 1. 从名称提取
        name_keywords = self.extract_from_name(name)
        all_keywords.extend(name_keywords)
        sources['名称'] = name_keywords
        
        # 2. 从主营业务提取
        business_keywords = self.extract_from_business(ts_code)
        all_keywords.extend(business_keywords)
        sources['主营业务'] = business_keywords
        
        # 3. 从概念提取（可选，较慢）
        # concept_keywords = self.extract_from_concepts(ts_code)
        # all_keywords.extend(concept_keywords)
        # sources['概念'] = concept_keywords
        
        # 去重
        all_keywords = list(set(all_keywords))
        
        return {
            'ts_code': ts_code,
            'name': name,
            'keywords': all_keywords,
            'sources': sources,
            'keyword_count': len(all_keywords),
        }
    
    def calculate_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """
        计算两组关键词的相似度
        
        Args:
            keywords1: 关键词列表1
            keywords2: 关键词列表2
            
        Returns:
            相似度 (0-1)
        """
        if not keywords1 or not keywords2:
            return 0.0
        
        set1 = set(keywords1)
        set2 = set(keywords2)
        
        # Jaccard 相似度
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def cluster_stocks(self, stocks_keywords: List[Dict], min_similarity: float = 0.3) -> List[List[Dict]]:
        """
        基于关键词相似度聚类股票
        
        Args:
            stocks_keywords: 股票关键词列表
            min_similarity: 最小相似度阈值
            
        Returns:
            聚类结果
        """
        n = len(stocks_keywords)
        if n == 0:
            return []
        
        # 构建相似度矩阵
        similarity_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                sim = self.calculate_similarity(
                    stocks_keywords[i]['keywords'],
                    stocks_keywords[j]['keywords']
                )
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim
        
        # 简单的连通分量聚类
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # BFS 找连通分量
            cluster = []
            queue = [i]
            visited[i] = True
            
            while queue:
                curr = queue.pop(0)
                cluster.append(stocks_keywords[curr])
                
                for j in range(n):
                    if not visited[j] and similarity_matrix[curr][j] >= min_similarity:
                        visited[j] = True
                        queue.append(j)
            
            if cluster:
                clusters.append(cluster)
        
        # 按簇大小排序
        clusters.sort(key=lambda x: len(x), reverse=True)
        
        return clusters
    
    def analyze_limit_up_keywords(self, trade_date: Optional[str] = None) -> Dict:
        """
        分析当日涨停股的关键词
        
        Args:
            trade_date: 交易日期
            
        Returns:
            分析结果
        """
        if trade_date is None:
            trade_date = self.fetcher.get_latest_trade_date()
        
        logger.info(f"分析 {trade_date} 涨停股关键词...")
        
        # 获取涨停股
        limit_df = self.fetcher.get_limit_up_data(trade_date)
        if limit_df.empty:
            logger.warning("当日无涨停股")
            return {}
        
        logger.info(f"获取到 {len(limit_df)} 只涨停股")
        
        # 提取每只股票的关键词
        stocks_keywords = []
        for _, row in limit_df.iterrows():
            ts_code = row['ts_code']
            name = row['name']
            
            logger.debug(f"提取 {name} ({ts_code}) 的关键词...")
            
            keyword_info = self.extract_keywords(ts_code, name)
            keyword_info['limit_days'] = row.get('limit_days', 1)
            keyword_info['pct_chg'] = row.get('pct_chg', 0)
            
            stocks_keywords.append(keyword_info)
        
        # 聚类
        logger.info("开始聚类分析...")
        clusters = self.cluster_stocks(stocks_keywords, min_similarity=0.2)
        
        # 统计热门关键词
        all_keywords = []
        for sk in stocks_keywords:
            all_keywords.extend(sk['keywords'])
        
        keyword_counter = Counter(all_keywords)
        top_keywords = keyword_counter.most_common(20)
        
        return {
            'trade_date': trade_date,
            'total_stocks': len(limit_df),
            'stocks_keywords': stocks_keywords,
            'clusters': clusters,
            'top_keywords': top_keywords,
        }


def main():
    """测试关键词提取"""
    try:
        extractor = KeywordExtractor()
        
        # 分析涨停股关键词
        result = extractor.analyze_limit_up_keywords()
        
        if not result:
            print("无数据")
            return
        
        print("\n" + "="*70)
        print(f"涨停关键词分析报告 - {result['trade_date']}")
        print("="*70)
        
        # 热门关键词
        print(f"\n【热门关键词 TOP10】")
        for i, (keyword, count) in enumerate(result['top_keywords'][:10], 1):
            print(f"  {i}. {keyword}: {count}次")
        
        # 聚类结果
        print(f"\n【聚类分组】")
        for i, cluster in enumerate(result['clusters'][:5], 1):
            print(f"\n  组{i} ({len(cluster)}只股票):")
            
            # 提取该组的核心关键词
            cluster_keywords = []
            for stock in cluster:
                cluster_keywords.extend(stock['keywords'])
            cluster_top = Counter(cluster_keywords).most_common(3)
            
            print(f"    核心关键词: {', '.join([k for k, _ in cluster_top])}")
            
            for stock in cluster[:5]:  # 只显示前5只
                print(f"    - {stock['name']} ({stock['ts_code']}): {', '.join(stock['keywords'][:5])}")
            
            if len(cluster) > 5:
                print(f"    ... 还有 {len(cluster) - 5} 只")
        
        print("\n" + "="*70)
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
