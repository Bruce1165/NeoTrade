#!/usr/bin/env python3
"""
新闻抓取模块 - News Fetcher

功能：
- 从新浪财经抓取个股新闻
- 缓存机制：新闻数据缓存24小时
- 支持批量获取
"""

# 清除代理环境变量，避免网络请求失败
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import requests
import json
import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = "data/news_cache"
CACHE_EXPIRY_HOURS = 24

# 新浪财经API
SINA_NEWS_API = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php"
SINA_NEWS_LIST = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsSearch.php"


class NewsCache:
    """新闻缓存管理"""
    
    def __init__(self, cache_dir: str = CACHE_DIR, expiry_hours: int = CACHE_EXPIRY_HOURS):
        self.cache_dir = cache_dir
        self.expiry_hours = expiry_hours
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, stock_code: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"news_{stock_code}".encode()).hexdigest()
    
    def _get_cache_path(self, stock_code: str) -> str:
        """获取缓存文件路径"""
        cache_key = self._get_cache_key(stock_code)
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, stock_code: str) -> Optional[List[Dict]]:
        """获取缓存的新闻"""
        cache_path = self._get_cache_path(stock_code)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查是否过期
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cached_time > timedelta(hours=self.expiry_hours):
                return None
            
            return cache_data['news']
        except Exception as e:
            logger.warning(f"Error reading cache for {stock_code}: {e}")
            return None
    
    def set(self, stock_code: str, news: List[Dict]):
        """设置缓存"""
        cache_path = self._get_cache_path(stock_code)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'stock_code': stock_code,
                'news': news
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error writing cache for {stock_code}: {e}")
    
    def clear_expired(self):
        """清理过期缓存"""
        try:
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith('.json'):
                    continue
                
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    cached_time = datetime.fromisoformat(cache_data['timestamp'])
                    if datetime.now() - cached_time > timedelta(hours=self.expiry_hours):
                        os.remove(filepath)
                        logger.debug(f"Removed expired cache: {filename}")
                except:
                    pass
        except Exception as e:
            logger.warning(f"Error clearing expired cache: {e}")


