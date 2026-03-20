/**
 * Neo Trading System - Dashboard App
 */

const API_BASE = '';

// Module definitions - 显示名称改为中文
const MODULES = {
    screeners: {
        title: '技术分析筛选器',
        items: [
            'coffee_cup_screener',
            'jin_feng_huang_screener',
            'er_ban_hui_tiao_screener',
            'zhang_ting_bei_liang_yin_screener',
            'yin_feng_huang_screener',
            'shi_pan_xian_screener',
            'breakout_20day_screener',
            'daily_hot_screener'
        ],
        displayNames: {
            'coffee_cup_screener': '欧奈尔杯柄形态 (CANSLIM)',
            'jin_feng_huang_screener': '金凤皇形态',
            'er_ban_hui_tiao_screener': '二板回调',
            'zhang_ting_bei_liang_yin_screener': '涨停倍量阴',
            'yin_feng_huang_screener': '银凤皇形态',
            'shi_pan_xian_screener': '试盘线',
            'breakout_20day_screener': '20日突破',
            'daily_hot_screener': '每日最热股'
        }
    },
    cron: {
        title: '定时任务',
        items: [
            'intraday_screener',
            'postmarket_screener',
            'keyword_expander_screener'
        ],
        displayNames: {
            'intraday_screener': '盘中筛选',
            'postmarket_screener': '盘后筛选',
            'keyword_expander_screener': '关键词扩展'
        },
        schedules: {
            'intraday_screener': '09:35, 09:45, 10:00, 15:00',
            'postmarket_screener': '15:30 daily',
            'keyword_expander_screener': '16:00 daily'
        }
    },
    jobs: {
        title: '手动任务',
        items: [
            'daily_update_screener',
            'coffee_cup_daily_output_screener',
            'coffee_cup_daily_screener'
        ],
        displayNames: {
            'daily_update_screener': '每日数据更新',
            'coffee_cup_daily_output_screener': '咖啡杯输出',
            'coffee_cup_daily_screener': '咖啡杯每日筛选'
        },
        dependencies: {
            'daily_update_screener': null,
            'coffee_cup_daily_output_screener': '需在咖啡杯每日筛选后运行',
            'coffee_cup_daily_screener': '需等待每日数据更新完成'
        }
    }
};

// State
let allScreeners = [];
let currentPage = 'screeners';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadScreeners();
    initModals();

    // Set default date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('run-date').value = today;
    document.getElementById('results-date-input').value = today;

    // Bind download button
    const downloadBtn = document.getElementById('download-results-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadResults);
    }
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const page = btn.dataset.page;
            switchPage(page);
            
            // Update active state
            document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

function switchPage(page) {
    currentPage = page;
    
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    
    // Show selected page
    const pageEl = document.getElementById(`${page}-page`);
    if (pageEl) {
        pageEl.classList.add('active');
    }
    
    // Update title
    const titles = {
        screeners: '技术分析筛选器',
        results: '筛选结果',
        calendar: '运行日历',
        cron: '自动任务',
        jobs: '手动任务'
    };
    document.getElementById('page-title').textContent = titles[page] || page;
    
    // Load page data
    if (page === 'results') {
        loadResultsPage();
    } else if (page === 'calendar') {
        loadCalendar();
    } else if (page === 'cron') {
        renderCronTasks();
    } else if (page === 'jobs') {
        renderManualJobs();
    } else if (page === 'screeners') {
        renderScreeners();
    }
}

// Load all screeners from API
async function loadScreeners() {
    try {
        const response = await fetch(`${API_BASE}/api/screeners`);
        const data = await response.json();
        allScreeners = data.screeners || [];
        
        if (currentPage === 'screeners') {
            renderScreeners();
        } else if (currentPage === 'cron') {
            renderCronTasks();
        } else if (currentPage === 'jobs') {
            renderManualJobs();
        }
        
        // Populate results dropdown
        populateResultsDropdown();
    } catch (error) {
        console.error('Failed to load screeners:', error);
    }
}

// Render Screeners Grid
function renderScreeners() {
    const grid = document.getElementById('screener-grid');
    const screenerNames = MODULES.screeners.items;
    
    const screeners = allScreeners.filter(s => screenerNames.includes(s.name));
    
    if (screeners.length === 0) {
        grid.innerHTML = '<p class="empty-state">No screeners available. Click "Add Screener" to create one.</p>';
        return;
    }
    
    grid.innerHTML = screeners.map(s => {
        const displayName = MODULES.screeners.displayNames[s.name] || s.display_name;
        return `
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">${displayName}</div>
                    <div class="card-subtitle">${s.name}</div>
                </div>
                <span class="card-type technical">技术分析</span>
            </div>
            <div class="card-body">
                <p class="card-description">${s.description || '形态识别筛选器'}</p>
            </div>
            <div class="card-footer">
                <button class="btn btn-primary btn-sm" onclick="openRunModal('${s.name}', '${displayName}', 'screener')">▶ 运行</button>
                <button class="btn btn-info btn-sm" onclick="openCheckModal('${s.name}', '${displayName}')">🔍 检查</button>
                <button class="btn btn-secondary btn-sm" onclick="openEditModal('${s.name}', 'screener')">编辑</button>
                <button class="btn btn-secondary btn-sm" onclick="viewScreenerDetail('${s.name}')">查看</button>
                <button class="btn btn-danger btn-sm" onclick="openDeleteModal('${s.name}', '${displayName}')">🗑</button>
            </div>
        </div>
    `}).join('');
}

