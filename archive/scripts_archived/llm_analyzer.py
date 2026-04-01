#!/usr/bin/env python3
"""
LLM分析模块 - LLM Analyzer

功能：
- 分析个股上涨原因（基于新闻 + 价格走势）
- 推断行业分类（基于股票名称 + 新闻）
- 识别相关概念/板块
- 缓存机制避免重复分析
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = "data/llm_cache"
CACHE_EXPIRY_HOURS = 24

# 尝试导入OpenAI或其他LLM库
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available")


class LLMCache:
    """LLM分析结果缓存"""
    
    def __init__(self, cache_dir: str = CACHE_DIR, expiry_hours: int = CACHE_EXPIRY_HOURS):
        self.cache_dir = cache_dir
        self.expiry_hours = expiry_hours
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, stock_code: str, date_str: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{stock_code}_{date_str}".encode()).hexdigest()
    
    def _get_cache_path(self, stock_code: str, date_str: str) -> str:
        """获取缓存文件路径"""
        cache_key = self._get_cache_key(stock_code, date_str)
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, stock_code: str, date_str: str) -> Optional[Dict]:
        """获取缓存的分析结果"""
        cache_path = self._get_cache_path(stock_code, date_str)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查是否过期
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cached_time > timedelta(hours=self.expiry_hours):
                return None
            
            return cache_data['analysis']
        except Exception as e:
            logger.warning(f"Error reading LLM cache for {stock_code}: {e}")
            return None
    
    def set(self, stock_code: str, date_str: str, analysis: Dict):
        """设置缓存"""
        cache_path = self._get_cache_path(stock_code, date_str)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'stock_code': stock_code,
                'date': date_str,
                'analysis': analysis
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error writing LLM cache for {stock_code}: {e}")


class LLMAnalyzer:
    """LLM分析器"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: str = None, cache_dir: str = CACHE_DIR):
        """
        初始化LLM分析器
        
        Args:
            api_key: API密钥，默认从环境变量获取
            base_url: API基础URL
            model: 模型名称，默认从环境变量获取或使用系统默认
            cache_dir: 缓存目录
        """
        self.cache = LLMCache(cache_dir)
        
        # 获取模型名称，优先级：参数 > 环境变量 > 默认值
        self.model = model or os.getenv('DEFAULT_MODEL') or "moonshot/kimi-k2.5"
        
        # 初始化LLM客户端
        self.client = None
        if OPENAI_AVAILABLE:
            try:
                api_key = api_key or os.getenv('OPENAI_API_KEY')
                base_url = base_url or os.getenv('OPENAI_BASE_URL')
                
                if api_key and base_url:
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"LLM client initialized with model: {self.model}")
                else:
                    logger.warning("No API key or base_url provided for LLM")
            except Exception as e:
                logger.error(f"Error initializing LLM client: {e}")
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        if not self.client:
            logger.warning("LLM client not available")
            return ""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的股票分析师，擅长分析个股上涨原因、行业分类和概念板块。请用中文简洁回答。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return ""
    
    def analyze_stock(self, stock_code: str, stock_name: str, 
                      news_summary: str, price_data: Optional[Dict] = None,
                      date_str: Optional[str] = None, use_cache: bool = True) -> Dict:
        """
        分析单只股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            news_summary: 新闻摘要
            price_data: 价格数据（可选）
            date_str: 日期字符串（用于缓存）
            use_cache: 是否使用缓存
        
        Returns:
            分析结果字典
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # 检查缓存
        if use_cache:
            cached = self.cache.get(stock_code, date_str)
            if cached:
                logger.debug(f"Using cached analysis for {stock_code}")
                return cached
        
        # 如果没有LLM客户端，返回默认分析
        if not self.client:
            default_result = self._get_default_analysis(stock_name, news_summary)
            if use_cache:
                self.cache.set(stock_code, date_str, default_result)
            return default_result
        
        # 构建提示词
        price_info = ""
        if price_data:
            price_info = f"""
价格走势信息：
- 最近收盘价: {price_data.get('close', 'N/A')}
- 涨跌幅: {price_data.get('pct_change', 'N/A')}%
- 换手率: {price_data.get('turnover', 'N/A')}%
- 成交量变化: {price_data.get('volume_change', 'N/A')}
"""
        
        prompt = f"""请分析以下股票，提供JSON格式的分析结果：

股票代码: {stock_code}
股票名称: {stock_name}

相关新闻：
{news_summary}
{price_info}

请从以下几个维度分析上涨原因（可多选）：
1. 国家政策 - 如：政策利好、监管支持、产业扶持等
2. 国际环境 - 如：国际市场联动、汇率变化、地缘政治等
3. 突发事件 - 如：公司重大公告、行业突发事件、黑天鹅事件等
4. 相关行业带动 - 如：上下游产业链带动、龙头企业带动等
5. 所属行业推动 - 如：行业景气度提升、行业政策利好等
6. 技术形态 - 如：突破形态、资金流入、市场情绪等

请分析并返回以下字段（JSON格式）：
{{
    "上涨原因": "主要上涨原因，30字以内，请注明是哪个维度",
    "上涨维度": ["政策", "国际", "突发事件", "行业带动", "行业推动", "技术"],
    "行业分类": "主要行业分类，如：半导体、新能源汽车、医药等",
    "相关概念": "相关概念板块，用顿号分隔，如：人工智能、芯片、国产替代",
    "新闻摘要": "新闻核心内容摘要，30字以内",
    "分析置信度": "高/中/低"
}}