class NewsFetcher:
    """新闻抓取器"""
    
    def __init__(self, cache_dir: str = CACHE_DIR, cache_expiry_hours: int = CACHE_EXPIRY_HOURS):
        self.cache = NewsCache(cache_dir, cache_expiry_hours)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    
    def _format_stock_code(self, code: str) -> str:
        """格式化股票代码"""
        code = str(code).strip()
        
        # 如果已经有前缀，直接返回
        if code.startswith(('sh', 'sz', 'bj')):
            return code
        
        # 根据代码判断交易所
        if code.startswith('6'):
            return f"sh{code}"
        elif code.startswith(('0', '3')):
            return f"sz{code}"
        elif code.startswith(('4', '8')):
            return f"bj{code}"
        elif code.startswith('68'):
            return f"sh{code}"
        else:
            # 默认上海
            return f"sh{code}"
    
    def fetch_news_sina(self, stock_code: str, max_news: int = 10) -> List[Dict]:
        """
        从新浪财经抓取新闻
        
        Args:
            stock_code: 股票代码
            max_news: 最大新闻数量
        
        Returns:
            新闻列表
        """
        formatted_code = self._format_stock_code(stock_code)
        
        try:
            # 新浪财经新闻列表页
            url = f"https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsSearch.php?stockid={stock_code}&Page=1"
            
            response = self.session.get(url, timeout=10)
            response.encoding = 'gb2312'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_list = []
            
            # 查找新闻表格
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # 提取新闻标题和链接
                        link_cell = cells[0]
                        date_cell = cells[1] if len(cells) > 1 else None
                        
                        link_elem = link_cell.find('a')
                        if link_elem:
                            title = link_elem.get_text(strip=True)
                            href = link_elem.get('href', '')
                            
                            # 提取日期
                            date_str = ''
                            if date_cell:
                                date_str = date_cell.get_text(strip=True)
                            
                            if title and len(title) > 5:  # 过滤掉无效条目
                                news_list.append({
                                    'title': title,
                                    'url': href if href.startswith('http') else f"https://vip.stock.finance.sina.com.cn{href}",
                                    'date': date_str,
                                    'source': '新浪财经'
                                })
            
            # 去重并限制数量
            seen_titles = set()
            unique_news = []
            for news in news_list:
                if news['title'] not in seen_titles:
                    seen_titles.add(news['title'])
                    unique_news.append(news)
            
            return unique_news[:max_news]
            
        except Exception as e:
            logger.error(f"Error fetching news for {stock_code} from Sina: {e}")
            return []
    
    def fetch_news_eastmoney(self, stock_code: str, max_news: int = 10) -> List[Dict]:
        """
        从东方财富抓取新闻（备用源）
        
        Args:
            stock_code: 股票代码
            max_news: 最大新闻数量
        
        Returns:
            新闻列表
        """
        try:
            # 东方财富新闻API
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={stock_code}&type=14&count=1"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if not data.get('QuotationCodeTable', {}).get('Data', []):
                return []
            
            stock_info = data['QuotationCodeTable']['Data'][0]
            security_code = stock_info.get('SecurityCode', '')
            
            # 获取新闻列表
            news_url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size={max_news}&page_index=1&ann_type=A&client_source=web&stock_code={security_code}"
            
            news_response = self.session.get(news_url, timeout=10)
            news_data = news_response.json()
            
            news_list = []
            for item in news_data.get('data', {}).get('list', []):
                news_list.append({
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'date': item.get('notice_date', ''),
                    'source': '东方财富'
                })
            
            return news_list
            
        except Exception as e:
            logger.error(f"Error fetching news for {stock_code} from Eastmoney: {e}")
            return []
    
    def get_news(self, stock_code: str, max_news: int = 10, use_cache: bool = True) -> List[Dict]:
        """
        获取股票新闻（带缓存）
        
        Args:
            stock_code: 股票代码
            max_news: 最大新闻数量
            use_cache: 是否使用缓存
        
        Returns:
            新闻列表
        """
        # 检查缓存
        if use_cache:
            cached_news = self.cache.get(stock_code)
            if cached_news is not None:
                logger.debug(f"Using cached news for {stock_code}")
                return cached_news[:max_news]
        
        # 抓取新闻
        news = self.fetch_news_sina(stock_code, max_news)
        
        # 如果新浪财经没有数据，尝试东方财富
        if not news:
            news = self.fetch_news_eastmoney(stock_code, max_news)
        
        # 保存缓存
        if use_cache and news:
            self.cache.set(stock_code, news)
        
        return news
    
    def get_news_batch(self, stock_codes: List[str], max_news: int = 10, 
                       use_cache: bool = True, delay: float = 0.5) -> Dict[str, List[Dict]]:
        """
        批量获取股票新闻
        
        Args:
            stock_codes: 股票代码列表
            max_news: 每个股票的最大新闻数量
            use_cache: 是否使用缓存
            delay: 请求间隔（秒）
        
        Returns:
            字典：{stock_code: news_list}
        """
        results = {}
        
        for i, code in enumerate(stock_codes):
            results[code] = self.get_news(code, max_news, use_cache)
            
            # 添加延迟避免请求过快
            if delay > 0 and i < len(stock_codes) - 1:
                time.sleep(delay)
        
        return results
    
    def get_news_summary(self, stock_code: str, max_news: int = 5) -> str:
        """
        获取新闻摘要（用于LLM分析）
        
        Args:
            stock_code: 股票代码
            max_news: 最大新闻数量
        
        Returns:
            新闻摘要文本
        """
        news_list = self.get_news(stock_code, max_news)
        
        if not news_list:
            return "暂无相关新闻"
        
        summary_parts = []
        for i, news in enumerate(news_list, 1):
            date_str = f"[{news.get('date', '未知日期')}]" if news.get('date') else ""
            summary_parts.append(f"{i}. {date_str} {news['title']}")
        
        return "\n".join(summary_parts)


# 便捷函数
def get_news(stock_code: str, max_news: int = 10, use_cache: bool = True) -> List[Dict]:
    """便捷函数：获取单只股票新闻"""
    fetcher = NewsFetcher()
    return fetcher.get_news(stock_code, max_news, use_cache)


def get_news_batch(stock_codes: List[str], max_news: int = 10, 
                   use_cache: bool = True) -> Dict[str, List[Dict]]:
    """便捷函数：批量获取新闻"""
    fetcher = NewsFetcher()
    return fetcher.get_news_batch(stock_codes, max_news, use_cache)


def get_news_summary(stock_code: str, max_news: int = 5) -> str:
    """便捷函数：获取新闻摘要"""
    fetcher = NewsFetcher()
    return fetcher.get_news_summary(stock_code, max_news)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    fetcher = NewsFetcher()
    
    # 测试单只股票
    test_code = "600519"  # 贵州茅台
    print(f"\nFetching news for {test_code}...")
    news = fetcher.get_news(test_code, max_news=5)
    
    for item in news:
        print(f"[{item['date']}] {item['title']}")
    
    # 测试批量获取
    print("\n\nBatch fetching...")
    batch_results = fetcher.get_news_batch(["600519", "000001"], max_news=3)
    for code, news_list in batch_results.items():
        print(f"\n{code}: {len(news_list)} news")
