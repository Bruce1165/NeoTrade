# 更新日志 - 2026-03-14

## 今日完成

### 1. Dashboard 系统
- ✅ 创建 Flask + SQLite 后端
- ✅ 创建 HTML/JS/ECharts 前端
- ✅ 自动发现筛选器（动态扫描 scripts 目录）
- ✅ 批量运行按钮（Run All Screeners）
- ✅ 系统服务常驻（LaunchAgent）
- ✅ 桌面 App 一键启动

### 2. 新增 3 个筛选器
- ✅ 涨停金凤凰（jin_feng_huang）
- ✅ 涨停银凤凰（yin_feng_huang）
- ✅ 涨停试盘线（shi_pan_xian）

### 3. 筛选器架构升级
- ✅ 基础模块（base_screener.py）
- ✅ 交易日历模块（自动跳过周末/节假日）
- ✅ 新闻抓取模块（新浪财经）
- ✅ LLM 分析模块（上涨原因、行业分类）
- ✅ 进度跟踪模块（断点续传）
- ✅ 输出管理模块（统一目录结构）

### 4. 目录结构
```
data/screeners/
├── coffee_cup/YYYY-MM-DD.xlsx
├── jin_feng_huang/YYYY-MM-DD.xlsx
├── yin_feng_huang/YYYY-MM-DD.xlsx
├── shi_pan_xian/YYYY-MM-DD.xlsx
├── er_ban_hui_tiao/YYYY-MM-DD.xlsx
└── zhang_ting_bei_liang_yin/YYYY-MM-DD.xlsx
```

### 5. Bug 修复
- ✅ 修复所有筛选器价格字段（统一使用 'close'）
- ✅ 修复 Dashboard API 端口问题
- ✅ 修复筛选器发现逻辑（排除 base/test 文件）

### 6. 上涨原因分析维度
- 国家政策
- 国际环境
- 突发事件
- 相关行业带动
- 所属行业推动
- 技术形态

## 待办
- [ ] 配置 LLM API key 启用智能分析
- [ ] 接入准确的股票行业分类数据
- [ ] 添加更多筛选器到 Dashboard

## 系统状态
- Dashboard: http://localhost:5003
- 服务状态: **已停止**
- 筛选器数量: 6 个

## 新增更新（14:30）

### 7. 涨停银凤凰逻辑更新
- ✅ 改为基于"最初涨停日"计算
- ✅ 支撑位 = 最初涨停（最高+最低）/2 × 50%
- ✅ 缩量阈值 = 最初涨停后最大成交额的 50%
- ✅ 突破放量 = 环比前日 2 倍以上
- ✅ 回调时间延长至 13 天

### 8. 测试运行结果
- 金凤凰：0 只股票（2026-03-13）
- 银凤凰：大量股票，多数回调中，少数已突破
- 试盘线：1 只股票（京运通），价格显示正常

### 9. Dashboard 外网访问
- 已配置绑定 0.0.0.0
- 内网地址：http://192.168.0.121:5003
- 外网访问需路由器端口映射或 ngrok