只返回JSON，不要其他内容。"""
        
        try:
            response = self._call_llm(prompt)
            
            # 解析JSON响应
            # 尝试提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)
            else:
                # 尝试直接解析
                analysis = json.loads(response)
            
            # 确保所有字段存在
            result = {
                '上涨原因': analysis.get('上涨原因', '技术形态突破'),
                '行业分类': analysis.get('行业分类', self._infer_industry(stock_name)),
                '相关概念': analysis.get('相关概念', ''),
                '新闻摘要': analysis.get('新闻摘要', news_summary[:50] if news_summary else ''),
                '分析置信度': analysis.get('分析置信度', '中'),
                '分析时间': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error parsing LLM response for {stock_code}: {e}")
            result = self._get_default_analysis(stock_name, news_summary)
        
        # 保存缓存
        if use_cache:
            self.cache.set(stock_code, date_str, result)
        
        return result
    
    def _get_default_analysis(self, stock_name: str, news_summary: str) -> Dict:
        """获取默认分析结果（当LLM不可用时）"""
        return {
            '上涨原因': '技术形态突破',
            '行业分类': self._infer_industry(stock_name),
            '相关概念': '',
            '新闻摘要': news_summary[:50] if news_summary else '暂无新闻',
            '分析置信度': '低',
            '分析时间': datetime.now().isoformat()
        }
    
    def _infer_industry(self, stock_name: str) -> str:
        """基于股票名称推断行业"""
        # 简单的行业关键词匹配
        industry_keywords = {
            '银行': '银行金融',
            '证券': '券商',
            '保险': '保险',
            '医药': '医药生物',
            '医疗': '医疗器械',
            '科技': '科技',
            '电子': '电子',
            '半导体': '半导体',
            '芯片': '半导体',
            '新能源': '新能源',
            '汽车': '汽车',
            '锂': '锂电池',
            '光伏': '光伏',
            '电力': '电力',
            '能源': '能源',
            '化工': '化工',
            '钢铁': '钢铁',
            '煤炭': '煤炭',
            '有色': '有色金属',
            '稀土': '稀土永磁',
            '地产': '房地产',
            '建筑': '建筑',
            '建材': '建材',
            '食品': '食品饮料',
            '饮料': '食品饮料',
            '白酒': '白酒',
            '家电': '家电',
            '纺织': '纺织服装',
            '航空': '航空',
            '运输': '交通运输',
            '物流': '物流',
            '通信': '通信',
            '5G': '5G通信',
            '人工智能': '人工智能',
            'AI': '人工智能',
            '机器人': '机器人',
            '军工': '国防军工',
            '航天': '航天航空',
            '环保': '环保',
            '农业': '农业',
            '养殖': '养殖',
            '传媒': '传媒',
            '游戏': '游戏',
            '互联网': '互联网',
        }
        
        for keyword, industry in industry_keywords.items():
            if keyword in stock_name:
                return industry
        
        return '其他'
    
    def analyze_batch(self, stocks_data: List[Dict], date_str: Optional[str] = None,
                      use_cache: bool = True, delay: float = 0.5) -> Dict[str, Dict]:
        """
        批量分析股票
        
        Args:
            stocks_data: 股票数据列表，每个元素包含code, name, news_summary等
            date_str: 日期字符串
            use_cache: 是否使用缓存
            delay: 请求间隔
        
        Returns:
            分析结果字典：{stock_code: analysis_result}
        """
        results = {}
        
        for i, stock_data in enumerate(stocks_data):
            code = stock_data['code']
            name = stock_data['name']
            news = stock_data.get('news_summary', '')
            price = stock_data.get('price_data', {})
            
            results[code] = self.analyze_stock(code, name, news, price, date_str, use_cache)
            
            if delay > 0 and i < len(stocks_data) - 1:
                import time
                time.sleep(delay)
        
        return results


# 便捷函数
def analyze_stock(stock_code: str, stock_name: str, news_summary: str,
                  price_data: Optional[Dict] = None, date_str: Optional[str] = None) -> Dict:
    """便捷函数：分析单只股票"""
    analyzer = LLMAnalyzer()
    return analyzer.analyze_stock(stock_code, stock_name, news_summary, price_data, date_str)


def analyze_batch(stocks_data: List[Dict], date_str: Optional[str] = None) -> Dict[str, Dict]:
    """便捷函数：批量分析"""
    analyzer = LLMAnalyzer()
    return analyzer.analyze_batch(stocks_data, date_str)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    analyzer = LLMAnalyzer()
    
    # 测试单只股票分析
    test_code = "600519"
    test_name = "贵州茅台"
    test_news = """
1. [2026-03-13] 贵州茅台发布2025年年报，净利润同比增长15%
2. [2026-03-12] 白酒板块整体走强，茅台领涨
3. [2026-03-10] 茅台推出新品，市场反响热烈
"""
    
    print(f"\nAnalyzing {test_code} {test_name}...")
    result = analyzer.analyze_stock(test_code, test_name, test_news)
    
    print("\n分析结果:")
    for key, value in result.items():
        print(f"  {key}: {value}")
