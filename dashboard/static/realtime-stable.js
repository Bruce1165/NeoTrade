/**
 * Production-Ready Realtime Button Integration
 * Reliable, non-intrusive injection of Realtime Run button
 */
(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        apiEndpoint: '/api/screener/{name}/realtime-run',
        buttonText: '⚡ Realtime',
        buttonClass: 'btn-realtime-run',
        debounceMs: 100
    };
    
    // Screener name mapping: display name -> API name
    const NAME_MAP = {
        'coffee_cup': 'coffee_cup_screener',
        'zhangting_beiliangyin': 'zhang_ting_bei_liang_yin_screener',
        'jinfenghuang': 'jin_feng_huang_screener',
        'yinfenghuang': 'yin_feng_huang_screener',
        'erban_huitiao': 'er_ban_hui_tiao_screener',
        'shipanxian': 'shi_pan_xian_screener',
        'breakout_20day': 'breakout_20day_screener',
        'breakout_main': 'breakout_main_screener',
        'daily_hot_cold': 'daily_hot_cold_screener',
        'ascending_triangle': 'ascending_triangle_screener',
        'double_bottom': 'double_bottom_screener',
        'high_tight_flag': 'high_tight_flag_screener',
        'flat_base': 'flat_base_screener',
        'ashare_21': 'ashare_21_screener',
        'shuang_shou_ban': 'shuang_shou_ban_screener'
    };
    
    // Track processed modals
    const processedModals = new WeakSet();
    let checkInterval = null;
    
    // Add styles once
    function injectStyles() {
        if (document.getElementById('realtime-btn-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'realtime-btn-styles';
        style.textContent = `
            .${CONFIG.buttonClass} {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                margin-left: 12px;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                transition: all 0.2s ease;
                box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
            }
            .${CONFIG.buttonClass}:hover {
                opacity: 0.9;
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
            }
            .${CONFIG.buttonClass}:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .${CONFIG.buttonClass}.loading::after {
                content: '';
                width: 14px;
                height: 14px;
                border: 2px solid transparent;
                border-top-color: white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
        `;
        document.head.appendChild(style);
    }
    
    // Detect screener name from modal content
    function detectScreenerName(modal) {
        if (!modal) return null;
        
        const text = modal.textContent.toLowerCase();
        
        // Check all mapped names
        for (const [shortName, fullName] of Object.entries(NAME_MAP)) {
            const patterns = shortName.split('_');
            const matches = patterns.every(p => text.includes(p));
            if (matches) return fullName;
        }
        
        // Fallback: try to extract from title
        const titleEl = modal.querySelector('h2, h3, .modal-title, [class*="title"]');
        if (titleEl) {
            const title = titleEl.textContent.toLowerCase().replace(/\s+/g, '_');
            for (const [shortName, fullName] of Object.entries(NAME_MAP)) {
                if (title.includes(shortName.replace('_', ''))) {
                    return fullName;
                }
            }
        }
        
        return null;
    }
    
    // Find the RUN button in modal
    function findRunButton(modal) {
        if (!modal) return null;
        
        const buttons = modal.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent.trim().toUpperCase();
            if (text === 'RUN' || text.includes('运行')) {
                return btn;
            }
        }
        return null;
    }
    
    // Create and inject realtime button
    function injectButton(modal) {
        if (processedModals.has(modal)) return;
        
        const runBtn = findRunButton(modal);
        if (!runBtn) return;
        
        // Check if already injected
        if (runBtn.parentNode.querySelector(`.${CONFIG.buttonClass}`)) {
            processedModals.add(modal);
            return;
        }
        
        const screenerName = detectScreenerName(modal);
        if (!screenerName) {
            console.log('[Realtime] Could not detect screener name');
            return;
        }
        
        console.log('[Realtime] Injecting button for:', screenerName);
        
        const btn = document.createElement('button');
        btn.className = CONFIG.buttonClass;
        btn.innerHTML = CONFIG.buttonText;
        btn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            runRealtime(screenerName, btn);
        };
        
        runBtn.parentNode.insertBefore(btn, runBtn.nextSibling);
        processedModals.add(modal);
    }
    
    // Execute realtime run
    async function runRealtime(name, button) {
        button.disabled = true;
        button.classList.add('loading');
        button.innerHTML = '⚡ Running...';
        
        try {
            const url = CONFIG.apiEndpoint.replace('{name}', name);
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            
            if (data.success) {
                const count = data.stocks_found || data.count || 0;
                alert(`✅ Realtime scan complete!\nFound ${count} stocks\nSaved to: ${data.file_path || data.output_file || 'results'}`);
            } else {
                alert(`❌ Error: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            alert(`❌ Request failed: ${error.message}`);
        } finally {
            button.disabled = false;
            button.classList.remove('loading');
            button.innerHTML = CONFIG.buttonText;
        }
    }
    
    // Check for open modals
    function checkModals() {
        const modals = document.querySelectorAll(
            '[class*="modal"]:not([class*="backdrop"]), ' +
            '[role="dialog"], ' +
            '[class*="dialog"], ' +
            '[class*="overlay"] > div'
        );
        
        modals.forEach(modal => {
            // Check if modal is visible
            const style = window.getComputedStyle(modal);
            if (style.display !== 'none' && style.visibility !== 'hidden') {
                injectButton(modal);
            }
        });
    }
    
    // Initialize
    function init() {
        injectStyles();
        
        // Check periodically
        checkInterval = setInterval(checkModals, 500);
        
        // Also check on DOM changes
        const observer = new MutationObserver(() => {
            checkModals();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        
        console.log('[Realtime] Initialized');
    }
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (checkInterval) clearInterval(checkInterval);
    });
    
    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();