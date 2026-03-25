# MEMORY.md - Long-term Memory

**Created:** 2026-03-11
**Agent:** Neo
**Purpose:** Trading analysis & model building

---

## 🚀 Active Projects

### Dashboard 2.0
**Status:** Completed - All features working
**Created:** 2026-03-18
**Description:** Modern React-based trading dashboard with real-time screening results
**Location:** `dashboard2/frontend/`
**Deployment:** Local Flask + ngrok

**Features:**
- Results table with Chinese column names (all screeners)
- Clickable stock codes showing ECharts K-line charts
- Excel (.xlsx) export with proper formatting
- Dynamic table rendering for all data structures
- Today-date validation preventing errors

**Key Fixes:**
- Removed pandas dependency (pure SQLite)
- Delayed chart initialization for modal rendering
- Comprehensive column name translations (lowercase/uppercase/extra_data)

---

### Coffee Cup Pattern Screener (咖啡杯形态筛选)
**Status:** Active - Awaiting data download completion
**Created:** 2026-03-13
**Description:** Advanced cup-handle pattern screener with strict criteria
**Script:** `coffee_cup_screener.py`
**Output:** `data/coffee_cup_YYYY-MM-DD.xlsx`

**Criteria:**
- 杯沿 = 昨天收盘价
- 杯柄 = 45天前或更早，价格差 ≤ 5%
- 杯底期间所有收盘价 < 杯柄/杯沿
- 换手率 ≥ 5%
- 涨幅 ≥ 2%
- 放量 ≥ 2x (最近3天 vs 前3天)

**Latest Results:** 18 stocks found (see daily log 2026-03-13)

### 12month-cuphold Screening Task (Legacy)
**Status:** Archived

---

## 🧬 NeoTrade Strategy Research (AutoResearch Skill)

**Status:** Active - Experiment Loop Running  
**Created:** 2026-03-24  
**Branch:** `autoresearch/strategy-v1`  
**Skill:** `/autoresearch` - Autonomous experiment protocol  

**Goal:** Build short-to-medium term trading strategy targeting:
- Win rate > 65%
- Annual return > 50%
- Max drawdown < 10%

**Strategy:** Multi-factor momentum (RS ranking + MA pullback entry)

**Baseline Results (v0.1):**
```
Sharpe: -0.186 | Return: -1.57% | Win Rate: 42.9% | DD: 6.08%
```

**Active Experiments:**
- EXP-1: Widen stop loss -8% → -10%, reduce take profit +20% → +15%
- Status: Subagent completed, awaiting next run

**Recent Fixes (2026-03-24):**
- ✅ ShiPanXian screener database connection fixed (using Lite version)
- ✅ Turnover data download fixed for future dates
- ✅ Access statistics showing unique visitors (not page views)
- ✅ Ngrok tunnel stabilized

**Known Issues:**
- 2026-03-23/24 turnover data partially missing (5104/5105 stocks affected)
- Batch repair in progress using Baostock
- ShiPanXian full feature pending (Lite version active)

**Data Split:**
- Training: 2024-09-02 to 2025-08-31
- Validation: 2025-09-01 to 2026-02-28 (LOCKED)

**Files:**
- `autoresearch.config.md` - Experiment protocol
- `results.tsv` - Experiment log
- `scripts/neo_strategy/` - Strategy implementation
**Created:** 2026-03-12
**Note:** Replaced by Coffee Cup Pattern Screener

---

## 📊 Data Infrastructure

### Database
- **Path:** `data/stock_data.db`
- **Tables:** stocks, daily_prices, announcements, limit_up_reasons
- **Date Range:** 2024-09-02 to 2026-03-12
- **Total Stocks:** 5,697

### Data Download System
- **Script:** `download_chunked.py`
- **Method:** Chunked download (200 stocks/chunk)
- **Source:** Baostock
- **Progress File:** `data/download_progress.json`

---

## 🧠 Key Insights

### Pattern Recognition
- Coffee cup pattern requires strict cup-bottom validation
- Volume surge (2x+) is strong confirmation signal
- 45+ day separation between handle and rim is critical

### Data Quality
- Always verify data integrity before screening
- Chunked downloads with progress tracking prevent data loss
- Check for delisted stocks (names ending with "退")

---

## 📝 Important Notes

- **Text > Brain**: Always write to files
- **Source everything**: Data without provenance is useless
- **Version your models**: Track what changed and why
- **Log your trades**: Even paper trades build discipline
- **Save progress**: Use progress files for long-running tasks

---

## 🔧 Data Infrastructure Issues (2026-03-19)

