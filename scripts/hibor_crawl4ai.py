#!/opt/homebrew/bin/python3.11
"""
慧博投研公告爬虫 - 使用Crawl4AI
"""

import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import pandas as pd
from datetime import datetime
import json

async def get_hibor_notices(crawler, stock_code, stock_name):
    """
    从慧博投研获取公告
    
    Args:
        crawler: Crawl4AI crawler对象
        stock_code: 股票代码
        stock_name: 股票名称
        
    Returns:
        公告标题列表
    """
    try:
        # 慧博搜索页面
        url = f"https://www.hibor.com.cn/search?keyword={stock_code}"
        
        print(f"  爬取: {url}")
        
        result = await crawler.arun(
            url=url,
            wait_for="css:.search-result",
            timeout=30
        )
        
        if result.success:
            # 从markdown中提取公告标题
            content = result.markdown
            
            # 查找包含股票代码和"公告"的行
            lines = content.split('\n')
            notices = []
            
            for line in lines:
                if stock_code in line and ('公告' in line or '报告' in line):
                    notices.append(line.strip())
            
            return notices[:5]  # 取前5条
        else:
            print(f"  爬取失败: {result.error_message}")
            return []
            
    except Exception as e:
        print(f"  错误: {e}")
        return []


async def main():
    """主函数"""
    
    # 读取股票列表
    input_path = '/Users/mac/.openclaw/workspace-neo/data/smallcap/20260311/smallcap_screening_filtered.xlsx'
    df = pd.read_excel(input_path)
    
    print(f"处理 {len(df)} 只股票...")
    
    # 确保代码列为字符串
    df['代码'] = df['代码'].astype(str).str.replace('.0', '', regex=False)
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        
        notices_list = []
        
        for idx, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            
            print(f"[{idx+1}/{len(df)}] {code} {name}")
            
            titles = await get_hibor_notices(crawler, code, name)
            
            if titles:
                titles_str = ' | '.join(titles)
            else:
                titles_str = '无近期公告'
            
            notices_list.append({
                '代码': code,
                '近10天公告标题': titles_str
            })
            
            # 延时
            await asyncio.sleep(2)
    
    # 创建DataFrame
    notices_df = pd.DataFrame(notices_list)
    
    # 合并
    df_with_notices = df.merge(notices_df, on='代码', how='left')
    
    # 保存
    output_path = '/Users/mac/Desktop/小市值强势股_含公告标题_crawl4ai.xlsx'
    df_with_notices.to_excel(output_path, index=False, engine='xlsxwriter')
    
    print(f"\n已保存: {output_path}")
    
    # 统计
    success_count = len([n for n in notices_list if n['近10天公告标题'] != '无近期公告'])
    print(f"成功获取: {success_count}/{len(df)} 只")


if __name__ == '__main__':
    asyncio.run(main())