// Render Cron Tasks List
function renderCronTasks() {
    const list = document.getElementById('cron-list');
    const taskNames = MODULES.cron.items;
    
    const tasks = allScreeners.filter(s => taskNames.includes(s.name));
    
    if (tasks.length === 0) {
        list.innerHTML = '<p class="empty-state">No cron tasks available. Click "Add Cron Task" to create one.</p>';
        return;
    }
    
    list.innerHTML = tasks.map(t => {
        const schedule = MODULES.cron.schedules[t.name] || '定时运行';
        const displayName = MODULES.cron.displayNames[t.name] || t.display_name;
        return `
        <div class="list-card">
            <div class="list-card-info">
                <div class="list-card-title">${displayName}</div>
                <div class="list-card-meta">⏰ ${schedule}</div>
            </div>
            <div class="list-card-actions">
                <button class="btn btn-success btn-sm" onclick="openRunModal('${t.name}', '${displayName}', 'cron')">▶ 立即运行</button>
                <button class="btn btn-secondary btn-sm" onclick="openEditModal('${t.name}', 'cron')">编辑</button>
                <button class="btn btn-secondary btn-sm" onclick="viewScreenerDetail('${t.name}')">查看</button>
                <button class="btn btn-danger btn-sm" onclick="openDeleteModal('${t.name}', '${displayName}')">🗑</button>
            </div>
        </div>
    `}).join('');
}

// Render Manual Jobs List
function renderManualJobs() {
    const list = document.getElementById('jobs-list');
    const jobNames = MODULES.jobs.items;
    
    const jobs = allScreeners.filter(s => jobNames.includes(s.name));
    
    if (jobs.length === 0) {
        list.innerHTML = '<p class="empty-state">No manual jobs available. Click "Add Manual Job" to create one.</p>';
        return;
    }
    
    list.innerHTML = jobs.map(j => {
        const dep = MODULES.jobs.dependencies[j.name];
        const depBadge = dep ? `<span style="color: var(--accent-warning); font-size: 11px;">⚠️ ${dep}</span>` : '';
        const displayName = MODULES.jobs.displayNames[j.name] || j.display_name;

        return `
        <div class="list-card">
            <div class="list-card-info">
                <div class="list-card-title">${displayName}</div>
                <div class="list-card-meta">⚡ 手动触发 ${depBadge}</div>
            </div>
            <div class="list-card-actions">
                <button class="btn btn-primary btn-sm" onclick="openRunModal('${j.name}', '${displayName}', 'job', '${dep || ''}')">▶ 运行</button>
                <button class="btn btn-secondary btn-sm" onclick="openEditModal('${j.name}', 'job')">编辑</button>
                <button class="btn btn-secondary btn-sm" onclick="viewScreenerDetail('${j.name}')">查看</button>
                <button class="btn btn-danger btn-sm" onclick="openDeleteModal('${j.name}', '${displayName}')">🗑</button>
            </div>
        </div>
    `}).join('');
}

// Populate results dropdown
function populateResultsDropdown() {
    const select = document.getElementById('results-screener-select');
    select.innerHTML = '<option value="">Select Screener</option>';
    
    allScreeners.forEach(s => {
        const option = document.createElement('option');
        option.value = s.name;
        option.textContent = s.display_name;
        select.appendChild(option);
    });
}

// Modals
function initModals() {
    // Close buttons
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', closeAllModals);
    });
    
    // Close on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeAllModals();
            }
        });
    });
    
    // Run button
    document.getElementById('confirm-run-btn').addEventListener('click', runTask);
    
    // Edit/Save button
    document.getElementById('confirm-edit-btn').addEventListener('click', saveScreener);
    
    // Delete button
    document.getElementById('confirm-delete-btn').addEventListener('click', deleteScreener);
    
    // Load results button
    document.getElementById('load-results-btn').addEventListener('click', loadResults);
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
}

// Run Modal
let currentRunTask = null;

function openRunModal(name, displayName, type, dependency = '') {
    currentRunTask = name;
    document.getElementById('run-task-name').textContent = displayName;
    document.getElementById('run-status').innerHTML = '';
    
    // Show dependency info if exists
    const depEl = document.getElementById('run-dependencies');
    const depText = document.getElementById('run-deps-text');
    
    if (dependency) {
        depEl.style.display = 'flex';
        depText.textContent = dependency;
    } else {
        depEl.style.display = 'none';
    }
    
    document.getElementById('run-modal').classList.add('active');
}

async function runTask() {
    if (!currentRunTask) return;
    
    const date = document.getElementById('run-date').value;
    const statusEl = document.getElementById('run-status');
    
    statusEl.innerHTML = '<span class="loading">Running...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/screeners/${currentRunTask}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date })
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusEl.innerHTML = `<span class="success">✓ Completed: ${data.stocks_found} stocks found</span>`;
            setTimeout(closeAllModals, 1500);
        } else {
            statusEl.innerHTML = `<span class="error">✗ Error: ${data.error || 'Unknown error'}</span>`;
        }
    } catch (error) {
        statusEl.innerHTML = `<span class="error">✗ Failed: ${error.message}</span>`;
    }
}

