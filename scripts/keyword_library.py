#!/usr/bin/env python3
"""
关键词库管理系统 - Neo量化研究体系
维护核心关键词库，支持动态更新和关联分析
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeywordLibrary:
    """关键词库管理器"""
    
    def __init__(self, library_path: Optional[str] = None):
        """
        初始化关键词库
        
        Args:
            library_path: 关键词库文件路径
        """
        if library_path is None:
            library_path = '/Users/mac/.openclaw/workspace-neo/data/keyword_library.json'
        
        self.library_path = Path(library_path)
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载或初始化关键词库
        self.library = self._load_library()
        
        # 股票-关键词映射缓存
        self.stock_keyword_map = {}  # {ts_code: {keywords}}
        
        logger.info("关键词库管理器初始化完成")
    
    def _load_library(self) -> Dict:
        """加载关键词库"""
        if self.library_path.exists():
            try:
                with open(self.library_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载关键词库失败: {e}")
        
        # 初始化默认关键词库
        return self._init_default_library()
    
    def _init_default_library(self) -> Dict:
        """初始化默认关键词库"""
        library = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'categories': {
                'industry': {  # 行业关键词
                    '半导体': ['芯片', '半导体', '集成电路', '晶圆', '光刻', 'EDA', '存储', 'CPU', 'GPU', 'AI芯片', '先进封装', 'Chiplet'],
                    '新能源': ['光伏', '风电', '储能', '锂电池', '氢能', '核电', '清洁能源', '逆变器', '钙钛矿', 'TOPCon'],
                    '新能源汽车': ['电动车', '动力电池', '充电桩', '自动驾驶', '智能座舱', '整车', '一体化压铸', '800V高压', 'SiC碳化硅'],
                    '人工智能': ['AI', '大模型', '算力', '算法', '机器学习', '计算机视觉', 'NLP', 'AIGC', '多模态', 'Transformer'],
                    '机器人': ['人形机器人', '减速器', '丝杠', '传感器', '灵巧手', '电机', '工业机器人', '谐波减速器', 'RV减速器', '无框力矩电机'],
                    '医药': ['创新药', 'CXO', '医疗器械', '生物制药', '中药', '疫苗', '基因', 'CRO', 'GLP-1', 'ADC药物'],
                    '军工': ['航空航天', '船舶', '兵器', '雷达', '导弹', '军民融合', '卫星', '北斗导航', '隐身材料'],
                    '通信': ['5G', '6G', '光通信', '光纤', '基站', '通信设备', '卫星通信', '光模块', 'CPO', 'LPO'],
                    '金融': ['银行', '保险', '证券', '信托', '金融科技', '数字货币', '支付', '跨境支付', '金融IT'],
                    '地产': ['房地产', '物业管理', '建材', '装修', '家居', '基建', '装配式建筑'],
                    '消费': ['白酒', '食品', '家电', '零售', '餐饮', '旅游', '免税', '预制菜', '宠物经济'],
                    '周期': ['煤炭', '钢铁', '有色', '化工', '石油', '航运', '稀土', '贵金属', '工业金属'],
                    '传媒': ['游戏', '影视', '广告', '出版', '短视频', '直播', '短剧', 'IP经济'],
                    '电力': ['火电', '水电', '核电', '风电', '光伏', '电网', '特高压', '虚拟电厂', '智能电网'],
                    '数据中心': ['IDC', '服务器', '液冷', '算力中心', '云计算', '边缘计算'],
                },
                'concept': {  # 概念关键词
                    '新质生产力': ['机器人', '工业母机', '3D打印', '智能制造', '工业互联网'],
                    '设备更新': ['机床', '工程机械', '农机', '医疗设备', '教育设备'],
                    '以旧换新': ['家电', '汽车', '消费电子'],
                    '低空经济': ['无人机', 'eVTOL', '通航', '空管', '卫星导航', '飞行汽车'],
                    '固态电池': ['固态电解质', '锂金属', '凝聚态', '快充', '半固态'],
                    '数据要素': ['数据确权', '数据交易', '数据安全', '大数据', '云计算'],
                    '国产替代': ['信创', '操作系统', '数据库', '办公软件', '工业软件', '光刻机'],
                    '一带一路': ['海外工程', '港口', '铁路', '基建出海'],
                    '碳中和': ['碳交易', '碳捕捉', '节能减排', '绿电'],
                    '元宇宙': ['VR', 'AR', '虚拟现实', '数字孪生', 'NFT'],
                    # 用户新增概念
                    '算电协同': ['算力', '电力', '数据中心', '绿电', '东数西算'],
                    '液冷超充': ['液冷', '超充', '充电桩', '快充', '热管理'],
                    '光模块': ['CPO', 'LPO', '光芯片', '800G', '1.6T'],
                    '无人驾驶': ['自动驾驶', '激光雷达', '高精地图', '车路协同', '智能座舱'],
                    '锂矿': ['锂资源', '盐湖提锂', '锂辉石', '碳酸锂', '氢氧化锂'],
                    '氢能': ['氢燃料电池', '电解槽', '储氢', '加氢站', '绿氢'],
                    '云计算': ['公有云', '私有云', '混合云', 'SaaS', 'PaaS'],
                    '边缘计算': ['MEC', '边缘节点', '边缘服务器', '5G边缘'],
                    '脑机接口': ['BCI', '神经接口', '植入式', '非植入式', '医疗康复'],
                },
                'theme': {  # 主题/事件关键词
                    '业绩预增': ['净利润增长', '扭亏为盈', '超预期', '年报增长'],
                    '并购重组': ['收购', '重组', '借壳', '资产注入', '股权转让'],
                    '订单公告': ['中标', '大单', '合同', '框架协议'],
                    '技术突破': ['专利', '新品发布', '量产', '认证'],
                    '政策利好': ['补贴', '扶持', '规划', '试点'],
                }
            },
            'keyword_stats': {},  # 关键词统计 {keyword: {count, last_date, stocks}}
            'stock_keywords': {},  # 股票关键词历史 {ts_code: {keywords, dates}}
        }
        
        self._save_library(library)
        logger.info("初始化默认关键词库")
        return library
    
    def _save_library(self, library: Dict = None):
        """保存关键词库"""
        if library is None:
            library = self.library
        
        library['updated_at'] = datetime.now().isoformat()
        
        with open(self.library_path, 'w', encoding='utf-8') as f:
            json.dump(library, f, ensure_ascii=False, indent=2)
        
        logger.info(f"关键词库已保存: {self.library_path}")
    
    def extract_keywords(self, name: str, ts_code: str = '', 
                         business: str = '', concepts: List[str] = None) -> Set[str]:
        """
        从股票信息中提取关键词
        
        Args:
            name: 股票名称
            ts_code: 股票代码
            business: 主营业务
            concepts: 所属概念列表
            
        Returns:
            关键词集合
        """
        keywords = set()
        text = f"{name} {business} {' '.join(concepts or [])}"
        
        # 遍历所有类别匹配关键词
        for category in self.library['categories'].values():
            for main_keyword, sub_keywords in category.items():
                # 检查主关键词
                if main_keyword in text:
                    keywords.add(main_keyword)
                
                # 检查子关键词
                for sub in sub_keywords:
                    if sub in text:
                        keywords.add(sub)
                        keywords.add(main_keyword)  # 同时添加主分类
        
        # 特殊规则：从名称提取
        name_keywords = self._extract_from_name(name)
        keywords.update(name_keywords)
        
        return keywords
    
    def _extract_from_name(self, name: str) -> Set[str]:
        """从名称提取关键词"""
        keywords = set()
        
        # 常见业务词映射
        name_mapping = {
            '科技': ['科技', '技术'],
            '智能': ['人工智能', '智能制造'],
            '电子': ['电子', '半导体'],
            '通信': ['通信', '5G'],
            '医药': ['医药', '医疗'],
            '生物': ['生物医药', '生物技术'],
            '环保': ['环保', '新能源'],
            '能源': ['能源', '电力'],
            '材料': ['新材料', '化工'],
            '精工': ['精密制造', '工业'],
            '数控': ['数控机床', '工业母机'],
            '光学': ['光学', '光通信'],
            '数据': ['大数据', '数据要素'],
            '云': ['云计算', '云服务'],
        }
        
        for key, values in name_mapping.items():
            if key in name:
                keywords.update(values)
        
        return keywords
    
    def update_stats(self, date: str, stocks_data: List[Dict]):
        """
        更新关键词统计
        
        Args:
            date: 日期 (YYYYMMDD)
            stocks_data: 股票数据列表 [{ts_code, name, keywords, limit_days}]
        """
        keyword_counter = Counter()
        keyword_stocks = defaultdict(set)
        
        for stock in stocks_data:
            ts_code = stock['ts_code']
            keywords = stock.get('keywords', set())
            
            # 更新股票关键词历史
            if ts_code not in self.library['stock_keywords']:
                self.library['stock_keywords'][ts_code] = {
                    'name': stock.get('name', ''),
                    'keywords': list(keywords),
                    'dates': [date]
                }
            else:
                # 合并关键词
                existing = set(self.library['stock_keywords'][ts_code]['keywords'])
                existing.update(keywords)
                self.library['stock_keywords'][ts_code]['keywords'] = list(existing)
                if date not in self.library['stock_keywords'][ts_code]['dates']:
                    self.library['stock_keywords'][ts_code]['dates'].append(date)
            
            # 统计关键词
            for kw in keywords:
                keyword_counter[kw] += 1
                keyword_stocks[kw].add(ts_code)
        
        # 更新全局统计
        for kw, count in keyword_counter.items():
            if kw not in self.library['keyword_stats']:
                self.library['keyword_stats'][kw] = {
                    'total_count': 0,
                    'daily_counts': {},
                    'stocks': list(keyword_stocks[kw])
                }
            
            self.library['keyword_stats'][kw]['total_count'] += count
            self.library['keyword_stats'][kw]['daily_counts'][date] = count
            self.library['keyword_stats'][kw]['stocks'] = list(keyword_stocks[kw])
        
        self._save_library()
        logger.info(f"更新关键词统计完成: {date}, {len(stocks_data)}只股票")
    
    def get_hot_keywords(self, date: Optional[str] = None, top_n: int = 20) -> List[Tuple[str, int]]:
        """
        获取热门关键词
        
        Args:
            date: 日期，默认所有时间
            top_n: 返回前N个
            
        Returns:
            [(keyword, count), ...]
        """
        if date:
            # 获取指定日期的热门关键词
            counts = []
            for kw, stats in self.library['keyword_stats'].items():
                if date in stats['daily_counts']:
                    counts.append((kw, stats['daily_counts'][date]))
        else:
            # 获取所有时间的热门关键词
            counts = [(kw, stats['total_count']) 
                     for kw, stats in self.library['keyword_stats'].items()]
        
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:top_n]
    
    def get_related_stocks(self, keyword: str) -> List[Dict]:
        """
        获取与关键词相关的股票
        
        Args:
            keyword: 关键词
            
        Returns:
            股票列表
        """
        if keyword not in self.library['keyword_stats']:
            return []
        
        stocks = []
        for ts_code in self.library['keyword_stats'][keyword]['stocks']:
            if ts_code in self.library['stock_keywords']:
                info = self.library['stock_keywords'][ts_code]
                stocks.append({
                    'ts_code': ts_code,
                    'name': info['name'],
                    'keywords': info['keywords'],
                    'dates': info['dates']
                })
        
        return stocks
    
    def get_keyword_trend(self, keyword: str, days: int = 30) -> List[Tuple[str, int]]:
        """
        获取关键词趋势
        
        Args:
            keyword: 关键词
            days: 最近N天
            
        Returns:
            [(date, count), ...]
        """
        if keyword not in self.library['keyword_stats']:
            return []
        
        daily_counts = self.library['keyword_stats'][keyword]['daily_counts']
        sorted_dates = sorted(daily_counts.keys())[-days:]
        
        return [(date, daily_counts[date]) for date in sorted_dates]
    
    def add_custom_keyword(self, category: str, main_keyword: str, sub_keywords: List[str]):
        """
        添加自定义关键词
        
        Args:
            category: 类别 (industry/concept/theme)
            main_keyword: 主关键词
            sub_keywords: 子关键词列表
        """
        if category not in self.library['categories']:
            self.library['categories'][category] = {}
        
        if main_keyword in self.library['categories'][category]:
            # 合并子关键词
            existing = set(self.library['categories'][category][main_keyword])
            existing.update(sub_keywords)
            self.library['categories'][category][main_keyword] = list(existing)
        else:
            self.library['categories'][category][main_keyword] = sub_keywords
        
        self._save_library()
        logger.info(f"添加自定义关键词: {category}/{main_keyword}")
    
    def export_report(self, date: str) -> Dict:
        """
        导出关键词报告
        
        Args:
            date: 日期
            
        Returns:
            报告字典
        """
        hot_keywords = self.get_hot_keywords(date, top_n=20)
        
        # 分类统计
        category_stats = defaultdict(list)
        for kw, count in hot_keywords:
            for cat_name, cat_data in self.library['categories'].items():
                for main_kw, sub_kws in cat_data.items():
                    if kw == main_kw or kw in sub_kws:
                        category_stats[cat_name].append((kw, count))
                        break
        
        return {
            'date': date,
            'hot_keywords': hot_keywords,
            'category_stats': dict(category_stats),
            'total_keywords': len(self.library['keyword_stats']),
            'total_stocks': len(self.library['stock_keywords']),
        }


def main():
    """测试关键词库"""
    lib = KeywordLibrary()
    
    print("="*80)
    print("关键词库测试")
    print("="*80)
    
    # 测试提取关键词
    test_cases = [
        ('宁德时代', '300750.SZ', '动力电池、储能系统', ['锂电池', '新能源车']),
        ('中科曙光', '603019.SH', '服务器、超算', ['算力', 'AI', '信创']),
        ('东方财富', '300059.SZ', '互联网金融', ['券商', '金融科技']),
    ]
    
    print("\n【关键词提取测试】")
    for name, code, business, concepts in test_cases:
        keywords = lib.extract_keywords(name, code, business, concepts)
        print(f"\n{name} ({code}):")
        print(f"  关键词: {', '.join(keywords)}")
    
    # 显示关键词库结构
    print("\n" + "="*80)
    print("关键词库结构")
    print("="*80)
    
    for cat_name, cat_data in lib.library['categories'].items():
        print(f"\n【{cat_name}】共 {len(cat_data)} 个主分类")
        for main_kw, sub_kws in list(cat_data.items())[:3]:
            print(f"  {main_kw}: {', '.join(sub_kws[:5])}")
        if len(cat_data) > 3:
            print(f"  ... 还有 {len(cat_data) - 3} 个")
    
    print("\n" + "="*80)
    print(f"关键词库已保存: {lib.library_path}")
    print("="*80)


if __name__ == '__main__':
    main()
