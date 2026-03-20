# TODO List - Neo Trading System (Updated 2026-03-20 14:52)

## ✅ COMPLETED TODAY

### 1. UI/UX
- [x] Realtime Run 按钮移除
- [x] "View Results" 按钮添加
- [x] K 线图修复 (Chart container not found)
- [x] 日期格式统一封装 (`utils/format.ts`)
- [x] 日期输入框添加 min/max 限制

### 2. Data
- [x] iFind 60天数据补充 (116,800 条)
- [x] Baostock 完整下载
- [x] 500只股票属性更新
- [x] 数据库字段扩展 (sector, pe_ratio, is_delisted 等)

### 3. Infrastructure
- [x] 自动进度报告 (cron 每30分钟)
- [x] Ngrok 监控脚本
- [x] 后台同步框架

---

## 📋 REMAINING TODO

### P0 - Critical (This Week)
1. **结果数据库存储**
   - 创建 `screener_runs` 表
   - 创建 `screener_results` 表
   - API: POST /results/store
   - API: GET /results/query
   - 前端：移除文件输出，改为数据库读取

2. **筛选器参数编辑**
   - Screener card 上显示可编辑参数
   - 默认参数展示
   - 参数修改后运行

3. **退市股票标识完成**
   - 剩余 63 只股票检查 (4600/4663 done)
   - 标记 is_delisted=1

### P1 - Important (Next Week)
4. **结果缓存逻辑**
   - 同日期同参数 → 直接返回缓存
   - DB 更新检测

5. **智能选股集成**
   - iFind MCP 预筛选
   - 自然语言查询支持

6. **Dashboard 性能优化**
   - 大数据量分页
   - 虚拟滚动

### P2 - Nice to Have
7. **Screener 模板标准化**
8. **自动化测试**
9. **数据可视化增强**

---

## 🐛 KNOWN ISSUES

1. **日期显示格式**
   - 状态: 🔄 修复中
   - 问题: 浏览器 locale 显示 2026/03/19 而非 2026-03-19
   - 方案: 已添加 formatDate 强制转换

2. **iFind 配额耗尽**
   - 状态: ⏸️ 暂停
   - 影响: 无法继续同步基本面数据
   - 方案: 等待下月配额或联系客服

3. **后台同步进程**
   - 状态: 🔄 运行中 (PID 6242)
   - 进度: 99% (4600/4663)
   - 行动: 可能需要手动停止

---

## 📁 KEY FILES

```
/Users/mac/.openclaw/workspace-neo/
├── dashboard2/frontend/src/
│   ├── App.tsx (主界面)
│   └── utils/format.ts (日期/代码格式化)
├── scripts/
│   ├── background_sync.py (后台同步)
│   └── migrate_db_ifind_fields.py (数据库迁移)
├── memory/
│   ├── 2026-03-20.md (工作日志)
│   └── conversation-snapshot-2026-03-20.md (对话快照)
└── data/stock_data.db
```

---

## 🎯 NEXT IMMEDIATE ACTION

**建议**: 先完成 P0 #1 (结果数据库存储)

理由:
1. 影响核心功能
2. 数据一致性基础
3. 后续功能依赖

预估时间: 2-3 小时