// Add/Edit Modal
let isEditing = false;

function openAddModal(category) {
    isEditing = false;
    document.getElementById('edit-modal-title').textContent = `Add New ${category === 'screener' ? 'Screener' : category === 'cron' ? 'Cron Task' : 'Manual Job'}`;
    document.getElementById('edit-original-name').value = '';
    document.getElementById('edit-category').value = category;
    document.getElementById('edit-name').value = '';
    document.getElementById('edit-name').disabled = false;
    document.getElementById('edit-display-name').value = '';
    document.getElementById('edit-description').value = '';
    document.getElementById('edit-code').value = generateDefaultCode(category);
    document.getElementById('edit-status').innerHTML = '';
    document.getElementById('edit-modal').classList.add('active');
}

async function openEditModal(name, category) {
    isEditing = true;
    document.getElementById('edit-modal-title').textContent = 'Edit';
    document.getElementById('edit-original-name').value = name;
    document.getElementById('edit-category').value = category;
    document.getElementById('edit-name').value = name;
    document.getElementById('edit-name').disabled = true;
    document.getElementById('edit-status').innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE}/api/screeners/${name}`);
        const data = await response.json();
        
        if (data.screener) {
            document.getElementById('edit-display-name').value = data.screener.display_name || '';
            document.getElementById('edit-description').value = data.screener.description || '';
        }
        
        if (data.source_code) {
            document.getElementById('edit-code').value = data.source_code;
        }
        
        document.getElementById('edit-modal').classList.add('active');
    } catch (error) {
        alert('Failed to load screener details');
    }
}

function generateDefaultCode(category) {
    const templates = {
        screener: `#!/usr/bin/env python3
"""
New Screener - Description here
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class NewScreener:
    """New Screener"""
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        logger = logging.getLogger('new_screener')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """Run screening"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"Running screener: {trade_date}")
        
        # TODO: Implement screening logic
        results = []
        
        self.logger.info(f"Found {len(results)} stocks")
        return results


def main():
    screener = NewScreener()
    results = screener.run_screening()
    print(f"Found {len(results)} stocks")


if __name__ == '__main__':
    main()`,
        cron: `#!/usr/bin/env python3
"""
New Cron Task - Description here
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class NewCronTask:
    """New Cron Task"""
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        logger = logging.getLogger('new_cron')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """Run cron task"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"Running cron task: {trade_date}")
        
        # TODO: Implement task logic
        results = []
        
        self.logger.info(f"Task completed: {len(results)} items")
        return results


def main():
    task = NewCronTask()
    results = task.run_screening()
    print(f"Completed: {len(results)} items")


if __name__ == '__main__':
    main()`,
        job: `#!/usr/bin/env python3
"""
New Manual Job - Description here
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class NewManualJob:
    """New Manual Job"""
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        logger = logging.getLogger('new_job')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """Run manual job"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"Running manual job: {trade_date}")
        
        # TODO: Implement job logic
        results = []
        
        self.logger.info(f"Job completed: {len(results)} items")
        return results


def main():
    job = NewManualJob()
    results = job.run_screening()
    print(f"Completed: {len(results)} items")


if __name__ == '__main__':
    main()`
    };
    
    return templates[category] || templates.screener;
}

async function saveScreener() {
    const originalName = document.getElementById('edit-original-name').value;
    const category = document.getElementById('edit-category').value;
    const name = document.getElementById('edit-name').value.trim();
    const displayName = document.getElementById('edit-display-name').value.trim();
    const description = document.getElementById('edit-description').value.trim();
    const code = document.getElementById('edit-code').value;
    const statusEl = document.getElementById('edit-status');
    
    if (!name || !displayName) {
        statusEl.innerHTML = '<span class="error">Name and Display Name are required</span>';
        return;
    }
    
    if (!code) {
        statusEl.innerHTML = '<span class="error">Code is required</span>';
        return;
    }
    
    statusEl.innerHTML = '<span class="loading">Saving...</span>';
    
    try {
        let response;
        
        if (isEditing) {
            // Update existing
            response = await fetch(`${API_BASE}/api/screeners/${originalName}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: code,
                    display_name: displayName,
                    description: description
                })
            });
        } else {
            // Create new
            response = await fetch(`${API_BASE}/api/screeners`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    display_name: displayName,
                    description: description,
                    category: category,
                    code: code
                })
            });
        }
        
        const data = await response.json();
        
        if (data.success) {
            statusEl.innerHTML = `<span class="success">✓ Saved successfully</span>`;
            
            // Add to MODULES if new
            if (!isEditing && data.screener) {
                MODULES[category].items.push(data.screener.name);
            }
            
            // Reload screeners
            await loadScreeners();
            
            setTimeout(closeAllModals, 1000);
        } else {
            statusEl.innerHTML = `<span class="error">✗ Error: ${data.error || 'Unknown error'}</span>`;
        }
    } catch (error) {
        statusEl.innerHTML = `<span class="error">✗ Failed: ${error.message}</span>`;
    }
}

// Delete Modal
let deleteTargetName = null;

function openDeleteModal(name, displayName) {
    deleteTargetName = name;
    document.getElementById('delete-target-name').textContent = displayName;
    document.getElementById('delete-modal').classList.add('active');
}

