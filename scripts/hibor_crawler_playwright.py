#!/usr/bin/env python3
"""
慧博投研公告爬虫 - 使用Playwright
爬取股票公告标题
"""

import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_hibor_notices(page, stock_code, stock_name):
    """
    从慧博投研获取公告
    
    Args:
        page: Playwright page对象
        stock_code: 股票代码
        stock_name: 股票名称
        
    Returns:
        公告标题列表
    """
    try:
        # 访问慧博搜索页面
        search_url = f"https://www.hibor.com.cn/search?keyword={stock_code}"
        
        logger.info(f"访问: {search_url}")
        await page.goto(search_url, wait_until="networkidle", timeout=30000)
        
        # 等待页面加载
        await page.wait_for_timeout(2000)
        
        # 查找公告标签或链接
        # 慧博的搜索结果页面可能有"公司公告"筛选
        notice_tab = await page.query_selector('text=公司公告')
        if notice_tab:
            await notice_tab.click()
            await page.wait_for_timeout(2000)
        
        # 提取公告标题
        # 尝试多种选择器
        selectors = [
            '.list-item .title',
            '.report-item .title',
            '.search-item .title',
            'a[href*="/data/"]',
            '.title a'
        ]
        
        titles = []
        for selector in selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                for elem in elements[:5]:  # 取前5条
                    text = await elem.text_content()
                    if text and stock_code in text:
                        titles.append(text.strip())
                if titles:
                    break
        
        return titles
        
    except Exception as e:
        logger.error(f"获取 {stock_code} 公告失败: {e}")
        return []


async def crawl_notices():
    """爬取所有股票的公告"""
    
    # 读取股票列表
    input_path = '/Users/mac/.openclaw/workspace-neo/data/smallcap/20260311/smallcap_screening_filtered.xlsx'
    df = pd.read_excel(input_path)
    
    logger.info(f"处理 {len(df)} 只股票...")
    
    # 确保代码列为字符串
    df['代码'] = df['代码'].astype(str).str.replace('.0', '', regex=False)
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # 为每只股票获取公告
        notices_list = []
        
        for idx, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            
            logger.info(f"[{idx+1}/{len(df)}] 获取 {code} {name} 的公告...")
            
            titles = await get_hibor_notices(page, code, name)
            
            if titles:
                titles_str = ' | '.join(titles[:3])
            else:
                titles_str = '无近期公告'
            
            notices_list.append({
                '代码': code,
                '近10天公告标题': titles_str
            })
            
            # 延时，避免请求过快
            await asyncio.sleep(1)
        
        # 关闭浏览器
        await browser.close()
    
    # 创建DataFrame
    notices_df = pd.DataFrame(notices_list)
    
    # 合并到原数据
    df_with_notices = df.merge(notices_df, on='代码', how='left')
    
    # 保存
    output_path = '/Users/mac/Desktop/小市值强势股_含公告标题.xlsx'
    df_with_notices.to_excel(output_path, index=False, engine='xlsxwriter')
    
    logger.info(f"已保存: {output_path}")
    
    # 统计
    success_count = len([n for n in notices_list if n['近10天公告标题'] != '无近期公告'])
    logger.info(f"成功获取公告: {success_count}/{len(df)} 只")


if __name__ == '__main__':
    asyncio.run(crawl_notices())
