# Sprint Plan - 2026-03-20
**Sprint**: 2026-03-20 → 2026-03-21  
**PM (Project)**: Neo  
**PM (Product)**: Bruce  
**Status**: Planning

---

## 🎯 Sprint Goals

1. **前端重构** - 重新封装代码，消除 regression 风险
2. **新 Screener 开发策略** - 标准化开发流程，支持双数据源
3. **框架集成与发布** - Baostock + iFinD 统一接入，Dashboard 上线

---

## 📋 Task Breakdown

### Task 1: 前端重构
**Owner**: Frontend Developer Agent  
**Priority**: P0  
**ETA**: 4 hours

#### 问题诊断
- 代码库不一致，多处重复逻辑
- 组件耦合度高，新功能容易引入 bug
- 状态管理混乱（useState 滥用）

#### 重构方案
1. **组件分层**
   ```
   components/
   ├── ui/           # 基础UI组件（Button, Modal, Table）
   ├── charts/       # 图表组件（KLine, Volume）
   ├── screeners/    # 筛选器相关（ScreenerList, ScreenerModal）
   ├── results/      # 结果展示（ResultsTable, DownloadButtons）
   └── layout/       # 布局组件（Header, Sidebar）
   ```

2. **数据访问层封装（核心）**
   - 统一数据接口，前端不感知数据源差异
   - 通过配置或参数切换 Baostock / iFinD / 混合模式
   ```typescript
   // api/dataSource.ts
   interface DataSource {
     fetchStockData(params: QueryParams): Promise<StockData[]>;
     fetchScreenerResults(screener: string, date: string): Promise<Result[]>;
     fetchRealtimeData(codes: string[]): Promise<RealtimeQuote[]>;
   }
   
   // 实现层
   class BaostockSource implements DataSource { ... }
   class iFinDSource implements DataSource { ... }
   class HybridSource implements DataSource { ... } // 自动切换
   
   // 使用层（前端只依赖接口，不依赖具体实现）
   const dataSource = createDataSource('auto'); // auto | baostock | ifind
   ```

3. **状态管理**
   - 使用 React Context 统一管理筛选器状态
   - 分离 UI 状态和业务数据状态

4. **API 封装**
   - 统一 `api/` 目录，按功能模块拆分
   - 统一错误处理和 loading 状态

4. **类型定义**
   - 补充 TypeScript 接口定义
   - ScreenerConfig, StockData, RunResult 等

5. **新增功能：一键查看结果**
   - **位置**: Screener 运行完成后的操作按钮区（Download CSV / Download Excel 旁边）
   - **按钮**: "查看结果" 或 "📊 查看结果"
   - **行为**: 
     - 点击后跳转到「结果查询」页面
     - URL 携带参数: `?screener={name}&date={date}`
     - 结果页面自动解析参数，加载并展示对应数据
   - **优势**: 减少用户操作步骤，从 4 步变为 1 步

#### 验收标准
- [ ] 所有现有功能正常工作（回归测试通过）
- [ ] 新组件结构清晰，无重复代码
- [ ] 新增筛选器时，只需修改配置文件，不改动核心代码
- [ ] 「一键查看结果」功能正常：跳转 + 自动加载 + 数据正确

---

### Task 2: 新 Screener 开发策略
**Owner**: Backend Architect Agent  
**Priority**: P0  
**ETA**: 2 hours

#### 标准化模板
```python
# scripts/templates/screener_template.py
class ScreenerTemplate:
    """
    筛选器开发模板
    - 数据源: Baostock / iFinD / Both
    - 输出格式: 统一
    """
    
    def __init__(self, data_source="auto"):
        self.data_source = data_source  # auto | baostock | ifind
        
    def fetch_data(self, trade_date):
        """统一数据获取接口"""
        pass
        
    def run_screening(self, trade_date):
        """核心筛选逻辑"""
        pass
        
    def save_results(self, results, trade_date):
        """统一输出格式"""
        pass
```

#### 数据源策略
| 场景 | 数据源 | 说明 |
|------|--------|------|
| 历史数据回测 | Baostock | 免费，历史数据完整 |
| 实时数据/今日收盘 | iFinD | 实时性高，需测试稳定性 |
| 混合模式 | Both | 优先 Baostock，缺失用 iFinD 补 |

#### 开发流程
1. 从模板创建新文件
2. 实现 `fetch_data()` - 指定数据源
3. 实现 `run_screening()` - 核心逻辑
4. 本地测试（单日期）
5. QA 测试（多日回测）
6. Dashboard 集成

---

### Task 3: 框架集成与发布
**Owner**: DevOps Automator + Backend Architect  
**Priority**: P0  
**ETA**: 2 hours

#### iFinD 集成
- [ ] 测试 `scripts/sync_ifind_to_db.py`
- [ ] 验证数据格式与 Baostock 一致
- [ ] 添加数据源切换逻辑（根据 trade_date 自动选择）

#### Ngrok 高可用机制
**问题**: ngrok 容易掉线（ERR_NGROK_3200/334）

**解决方案**:
1. **心跳检测脚本** - 每 30 秒检查隧道状态
2. **自动重启逻辑** - 检测到离线立即重启 ngrok + Flask
3. **多重保障**:
   - LaunchAgent（系统级）
   - Cron 定时检查（应用级）
   - Dashboard 健康检查 API（前端感知）

**验收标准**:
- [ ] 掉线检测时间 < 60 秒
- [ ] 自动恢复时间 < 30 秒
- [ ] 提供 `/api/health` 接口供前端轮询

#### Dashboard 发布
- [ ] 前端构建 + 后端部署
- [ ] ngrok 隧道更新
- [ ] 全功能回归测试

---

## 👥 Agent 分工

| Agent | Task | Time |
|-------|------|------|
| Frontend Developer | Task 1: 前端重构 | 08:45 - 12:45 |
| Backend Architect | Task 2: Screener 策略 | 13:00 - 15:00 |
| DevOps Automator | Task 3: 集成发布 | 15:00 - 17:00 |
| Code Reviewer | Review 所有 PR | 并行进行 |
| Daily QA | 回归测试 | 17:00 - 18:00 |

---

## 🚦 今日里程碑

| 时间 | 里程碑 | 验收 |
|------|--------|------|
| 12:45 | 前端重构完成 | 代码 Review 通过 |
| 15:00 | Screener 策略定稿 | 模板 + 文档完成 |
| 17:00 | Dashboard 新框架上线 | 可访问 + 功能正常 |
| 18:00 | QA 回归测试通过 | 11个筛选器全部通过 |

---

## 📝 工作日志

### 2026-03-20 08:40
- **事件**: Sprint Plan 创建
- **状态**: 待 Bruce Review
- **下一步**: 用户确认后，启动 Frontend Developer Agent

---

*Created by: Neo*  
*Review by: Bruce (pending)*