async function deleteScreener() {
    if (!deleteTargetName) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/screeners/${deleteTargetName}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remove from MODULES
            for (const cat of Object.keys(MODULES)) {
                const idx = MODULES[cat].items.indexOf(deleteTargetName);
                if (idx > -1) {
                    MODULES[cat].items.splice(idx, 1);
                    break;
                }
            }
            
            // Reload screeners
            await loadScreeners();
            closeAllModals();
        } else {
            alert(`Error: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Failed: ${error.message}`);
    }
    
    deleteTargetName = null;
}

async function viewScreenerDetail(name) {
    try {
        const response = await fetch(`${API_BASE}/api/screeners/${name}`);
        const data = await response.json();
        
        document.getElementById('detail-title').textContent = data.screener?.display_name || name;
        document.getElementById('detail-code').textContent = data.source_code || 'No code available';
        document.getElementById('detail-modal').classList.add('active');
    } catch (error) {
        alert('Failed to load screener details');
    }
}

// Results Page
async function loadResultsPage() {
    populateResultsDropdown();
}

// 当前结果数据（用于下载）
let currentResultsData = null;
let currentScreenerName = null;
let currentDate = null;

async function loadResults() {
    const screener = document.getElementById('results-screener-select').value;
    let date = document.getElementById('results-date-input').value;
    const container = document.getElementById('results-container');
    const toolbar = document.getElementById('results-toolbar');
    const info = document.getElementById('results-info');

    console.log('loadResults called:', { screener, date });

    if (!screener || !date) {
        alert('请选择筛选器和日期');
        return;
    }

    // Ensure date is in YYYY-MM-DD format
    // Input date from date picker is already in YYYY-MM-DD format
    // Just validate it looks correct
    console.log('Validating date:', date, 'regex test:', /^\d{4}-\d{2}-\d{2}$/.test(date));
    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        container.innerHTML = `<p class="empty-state">日期格式错误: ${date}</p>`;
        toolbar.style.display = 'none';
        return;
    }

    container.innerHTML = '<div class="loading">加载中...</div>';
    toolbar.style.display = 'none';

    try {
        const url = `${API_BASE}/api/results?screener=${screener}&date=${date}`;
        console.log('Fetching URL:', url);
        const response = await fetch(url);
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Response data:', data);

        if (data.error) {
            container.innerHTML = `<p class="empty-state">${data.error}</p>`;
            toolbar.style.display = 'none';
            return;
        }

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<p class="empty-state">该日期没有结果</p>';
            toolbar.style.display = 'none';
            return;
        }

        // 保存当前数据用于下载
        currentResultsData = data.results;
        currentScreenerName = screener;
        currentDate = date;

        // 显示工具栏
        const displayName = getScreenerDisplayName(screener);
        info.textContent = `${displayName} · ${date} · 共${data.results.length}只股票`;
        toolbar.style.display = 'flex';

        try {
            renderResultsTable(data.results, screener);
        } catch (renderError) {
            console.error('Render error:', renderError);
            container.innerHTML = `<p class="empty-state">渲染结果出错: ${renderError.message}</p>`;
            toolbar.style.display = 'none';
        }
    } catch (error) {
        console.error('Load error:', error);
        container.innerHTML = `<p class="empty-state">加载结果出错: ${error.message}</p>`;
        toolbar.style.display = 'none';
    }
}

// 获取筛选器显示名称
function getScreenerDisplayName(screenerName) {
    for (const cat of Object.keys(MODULES)) {
        if (MODULES[cat].displayNames && MODULES[cat].displayNames[screenerName]) {
            return MODULES[cat].displayNames[screenerName];
        }
    }
    return screenerName;
}

