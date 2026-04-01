#!/usr/bin/env python3
"""
巨潮资讯网公告爬虫 - Neo量化研究体系
爬取股票公告标题
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cninfo_notices(stock_code, max_retries=3):
    """
    从巨潮资讯网获取公告标题
    
    Args:
        stock_code: 股票代码
        max_retries: 最大重试次数
        
    Returns:
        公告标题列表
    """
    # 计算10天前的日期（过去10天）
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    # 巨潮资讯网API
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # 确定市场类型
    if stock_code.startswith('6'):
        column = 'sse'
        plate = 'sh'
    elif stock_code.startswith('0') or stock_code.startswith('3'):
        column = 'szse'
        plate = 'sz'
    elif stock_code.startswith('68'):
        column = 'sse'
        plate = 'sh'
    elif stock_code.startswith('8') or stock_code.startswith('4'):
        column = 'neeq'
        plate = 'bj'
    else:
        column = 'szse'
        plate = 'sz'
    
    payload = {
        'pageNum': '1',
        'pageSize': '30',
        'tabName': 'fulltext',
        'column': column,
        'stock': stock_code,
        'searchkey': '',
        'secid': '',
        'plate': plate,
        'category': 'category_all',
        'trade': '',
        'columnTitle': '历年公告',
        'seDate': f"{start_date}~{end_date}",
        'sortName': '',
        'sortType': '',
        'limit': '',
        'showTitle': '',
        'isHLtitle': 'true'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"{stock_code} 请求失败: {response.status_code}")
                time.sleep(1)
                continue
            
            data = response.json()
            
            if 'announcements' not in data or not data['announcements']:
                return []
            
            # 提取公告标题
            titles = []
            for item in data['announcements']:
                title = item.get('announcementTitle', '').strip()
                if title:
                    titles.append(title)
            
            return titles
            
        except Exception as e:
            logger.warning(f"{stock_code} 获取失败 (尝试 {attempt+1}/{max_retries}): {e}")
            time.sleep(1)
    
    return []


def add_notices_to_excel(input_path, output_path):
    """
    为Excel中的股票添加公告标题
    
    Args:
        input_path: 输入Excel路径
        output_path: 输出Excel路径
    """
    # 读取股票列表
    df = pd.read_excel(input_path)
    logger.info(f"读取到 {len(df)} 只股票")
    
    # 确保代码列为字符串
    df['代码'] = df['代码'].astype(str).str.replace('.0', '', regex=False)
    
    # 为每只股票获取公告
    notices_list = []
    
    for idx, row in df.iterrows():
        code = row['代码']
        name = row['名称']
        
        logger.info(f"[{idx+1}/{len(df)}] 获取 {code} {name} 的公告...")
        
        titles = get_cninfo_notices(code)
        
        if titles:
            # 取前5条公告标题
            titles_str = ' | '.join(titles[:5])
        else:
            titles_str = '无近期公告'
        
        notices_list.append({
            '代码': code,
            '近10天公告标题': titles_str
        })
        
        # 延时，避免请求过快
        time.sleep(0.5)
    
    # 创建DataFrame
    notices_df = pd.DataFrame(notices_list)
    
    # 合并到原数据
    df_with_notices = df.merge(notices_df, on='代码', how='left')
    
    # 保存
    df_with_notices.to_excel(output_path, index=False, engine='xlsxwriter')
    logger.info(f"已保存: {output_path}")
    
    # 统计
    success_count = len([n for n in notices_list if n['近10天公告标题'] != '无近期公告'])
    logger.info(f"成功获取公告: {success_count}/{len(df)} 只")
    
    return df_with_notices


if __name__ == '__main__':
    input_path = '/Users/mac/.openclaw/workspace-neo/data/smallcap/20260311/smallcap_screening_filtered.xlsx'
    output_path = '/Users/mac/Desktop/小市值强势股_含公告标题.xlsx'
    
    add_notices_to_excel(input_path, output_path)