### 发现的问题
**数据下载系统存在以下缺陷：**

1. **无查重机制**
   - 同一股票同一日期可重复插入，无唯一约束
   - 导致 2026-03-17 数据出现 5,399 条重复记录

2. **断点续传失效**
   - progress 文件记录混乱，completed 列表堆积重复条目
   - 无法准确识别已下载 vs 待下载股票
   - 重新启动时会重复下载已完成的股票

3. **日志缺失**
   - 没有清晰的更新记录和状态追踪
   - 无法快速判断数据完整性和时效性

### 改进计划
- [ ] 添加数据库唯一约束 (code + date)
- [ ] 重写 progress 文件逻辑，使用 Set 去重
- [ ] 添加下载日志表，记录每次更新操作
- [ ] 数据完整性检查脚本，定时自动运行

---

## 🐛 Bug Fixes & Improvements

### 2026-03-16 Dashboard 全面优化
**Fixed:**
1. **菜单结构** - 合并为单一导航栏：筛选器、自动任务、手动任务、结果、日历
2. **界面中文化** - 所有按钮、标签、提示改为中文
3. **筛选器显示名** - 拼音改为汉字：
   - `coffee_cup_screener` → 咖啡杯形态
   - `er_ban_hui_tiao_screener` → 二板回调
   - `zhang_ting_bei_liang_yin_screener` → 涨停倍量阴
   - 等等...
4. **字段排序** - 为每个筛选器定义专属字段顺序（身份→状态→表现→估值→信号）
5. **字段显示** - 股票列表字段全部中文化，智能格式化（价格、百分比、大数字）
6. **K线图修复** - 将 `showChart`, `viewDayResults` 等函数暴露到全局作用域，修复点击股票代码无法显示K线的问题
7. **日历紧凑化** - 新设计：网格布局、月份卡片、小圆点标记、悬停提示
8. **下载功能** - 结果列表上方添加下载按钮，支持导出 CSV 格式
9. **每日最热股筛选器** - 新增筛选器
   - 路径：`scripts/daily_hot_screener.py`
   - 输出：`data/每日最热股/YYYY-MM-DD.xlsx` 和 `.csv`
   - 条件：涨幅≥5%，成交额≥10亿，排除ST/北交所/新股
   - 板块分类：主板10%、创业板/科创板20%
   - 字段：代码、名称、板块、行业、价格、涨幅、成交额、换手率、累计涨停天数、5/10/20/60日涨幅、异动类型
10. **二板回调报错** - 修复 `run_screening()` 参数不匹配问题
    - 受影响文件：`er_ban_hui_tiao_screener.py`, `coffee_cup_screener.py`, `zhang_ting_bei_liang_yin_screener.py`
    - 统一签名：`run_screening(self, trade_date: str = None)`
11. **每日热冷股筛选器** - 新增筛选器（合并热股+冷股）
    - 路径：`scripts/daily_hot_cold_screener.py`
    - 输出：`data/每日热冷股/YYYY-MM-DD.xlsx`（两个Sheet：热股、冷股）
    - 热股条件：涨幅≥5%，成交额≥10亿
    - 冷股条件：跌幅≤-5%，成交额≥10亿
    - Dashboard显示：Tab切换（热股|冷股），每个Tab内按板块→异动原因分组
    - 排序：热股涨幅降序，冷股跌幅降序（最负在前），同涨跌幅按成交额降序
12. **数据库字段扩展** - 为 stocks 表添加新字段
    - `total_market_cap`: AB股总市值（元）
    - `circulating_market_cap`: 流通市值（元）
    - `pb_ratio`: 市净率
    - 每日更新任务自动从 AKShare 获取这些字段
13. **咖啡杯任务合并** - 合并咖啡杯每日筛选和输出
    - 删除 `coffee_cup_daily_output_screener.py`
    - 更新 `coffee_cup_daily_screener.py`，同时输出：
      - `data/coffee_cup_YYYYMMDD.xlsx`（基础字段）
      - `data/coffee_cup_daily/YYYYMMDD/咖啡杯形态选股.xlsx`（丰富字段，含市值、行业）
    - 从数据库读取市值、行业数据，不再依赖 AKShare 实时获取

### 2026-03-16 Goose 代码审查修复
**Critical Bug Fixed:**
- **金凤皇/银凤皇/试盘线筛选器崩溃问题**
  - 问题：`is_limit_up()` 方法访问 `row['code']`，但 dataframe 还没有该列
  - 修复：在 `get_stock_data()` 中添加 `df['code'] = code`
  - 受影响文件：`jin_feng_huang_screener.py`, `yin_feng_huang_screener.py`, `shi_pan_xian_screener.py`