// 下载结果为Excel
function downloadResults() {
    if (!currentResultsData || currentResultsData.length === 0) {
        alert('没有数据可下载');
        return;
    }

    // 处理数据格式
    let displayResults = currentResultsData;
    if (currentResultsData[0].extra_data && typeof currentResultsData[0].extra_data === 'object') {
        displayResults = currentResultsData.map(r => r.extra_data);
    }

    // 获取字段列表
    const allHeaders = Object.keys(displayResults[0]).filter(h => !h.startsWith('_'));
    let headers = allHeaders;
    if (currentScreenerName && FIELD_ORDERS[currentScreenerName]) {
        const order = FIELD_ORDERS[currentScreenerName];
        headers = [
            ...order.filter(h => allHeaders.includes(h)),
            ...allHeaders.filter(h => !order.includes(h))
        ];
    }

    // 构建CSV内容
    const bom = '\uFEFF'; // UTF-8 BOM for Excel
    const headerRow = headers.map(h => getFieldDisplayName(h)).join(',');
    const rows = displayResults.map(r => {
        return headers.map(h => {
            const val = r[h];
            if (val === null || val === undefined) return '';
            const str = String(val);
            // 如果包含逗号或换行，用引号包裹
            if (str.includes(',') || str.includes('\n') || str.includes('"')) {
                return '"' + str.replace(/"/g, '""') + '"';
            }
            return str;
        }).join(',');
    });

    const csv = bom + headerRow + '\n' + rows.join('\n');

    // 下载文件
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const displayName = getScreenerDisplayName(currentScreenerName);
    const filename = `${displayName}_${currentDate}.csv`;
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}

// 各筛选器的字段排序配置
const FIELD_ORDERS = {
    // 二板回调
    'er_ban_hui_tiao_screener': [
        'code', 'name', 'industry',
        'current_price', 'pct_change', 'turnover',
        'er_ban_date', 'days_ago', 'first_low', 'second_high',
        'support_price', 'support_distance',
        'bei_liang_volume', 'zt_volume', 'volume_ratio',
        'hui_tiao_status'
    ],
    // 咖啡杯形态
    'coffee_cup_screener': [
        'code', 'name', 'industry',
        'close', 'pct_change', 'turnover',
        'volume_ratio', 'amount',
        'handle_date', 'days_apart', 'handle_price', 'cup_rim_price',
        'price_diff_pct', 'cup_depth_pct'
    ],
    // 涨停倍量阴
    'zhang_ting_bei_liang_yin_screener': [
        'code', 'name', 'industry',
        'current_price', 'pct_change', 'turnover',
        'zt_date', 'bei_liang_date', 'di_liang_date', 'days_ago',
        'zt_close', 'bei_liang_open', 'bei_liang_close',
        'volume_ratio', 'di_liang_ratio',
        'support_price', 'support_distance'
    ],
    // 金凤皇 - 涨停后横盘突破
    'jin_feng_huang_screener': [
        'code', 'name', 'industry',
        'current_price', 'current_change', 'turnover',
        'limit_up_date', 'days_since_limit_up', 'limit_up_price', 'limit_up_high',
        'gap_high', 'gap_low', 'consolidation_days', 'consolidation_high', 'consolidation_low',
        'has_shrink_volume', 'breakout_date', 'limit_up_volume'
    ],
    // 银凤皇 - 涨停后回调企稳
    'yin_feng_huang_screener': [
        'code', 'name', 'industry',
        'current_price', 'current_change', 'turnover',
        'limit_up_date', 'days_since_limit_up', 'limit_up_price',
        'support_price', 'callback_days', 'callback_low', 'callback_high',
        'volume_ratio', 'near_support'
    ],
    // 试盘线 - 高量阳线后涨停回调
    'shi_pan_xian_screener': [
        'code', 'name', 'industry',
        'current_price', 'current_change', 'turnover',
        'high_volume_date', 'limit_up_date', 'days_between',
        'high_volume_price', 'high_volume', 'limit_up_price', 'limit_up_high',
        'callback_low', 'callback_days', 'volume_ratio'
    ],
    // 20日突破
    'breakout_20day_screener': [
        'code', 'name', 'industry',
        'close', 'pct_change', 'turnover',
        'breakout_date', 'breakout_type', 'volume_ratio', 'ma20', 'ma60'
    ],
    // 每日最热股
    'daily_hot_screener': [
        'code', 'name', 'board', 'industry',
        'close', 'pct_change', 'amount', 'turnover',
        'total_market_cap', 'circulating_cap', 'pe', 'pb',
        'total_limit_up', 'return_5d', 'return_10d', 'return_20d', 'return_60d',
        'listing_date', 'anomaly_type'
    ],
    // 每日热股（旧版，兼容）
    'daily_hot_cold_screener': [
        'code', 'name', 'industry',
        'close', 'pct_change', 'amount', 'turnover',
        'market_cap', 'circulating_cap', 'pe', 'pb',
        'continuous_limit_up', 'total_limit_up', 'limit_up_days',
        'return_5d', 'return_10d', 'return_20d', 'return_60d',
        'listing_date', 'abnormal_type'
    ]
};

// 字段名映射：英文 -> 中文
const FIELD_NAME_MAP = {
    // 基础字段
    'code': '代码',
    'name': '名称',
    'stock_code': '代码',
    'stock_name': '名称',
    
    // 价格相关
    'close': '收盘价',
    'current_price': '当前价',
    'price': '价格',
    'open': '开盘价',
    'high': '最高价',
    'low': '最低价',
    
    // 涨跌幅
    'pct_change': '涨幅%',
    'change': '涨跌额',
    'change_pct': '涨幅%',
    
    // 成交量/额
    'volume': '成交量',
    'amount': '成交额',
    'turnover': '换手率%',
    'turnover_rate': '换手率%',
    
    // 市值
    'market_cap': '总市值',
    'total_market_cap': '总市值',
    'circulating_cap': '流通市值',
    'float_market_cap': '流通市值',
    
    // 估值
    'pe': '市盈率',
    'pe_ratio': '市盈率',
    'pb': '市净率',
    'pb_ratio': '市净率',
    
    // 日期
    'trade_date': '交易日期',
    'date': '日期',
    'listing_date': '上市日期',
    
    // 其他
    'industry': '行业',
    'sector': '板块',
    'concept': '概念',
    'reason': '原因',
    'signal': '信号',
    'score': '评分',
    'rank': '排名',
    
    // 二板回调专用
    'er_ban_date': '二板日期',
    'days_ago': '距今天数',
    'first_low': '首板最低价',
    'second_high': '二板最高价',
    'support_distance': '支撑位距离%',
    'hui_tiao_status': '回调状态',
    'support_price': '支撑位',
    'bei_liang_volume': '倍量阴成交量',
    'zt_volume': '涨停成交量',

    // 金凤皇专用
    'limit_up_date': '涨停日期',
    'days_since_limit_up': '距涨停天数',
    'limit_up_price': '涨停价',
    'limit_up_high': '涨停最高价',
    'gap_high': '缺口上沿',
    'gap_low': '缺口下沿',
    'consolidation_days': '横盘天数',
    'consolidation_high': '横盘高点',
    'consolidation_low': '横盘低点',
    'has_shrink_volume': '是否缩量',
    'breakout_date': '突破日期',
    'limit_up_volume': '涨停成交量',
    'current_change': '当日涨幅%',

    // 银凤皇专用
    'support_price': '支撑位',
    'callback_days': '回调天数',
    'callback_low': '回调低点',
    'callback_high': '回调高点',
    'near_support': '接近支撑',

    // 试盘线专用
    'high_volume_date': '高量日期',
    'days_between': '间隔天数',
    'high_volume_price': '高量阳线价',
    'high_volume': '高量成交量',
    'callback_low': '回调低点',

    // 20日突破专用
    'breakout_date': '突破日期',
    'breakout_type': '突破类型',
    'ma20': '20日均线',
    'ma60': '60日均线',

    // 每日最热股专用
    'board': '板块',
    'total_market_cap': '总市值(亿)',
    'circulating_cap': '流通市值(亿)',

    // 多日涨幅
    'pct_change_5d': '5日涨幅%',
    'pct_change_10d': '10日涨幅%',
    'pct_change_20d': '20日涨幅%',
    'pct_change_60d': '60日涨幅%',
    'return_5d': '5日涨幅%',
    'return_10d': '10日涨幅%',
    'return_20d': '20日涨幅%',
    'return_60d': '60日涨幅%',
    
    // 涨停统计
    'continuous_limit_up': '连续涨停天数',
    'total_limit_up': '累计涨停天数',
    'limit_up_count': '涨停次数',
    'limit_up_days': '几天几板',
    
    // 异动类型
    'abnormal_type': '异动类型',
    'anomaly_type': '异动类型',
    
    // 数据库内部字段（隐藏）
    'id': '_id',
    'run_id': '_run_id',
    'created_at': '_created_at',
    'extra_data': '_extra_data',
    '_category': '_category'
};

function getFieldDisplayName(fieldName) {
    return FIELD_NAME_MAP[fieldName] || fieldName;
}

function renderResultsTable(results, screenerName) {
    const container = document.getElementById('results-container');

    // DEBUG
    console.log('renderResultsTable called:', screenerName, 'results count:', results.length);

    // 处理 extra_data 格式的数据（如 daily_hot_screener, daily_hot_cold_screener 等）
    let displayResults = results;
    if (results.length > 0 && results[0].extra_data && typeof results[0].extra_data === 'object') {
        // DEBUG
        console.log('Processing extra_data format, first result keys:', Object.keys(results[0]));
        console.log('First extra_data keys:', Object.keys(results[0].extra_data || {}));

        // 提取 extra_data 中的字段，并映射 code/name 字段
        displayResults = results.map(r => {
            const extra = r.extra_data || {};
            return {
                ...extra,
                // 确保 code 和 name 字段存在（从顶层获取）
                code: r.stock_code,
                name: r.stock_name,
                _source_code: r.stock_code,
                _source_name: r.stock_name
            };
        });
    }

    if (displayResults.length === 0) {
        container.innerHTML = '<p class="empty-state">无数据</p>';
        return;
    }

    // DEBUG
    console.log('displayResults[0] keys:', Object.keys(displayResults[0]));

    // 获取所有字段并过滤掉内部字段
    const allHeaders = Object.keys(displayResults[0]).filter(h => !h.startsWith('_'));

    // DEBUG
    console.log('allHeaders:', allHeaders);

    if (allHeaders.length === 0) {
        container.innerHTML = '<p class="empty-state">数据格式错误：无可用字段</p>';
        return;
    }

    // 应用字段排序
    let headers = allHeaders;
    if (screenerName && FIELD_ORDERS[screenerName]) {
        const order = FIELD_ORDERS[screenerName];
        // 按配置顺序排列，未配置的字段放在最后
        headers = [
            ...order.filter(h => allHeaders.includes(h)),
            ...allHeaders.filter(h => !order.includes(h))
        ];
    }

    const html = `
        <table class="results-table">
            <thead>
                <tr>
                    ${headers.map(h => `<th>${getFieldDisplayName(h)}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
                ${displayResults.map(r => `
                    <tr>
                        ${headers.map(h => {
                            const val = r[h];
                            // 代码字段可点击显示图表
                            if (h === 'code' || h === 'stock_code') {
                                const code = val || r._source_code || '';
                                return `<td><span class="stock-code" onclick="showChart('${code}')">${code}</span></td>`;
                            }
                            // 名称字段
                            if (h === 'name' || h === 'stock_name') {
                                const name = val || r._source_name || '';
                                return `<td>${name}</td>`;
                            }
                            // 空值显示 -
                            if (val === null || val === undefined || val === '') {
                                return `<td>-</td>`;
                            }
                            // 数字格式化
                            if (typeof val === 'number') {
                                // 百分比字段
                                if (h.includes('pct') || h.includes('return') || h.includes('change') || h.includes('distance') || h.includes('rate')) {
                                    return `<td>${val.toFixed(2)}%</td>`;
                                }
                                // 价格字段
                                if (h.includes('price') || h.includes('close') || h.includes('open') || h.includes('high') || h.includes('low')) {
                                    return `<td>${val.toFixed(2)}</td>`;
                                }
                                // 大数字（市值、成交额）
                                if (h.includes('cap') || h.includes('amount') || h.includes('volume')) {
                                    if (val >= 100000000) {
                                        return `<td>${(val / 100000000).toFixed(2)}亿</td>`;
                                    } else if (val >= 10000) {
                                        return `<td>${(val / 10000).toFixed(2)}万</td>`;
                                    }
                                }
                                return `<td>${val.toFixed ? val.toFixed(2) : val}</td>`;
                            }
                            return `<td>${val}</td>`;
                        }).join('')}
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = html;
}

// Calendar
async function loadCalendar() {
    const container = document.getElementById('calendar-container');
    container.innerHTML = '<div class="loading">Loading calendar...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/api/calendar`);
        const data = await response.json();
        
        renderCalendar(data.calendar || []);
    } catch (error) {
        container.innerHTML = `<p class="empty-state">Error loading calendar</p>`;
    }
}

function renderCalendar(calendarData) {
    const container = document.getElementById('calendar-container');

    if (!calendarData || calendarData.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无数据</p>';
        return;
    }

    // Group by month
    const byMonth = {};
    calendarData.forEach(day => {
        const month = day.date.substring(0, 7);
        if (!byMonth[month]) byMonth[month] = [];
        byMonth[month].push(day);
    });

    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];

    let html = '<div class="calendar-compact">';
    Object.entries(byMonth).forEach(([month, days]) => {
        const firstDay = new Date(month + '-01');
        const startOffset = firstDay.getDay();
        const year = parseInt(month.substring(0, 4));
        const mon = parseInt(month.substring(5, 7));
        const daysInMonth = new Date(year, mon, 0).getDate();

        // 计算该月总股票数和运行次数
        const monthTotal = days.reduce((sum, d) => sum + d.total_stocks, 0);
        const monthRuns = days.length;

        html += `
            <div class="calendar-month-compact">
                <div class="calendar-month-header-compact">
                    <span class="month-year">${year}年${mon}月</span>
                    <span class="month-stats">${monthRuns}次运行 · ${monthTotal}只股票</span>
                </div>
                <div class="calendar-grid-compact">
                    ${weekDays.map(d => `<div class="calendar-weekday-compact">${d}</div>`).join('')}
                    ${Array(startOffset).fill('<div class="calendar-day-empty-compact"></div>').join('')}
                    ${Array(daysInMonth).fill(0).map((_, i) => {
                        const dayNum = i + 1;
                        const dayStr = dayNum.toString().padStart(2, '0');
                        const dateStr = `${month}-${dayStr}`;
                        const dayData = days.find(d => d.date === dateStr);
                        const hasData = dayData && dayData.total_stocks > 0;
                        const stockCount = hasData ? dayData.total_stocks : 0;
                        const runCount = hasData ? dayData.screeners.length : 0;

                        return `
                            <div class="calendar-day-compact ${hasData ? 'has-data' : ''}"
                                 onclick="viewDayResults('${dateStr}')"
                                 title="${dateStr}${hasData ? ' - ' + runCount + '个筛选器 · ' + stockCount + '只股票' : ''}">
                                <span class="day-num">${dayNum}</span>
                                ${hasData ? `<span class="day-dot"></span>` : ''}
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    });
    html += '</div>';

    container.innerHTML = html;
}

