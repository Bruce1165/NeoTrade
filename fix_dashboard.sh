#!/bin/bash
echo "=== 修复方案 A ==="

# 修改 index.html
cd /Users/mac/.openclaw/workspace-neo/dashboard/static

# 创建新的 index.html 带 cache-control
cat > index.html <> 'HTMLEOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neo 交易系统 v2.0</title>
    <link rel="stylesheet" href="style.css?v=2">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script src="https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js"></script>
</head>
<body>
    <div class="app">
        <aside class="sidebar">
            <div class="logo">
                <span class="logo-icon">📈</span>
                <span class="logo-text">NEO v2.0</span>
            </div>
            <nav class="nav">
                <div class="nav-section">
                    <button class="nav-item active" data-page="screeners">
                        <span class="nav-icon">🔍</span>
                        <span>筛选器</span>
                    </button>
                    <button class="nav-item" data-page="cron">
                        <span class="nav-icon">⏰</span>
                        <span>自动任务</span>
                    </button>
                    <button class="nav-item" data-page="jobs">
                        <span class="nav-icon">⚡</span>
                        <span>手动任务</span>
                    </button>
                    <button class="nav-item" data-page="results">
                        <span class="nav-icon">📊</span>
                        <span>结果查询</span>
                    </button>
                    <button class="nav-item" data-page="calendar">
                        <span class="nav-icon">📅</span>
                        <span>日历</span>
                    </button>
                </div>
            </nav>
        </aside>

        <main class="main">
            <div class="page" id="screeners-page">
                <div class="page-header">
                    <h1 class="page-title">技术分析筛选器</h1>
                    <button class="btn btn-primary" onclick="openAddModal('screener')">+ 添加筛选器</button>
                </div>
                <div class="module-grid" id="screener-grid">
                    <!-- Screeners will be loaded here -->
                    <p class="loading">加载中...</p>
                </div>
            </div>

            <div class="page" id="cron-page" style="display:none;">
                <div class="page-header">
                    <h1 class="page-title">定时任务</h1>
                    <button class="btn btn-primary" onclick="openAddModal('cron')">+ 添加定时任务</button>
                </div>
                <div class="list-container" id="cron-list">
                    <p class="loading">加载中...</p>
                </div>
            </div>

            <div class="page" id="jobs-page" style="display:none;">
                <div class="page-header">
                    <h1 class="page-title">手动任务</h1>
                    <button class="btn btn-primary" onclick="openAddModal('manual')">+ 添加手动任务</button>
                </div>
                <div class="list-container" id="jobs-list">
                    <p class="loading">加载中...</p>
                </div>
            </div>

            <div class="page" id="results-page" style="display:none;">
                <div class="page-header">
                    <h1 class="page-title">结果查询</h1>
                </div>
                <div class="filter-bar">
                    <select id="results-screener-select" class="select-input">
                        <option value="">选择筛选器</option>
                    </select>
                    <input type="date" id="results-date" class="date-input">
                    <button class="btn btn-primary" onclick="loadResults()">查询</button>
                    <button class="btn btn-secondary" onclick="downloadResults()">⬇️ 下载</button>
                </div>
                <div id="results-content">
                    <p class="empty-state">请选择筛选器和日期后查询</p>
                </div>
            </div>

            <div class="page" id="calendar-page" style="display:none;">
                <div class="page-header">
                    <h1 class="page-title">日历视图</h1>
                </div>
                <div class="calendar-container" id="calendar-view">
                    <!-- Calendar will be loaded here -->
                </div>
            </div>
        </main>
    </div>

    <!-- Run Modal -->
    <div id="run-modal" class="modal">
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <h3 id="run-modal-title">运行任务</h3>
                <span class="close-btn">&times;</span>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label for="run-date">选择日期:</label>
                    <input type="date" id="run-date" class="date-input">
                </div>
                <div id="run-status" class="run-status"></div>
            </div>
            <div class="modal-footer">
                <button id="confirm-run-btn" class="btn btn-primary">运行</button>
                <button class="btn btn-secondary" onclick="closeAllModals()">取消</button>
            </div>
        </div>
    </div>

    <script src="app.js?v=2"></script>
</body>
</html>
HTMLEOF

echo "✅ 新的 index.html 已创建"
echo ""
echo "现在重启服务..."