### 2026-03-19 Excel 兼容性与下载功能优化
**Fixed:**
1. **Excel 兼容性问题**
   - 问题：`openpyxl` 引擎生成的文件在某些 Excel 版本上报格式错误
   - 修复：所有导出改用 `xlsxwriter` 引擎（OOXML 格式）
   - 修改文件：7 个（`output_manager.py`, `coffee_cup_screener.py` 等）
   
2. **下载 UI 改进**
   - CSV 提升为主选项：绿色渐变按钮 + "Recommended" 标签
   - Excel 降为次选项：描边样式按钮
   - 添加提示："CSV works with all Excel versions"
   - 修改文件：`dashboard2/frontend/src/App.tsx`, `App.css`

### 2026-03-20 Milestone v1.0.0 Release
**Production-Ready Trading Dashboard Released**
- **Commit:** `f256895`
- **Tag:** `v1.0.0`
- **Status:** Production Ready

**Major Features:**
- 14 Active Technical Screeners with data availability check
- Daily Hot/Cold Screener with date-specific filtering
- iFind Realtime daily data download (4663 stocks)
- Database storage for screener results
- K-Line Chart display with ECharts
- Ngrok HA monitoring with auto-restart
- CSV/Excel export functionality
- Data integrity check + Baostock backfill scripts

**Critical Fixes:**
- Date format handling: All dates use YYYY-MM-DD internally
- Data availability check: Screeners verify DB before running
- Removed 4 outdated screeners (intraday, postmarket, daily_update, keyword_expander)
- Fixed daily_hot_cold_screener to filter by specific date (not just latest)
- Frontend tab state sync with URL
- Fixed date input initialization to prevent pattern mismatch

**Infrastructure:**
- Ngrok monitoring LaunchAgent for auto-recovery
- Daily QA system for screener testing
- Scripts: `verify_data_integrity.py`, `backfill_baostock.py`, `download_today_ifind.py`

**Data Status:**
- Total stocks: 4,663
- Date range: 2024-09-02 to 2026-03-20
- Today's data: ✅ Complete
- Known gap: 2026-02-16 (external source needed)

---

## 🐛 Bug Fixes & Technical Notes

### 2026-03-23 - Hot/Cold Screener JSON NaN Fix
**Issue:** Download buttons not working for `daily_hot_cold_screener`
- Frontend error: "JSON Parse error: Unexpected identifier NaN"
- Root cause: Stock 600673 (东阳光) had `NaN` in `return_10d` field
- Python's `json.dumps()` outputs `NaN` by default, which is **not valid JSON**

**Files Modified:**
- `dashboard2/frontend/api/app.py` - Added SafeJSONEncoder
- `dashboard2/frontend/api/models.py` - Fixed database path

**Solution:**
```python
class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles NaN, Infinity, -Infinity by converting to null"""
    def encode(self, obj):
        obj = self._sanitize(obj)
        return super().encode(obj)
    
    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj
```

Also fixed database path in models.py:
- Was: `data/stock_data.db` (wrong location)
- Now: `dashboard2/frontend/api/data/dashboard.db` (correct)

**Status:** ✅ Fixed - All download buttons working

---

## 📝 TODO List

### Data Infrastructure

#### 🔴 High Priority
- [ ] **Fix network access for AKShare APIs**
  - **Problem:** AKShare connection reset, East Money API 502 error
  - **Impact:** Cannot fetch market cap (总市值/流通市值), list_date (上市日期), ROE, debt_ratio
  - **Current status:** 
    - ✅ Baostock working (96% coverage for industry, PE, PB)
    - ❌ iFind API limitation: `real_time_quotation` only supports trading data, NOT fundamental data
  - **Solutions to try:**
    1. Wait for AKShare rate limit reset (temporary)
    2. Use proxy/VPN for AKShare
    3. Purchase iFind data package with fundamental data API
    4. Import from downloaded Excel/CSV files (manual)
  - **Created:** 2026-03-25
  - **Updated:** 2026-03-25 - iFind API confirmed NOT supporting market cap/list date

#### 🟡 Medium Priority  
- [ ] Complete stocks table fundamental data
  - Market cap: 0.04% → target 100%
  - List date: 0% → target 100%
  - Financial ratios (ROE, debt_ratio): pending iFind

---
**For current priorities, check CACHE.md**
**For daily work logs, check memory/YYYY-MM-DD.md**