function viewDayResults(date) {
    // date is already in YYYY-MM-DD format from the calendar
    document.getElementById('results-date-input').value = date;
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelector('.nav-item[data-page="results"]').classList.add('active');
    switchPage('results');
}

// Chart
async function showChart(stockCode) {
    document.getElementById('chart-title').textContent = `Stock Chart: ${stockCode}`;
    document.getElementById('chart-modal').classList.add('active');
    
    try {
        const response = await fetch(`${API_BASE}/api/stock/${stockCode}/chart`);
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('chart-container').innerHTML = `<p class="empty-state">${data.error}</p>`;
            return;
        }
        
        renderChart(data.data);
    } catch (error) {
        document.getElementById('chart-container').innerHTML = `<p class="empty-state">Error loading chart</p>`;
    }
}

function renderChart(data) {
    const chartDom = document.getElementById('chart-container');
    const myChart = echarts.init(chartDom);
    
    const dates = data.map(d => d.date);
    const values = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume);
    
    const option = {
        backgroundColor: 'transparent',
        grid: [
            { left: '10%', right: '8%', height: '50%' },
            { left: '10%', right: '8%', top: '68%', height: '16%' }
        ],
        xAxis: [
            { type: 'category', data: dates, scale: true, axisLine: { lineStyle: { color: '#94a3b8' } } },
            { type: 'category', gridIndex: 1, data: dates, axisLine: { lineStyle: { color: '#94a3b8' } } }
        ],
        yAxis: [
            { scale: true, axisLine: { lineStyle: { color: '#94a3b8' } }, splitLine: { lineStyle: { color: '#334155' } } },
            { scale: true, gridIndex: 1, axisLine: { lineStyle: { color: '#94a3b8' } }, splitLine: { lineStyle: { color: '#334155' } } }
        ],
        series: [
            {
                type: 'candlestick',
                data: values,
                itemStyle: {
                    color: '#ef4444',
                    color0: '#10b981',
                    borderColor: '#ef4444',
                    borderColor0: '#10b981'
                }
            },
            {
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes,
                itemStyle: { color: '#3b82f6' }
            }
        ]
    };
    
    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// 将函数暴露到全局作用域，供 HTML onclick 调用
window.showChart = showChart;
window.viewDayResults = viewDayResults;
window.switchPage = switchPage;
window.openRunModal = openRunModal;
window.openEditModal = openEditModal;
window.openDeleteModal = openDeleteModal;
window.closeAllModals = closeAllModals;
window.viewScreenerDetail = viewScreenerDetail;
window.openAddModal = openAddModal;

// 检查股票弹窗
let currentCheckScreener = null;

function openCheckModal(screenerName, displayName) {
    currentCheckScreener = screenerName;
    alert("检查功能开发中: " + displayName);
}

window.openCheckModal = openCheckModal;


// 检查股票弹窗功能
let currentCheckScreener = null;

function openCheckModal(screenerName, displayName) {
    currentCheckScreener = screenerName;
    document.getElementById('check-screener-name').textContent = displayName || screenerName;
    document.getElementById('check-stock-code').value = '';
    document.getElementById('check-result').style.display = 'none';
    document.getElementById('check-status').innerHTML = '';
    
    // 设置默认日期为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('check-date').value = today;
    
    const modal = document.getElementById('check-modal');
    modal.style.display = 'block';
    modal.classList.add('active');
}

async function checkSingleStock() {
    const code = document.getElementById('check-stock-code').value.trim();
    const date = document.getElementById('check-date').value;
    const statusEl = document.getElementById('check-status');
    const resultEl = document.getElementById('check-result');
    const resultContentEl = document.getElementById('check-result-content');
    
    if (!code) {
        statusEl.innerHTML = '<span class="error">请输入股票代码</span>';
        return;
    }
    
    statusEl.innerHTML = '<span class="loading">检查中...</span>';
    resultEl.style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/api/check-stock`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Basic ' + btoa('user:neiltrade123')
            },
            body: JSON.stringify({
                screener: currentCheckScreener,
                code: code,
                date: date
            })
        });
        
        if (!response.ok) {
            throw new Error('请求失败: ' + response.status);
        }
        
        const data = await response.json();
        
        statusEl.innerHTML = '';
        resultEl.style.display = 'block';
        
        if (data.match) {
            // 符合条件
            let detailsHtml = '';
            if (data.details && Object.keys(data.details).length > 0) {
                detailsHtml = '<div class="check-details"><table class="check-details-table">';
                for (const [key, value] of Object.entries(data.details)) {
                    detailsHtml += `<tr><td>${key}</td><td>${value}</td></tr>`;
                }
                detailsHtml += '</table></div>';
            }
            
            let riskHtml = '';
            if (data.risk_management && Object.keys(data.risk_management).length > 0) {
                riskHtml = '<div class="risk-management"><div class="risk-title">📊 风控建议</div><div class="risk-content">';
                for (const [key, value] of Object.entries(data.risk_management)) {
                    riskHtml += `<div class="risk-item"><span class="risk-label">${key}:</span><span class="risk-value">${value}</span></div>`;
                }
                riskHtml += '</div></div>';
            }
            
            resultContentEl.innerHTML = `
                <div class="check-result-success">
                    <div class="check-result-icon">✅</div>
                    <div class="check-result-title">符合筛选条件</div>
                    <div class="check-result-details">
                        <p><strong>股票:</strong> ${data.code} ${data.name || ''}</p>
                        <p><strong>日期:</strong> ${data.date}</p>
                        ${detailsHtml}
                        ${riskHtml}
                    </div>
                </div>
            `;
        } else {
            // 不符合条件
            let reasonsHtml = '';
            if (data.reasons && data.reasons.length > 0) {
                reasonsHtml = '<div class="check-reasons-list"><strong>原因:</strong><ul>' + 
                    data.reasons.map(r => `<li>${r}</li>`).join('') + 
                    '</ul></div>';
            }
            
            resultContentEl.innerHTML = `
                <div class="check-result-fail">
                    <div class="check-result-icon">❌</div>
                    <div class="check-result-title">不符合筛选条件</div>
                    <div class="check-result-reasons">
                        <p><strong>股票:</strong> ${data.code} ${data.name || ''}</p>
                        <p><strong>日期:</strong> ${data.date}</p>
                        ${reasonsHtml}
                    </div>
                </div>
            `;
        }
    } catch (error) {
        statusEl.innerHTML = `<span class="error">✗ 错误: ${error.message}</span>`;
    }
}

// 绑定事件
document.addEventListener('DOMContentLoaded', () => {
    const confirmCheckBtn = document.getElementById('confirm-check-btn');
    if (confirmCheckBtn) {
        confirmCheckBtn.addEventListener('click', checkSingleStock);
    }
    
    // 绑定关闭按钮
    const checkModalClose = document.querySelector('#check-modal .close-btn');
    if (checkModalClose) {
        checkModalClose.addEventListener('click', closeAllModals);
    }
});

window.openCheckModal = openCheckModal;
