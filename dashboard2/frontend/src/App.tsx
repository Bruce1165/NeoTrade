import { useState, useEffect, useRef } from 'react';
import './App.css';
import * as echarts from 'echarts';
import { formatDate, formatStockCode, getYesterday, isValidDate, isValidStockCode, toISODate } from './utils/format';

// Backend API configuration
// Use proxy in development, ngrok in production
const API_BASE = import.meta.env.DEV ? '/api' : 'https://chariest-nancy-nonincidentally.ngrok-free.dev/api';
const AUTH_HEADER = 'Basic ' + btoa('user:neiltrade123');

interface Screener {
  id: number;
  name: string;
  display_name: string;
  description: string;
  category: string;
}

interface CheckResult {
  match: boolean;
  code: string;
  name: string;
  date: string;
  details: Record<string, any>;
  reasons: string[];
}

function App() {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [loading, setLoading] = useState(true);
  
  // 读取 URL 参数初始化 activeTab
  const getInitialTab = () => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    return tab || 'screeners';
  };
  
  const [activeTab, setActiveTab] = useState(getInitialTab());

  // Update URL when tab changes
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabId);
    window.history.replaceState({}, '', url.toString());
  };

  useEffect(() => {
    fetch(`${API_BASE}/screeners`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(data => { setScreeners(data.screeners || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'screeners', label: 'Screeners', icon: '🔍' },
    { id: 'results', label: 'Results', icon: '📈' },
  ];

  const renderContent = () => {
    switch(activeTab) {
      case 'dashboard': return <DashboardView />;
      case 'screeners': return <ScreenersView screeners={screeners} loading={loading} />;
      case 'results': return <ResultsView screeners={screeners} />;
      default: return <ScreenersView screeners={screeners} loading={loading} />;
    }
  };

  return (
    <div className="wsj-dashboard">
      <header className="market-bar">
        <div className="market-ticker">
          <span className="index">上证指数 <span className="up">+0.85%</span></span>
          <span className="index">深证成指 <span className="up">+1.12%</span></span>
          <span className="index">创业板指 <span className="down">-0.23%</span></span>
          <span className="time">{new Date().toLocaleTimeString()}</span>
        </div>
        <h1 className="logo">NEO TERMINAL</h1>
      </header>

      <div className="main-layout">
        <nav className="sidebar">
          {menuItems.map(item => (
            <div key={item.id} className={`menu-item ${activeTab === item.id ? 'active' : ''}`} onClick={() => handleTabChange(item.id)}>
              <span className="icon">{item.icon}</span>
              <span className="label">{item.label}</span>
            </div>
          ))}
        </nav>

        <main className="content">{renderContent()}</main>
      </div>
    </div>
  );
}

// Dashboard
function DashboardView() {
  const [stats, setStats] = useState({ screeners: 18, oneil: 5, lastUpdate: 'Loading...' });

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(d => {
      if (d.data_date) setStats(s => ({ ...s, lastUpdate: d.data_date }));
    }).catch(() => setStats(s => ({ ...s, lastUpdate: 'N/A' })));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h2>Market Dashboard</h2>
        <span className="subtitle">Real-time market overview</span>
      </div>
      <div className="dashboard-stats">
        <div className="stat-card"><div className="stat-value">{stats.screeners}</div><div className="stat-label">Active Screeners</div></div>
        <div className="stat-card"><div className="stat-value">{stats.oneil}</div><div className="stat-label">O'Neil Patterns</div></div>
        <div className="stat-card"><div className="stat-value">{stats.lastUpdate}</div><div className="stat-label">Data Date</div></div>
      </div>
    </div>
  );
}

// Screeners with real functionality
function ScreenersView({ screeners, loading }: { screeners: Screener[], loading: boolean }) {
  const [checkModal, setCheckModal] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });
  const [runModal, setRunModal] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });

  return (
    <div>
      <div className="page-header">
        <h2>Stock Screeners</h2>
        <span className="count">{screeners.length} Strategies Available</span>
      </div>

      {loading ? <div className="loading">Loading screeners...</div> : (
        <div className="screener-grid">
          {screeners.map(s => (
            <div key={s.id} className="screener-card">
              <div className="card-header">
                <h3>{s.display_name || s.name}</h3>
                <span className="category">{s.category}</span>
              </div>
              <p className="description">{s.description?.substring(0, 120) || 'Technical analysis screener'}...</p>
              <div className="card-actions">
                <button className="btn-primary" onClick={() => setRunModal({ open: true, screener: s })}>Run Screener</button>
                <button className="btn-secondary" onClick={() => setCheckModal({ open: true, screener: s })}>Check Stock</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {checkModal.open && checkModal.screener && (
        <CheckStockModal screener={checkModal.screener} onClose={() => setCheckModal({ open: false, screener: null })} />
      )}
      {runModal.open && runModal.screener && (
        <RunScreenerModal screener={runModal.screener} onClose={() => setRunModal({ open: false, screener: null })} />
      )}
    </div>
  );
}

// Check Stock Modal - REAL FUNCTIONALITY
function CheckStockModal({ screener, onClose }: { screener: Screener, onClose: () => void }) {
  const [code, setCode] = useState('');
  const [date, setDate] = useState(() => toISODate(new Date()));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState('');

  const handleCheck = async () => {
    if (!code) return;
    
    // 格式化输入
    const formattedCode = formatStockCode(code);
    const formattedDate = formatDate(date);
    
    // 验证
    if (!isValidStockCode(formattedCode)) {
      setError('股票代码格式无效，请输入6位数字');
      return;
    }
    
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/check-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: JSON.stringify({ screener: screener.name, code: formattedCode, date: formattedDate })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Failed to check stock');
    }
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>🔍 Check Single Stock</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label>Screener: <strong>{screener.display_name}</strong></label>
          </div>
          <div className="form-row">
            <input type="text" placeholder="Stock Code (e.g. 600000)" value={code} onChange={e => setCode(e.target.value)} className="wsj-input" />
            <input 
              type="date" 
              value={date} 
              onChange={e => setDate(e.target.value)} 
              min="2024-01-01"
              max={new Date().toISOString().split('T')[0]}
              className="wsj-input" 
            />
            <button className="btn-primary" onClick={handleCheck} disabled={loading}>
              {loading ? 'Checking...' : 'Check'}
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}

          {result && (
            <div className={`result-box ${result.match ? 'success' : 'fail'}`}>
              <div className="result-header">
                <span className="result-icon">{result.match ? '✅' : '❌'}</span>
                <span className="result-text">{result.match ? 'MATCH' : 'NO MATCH'}</span>
              </div>
              <div className="result-details">
                <div><strong>Code:</strong> {result.code}</div>
                <div><strong>Name:</strong> {result.name}</div>
                <div><strong>Date:</strong> {result.date}</div>
              </div>
              {!result.match && result.reasons?.length > 0 && (
                <div className="fail-reasons">
                  <strong>Reasons:</strong>
                  <ul>{result.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                </div>
              )}
              {result.match && Object.keys(result.details).length > 0 && (
                <div className="match-details">
                  <strong>Details:</strong>
                  <pre>{JSON.stringify(result.details, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Run Screener Modal - REAL FUNCTIONALITY
function RunScreenerModal({ screener, onClose }: { screener: Screener, onClose: () => void }) {
  // Initialize with yesterday's date in YYYY-MM-DD format
  const [date, setDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [stocks, setStocks] = useState<any[]>([]);
  const [error, setError] = useState('');

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // HTML5 date input returns YYYY-MM-DD format
    const value = e.target.value;
    setDate(value);
  };

  const handleRun = async () => {
    setLoading(true);
    setError('');
    
    // Final validation and formatting
    const formattedDate = toISODate(date);
    
    if (!isValidDate(formattedDate)) {
      setError('日期格式无效，请使用 YYYY-MM-DD 格式 (例如: 2026-03-20)');
      setLoading(false);
      return;
    }
    
    try {
      const res = await fetch(`${API_BASE}/screeners/${screener.name}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: JSON.stringify({ date: formattedDate })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.message || data.error);
      setResult(data);
      
      // Fetch results for download
      if (data.success) {
        const resultsRes = await fetch(`${API_BASE}/results?screener=${screener.name}&date=${formattedDate}`, { 
          headers: { 'Authorization': AUTH_HEADER }
        });
        const resultsData = await resultsRes.json();
        setStocks(resultsData.results || []);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to run screener');
    }
    setLoading(false);
  };

  // Download handlers for screener results
  const downloadCSV = () => {
    if (stocks.length === 0) return;
    
    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col => 
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];
    
    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'stock_name': '名称', 'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%', 'turnover': '换手率%', 'volume': '成交量',
      'amount': '成交额', 'industry': '行业', 'category': '类别', 'type': '类型',
      'board': '板块', 'reason': '原因', 'signal': '信号', 'status': '状态',
      'score': '评分', 'rank': '排名', 'note': '备注', 'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pb_ratio': '市净率', 'listing_date': '上市日期'
    };
    
    const headers = columns.map(col => headerMap[col] || col).join(',');
    const rows = stocks.map(row => {
      const flatData = flattenObject(row);
      return columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '';
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',');
    });
    
    const csvContent = '\uFEFF' + [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const downloadExcel = () => {
    if (stocks.length === 0) return;
    
    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col => 
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];
    
    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'stock_name': '名称', 'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%', 'turnover': '换手率%', 'volume': '成交量',
      'amount': '成交额', 'industry': '行业', 'category': '类别', 'type': '类型',
      'board': '板块', 'reason': '原因', 'signal': '信号', 'status': '状态',
      'score': '评分', 'rank': '排名', 'note': '备注', 'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pb_ratio': '市净率', 'listing_date': '上市日期'
    };
    
    let html = '<table border="1">';
    html += '<tr>' + columns.map(col => `<th>${headerMap[col] || col}</th>`).join('') + '</tr>';
    
    stocks.forEach(row => {
      const flatData = flattenObject(row);
      html += '<tr>' + columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '<td></td>';
        return `<td>${val}</td>`;
      }).join('') + '</tr>';
    });
    
    html += '</table>';
    
    const blob = new Blob([`
      <html xmlns:o="urn:schemas-microsoft-com:office:office" 
            xmlns:x="urn:schemas-microsoft-com:office:excel" 
            xmlns="http://www.w3.org/TR/REC-html40">
        <head>
          <meta charset="UTF-8">
          <!--[if gte mso 9]>
          <xml>
            <x:ExcelWorkbook>
              <x:ExcelWorksheets>
                <x:ExcelWorksheet>
                  <x:Name>筛选结果</x:Name>
                  <x:WorksheetOptions>
                    <x:DisplayGridlines/>
                  </x:WorksheetOptions>
                </x:ExcelWorksheet>
              </x:ExcelWorksheets>
            </x:ExcelWorkbook>
          </xml>
          <![endif]-->
        </head>
        <body>${html}</body>
      </html>
    `], { type: 'application/vnd.ms-excel;charset=utf-8' });
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>▶ Run Screener</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label>Screener: <strong>{screener.display_name}</strong></label>
            <input 
              type="date" 
              value={date} 
              onChange={handleDateChange}
              min="2024-01-01"
              max={new Date().toISOString().split('T')[0]}
              className="wsj-input" 
            />
            <button className="btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? 'Running...' : 'Run'}
            </button>
          </div>
          {error && <div className="error-message">{error}</div>}
          {result && (
            <div className={`result-box ${result.success ? 'success' : 'fail'}`}>
              <div className="result-header">
                <span className="result-icon">{result.success ? '✅' : '❌'}</span>
                <span className="result-text">{result.success ? 'SUCCESS' : 'FAILED'}</span>
              </div>
              <div className="result-details">
                <div><strong>Run ID:</strong> {result.run_id}</div>
                <div><strong>Stocks Found:</strong> {result.stocks_found || 0}</div>
                <div><strong>Message:</strong> {result.message}</div>
              </div>
              {result.success && (
                <div className="download-actions" style={{ 
                  marginTop: '16px', 
                  paddingTop: '16px', 
                  borderTop: '1px solid var(--border-color)',
                  backgroundColor: '#f0f9ff',
                  padding: '12px',
                  borderRadius: '8px'
                }}>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    {stocks.length > 0 && (
                      <>
                        <Tooltip text="CSV works with all Excel versions">
                          <button className="btn-csv-primary" onClick={downloadCSV}>
                            📄 Download CSV
                          </button>
                        </Tooltip>
                        <button className="btn-excel-secondary" onClick={downloadExcel}>
                          📊 Excel
                        </button>
                      </>
                    )}
                    <button 
                      className="btn-view-results" 
                      onClick={() => {
                        window.location.href = `?tab=results&screener=${screener.name}&date=${formatDate(date)}`;
                      }}
                      style={{ backgroundColor: '#3b82f6', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                    >
                      👁️ View Results
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Tooltip component
function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}
         onMouseEnter={() => setShow(true)}
         onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'var(--um-blue)',
          color: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          fontSize: '12px',
          whiteSpace: 'nowrap',
          zIndex: 1000,
          marginBottom: '8px',
          boxShadow: '0 4px 12px rgba(0,39,76,0.3)',
        }}>
          {text}
          <div style={{
            position: 'absolute',
            top: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            border: '6px solid transparent',
            borderTopColor: 'var(--um-blue)',
          }} />
        </div>
      )}
    </div>
  );
}

// Helper function to flatten nested objects
function flattenObject(obj: any, prefix = ''): any {
  let result: any = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      const newKey = prefix ? `${prefix}.${key}` : key;
      if (obj[key] !== null && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
        Object.assign(result, flattenObject(obj[key], newKey));
      } else {
        result[newKey] = obj[key];
      }
    }
  }
  return result;
}

// Stock Chart Modal Component - ECharts Candlestick
function StockChartModal({ code, name, onClose }: { code: string, name: string, onClose: () => void }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    // 延迟初始化，确保弹窗完全显示且有尺寸
    const timer = setTimeout(() => {
      fetch(`${API_BASE}/stock/${code}/chart?days=60`, {
        headers: { 'Authorization': AUTH_HEADER }
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) throw new Error(data.error);
          if (data.data && data.data.length > 0) {
            // 再等待一下确保容器渲染完成
            setTimeout(() => renderChart(data.data), 200);
          } else {
            setError('无K线数据');
            setLoading(false);
          }
        })
        .catch(e => {
          setError(e.message);
          setLoading(false);
        });
    }, 300); // 等待弹窗动画完成

    return () => {
      clearTimeout(timer);
      if (chartInstance.current) {
        chartInstance.current.dispose();
      }
    };
  }, [code]);

  const renderChart = (data: any[]) => {
    if (!chartRef.current) {
      console.error('Chart container ref not available');
      setError('图表容器加载失败');
      setLoading(false);
      return;
    }

    // 强制使用固定尺寸渲染，不依赖容器实际尺寸
    forceRenderChart(data);
  };

  const forceRenderChart = (data: any[]) => {
    if (!chartRef.current) return;

    const dates = data.map(d => d.date);
    const values = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume);

    console.log('Initializing chart with', dates.length, 'data points');
    
    // 如果已有实例，先销毁
    if (chartInstance.current) {
      chartInstance.current.dispose();
    }
    
    try {
      chartInstance.current = echarts.init(chartRef.current);

      const option: echarts.EChartsOption = {
        backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      grid: [
        { left: '10%', right: '8%', height: '50%' },
        { left: '10%', right: '8%', top: '68%', height: '16%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          scale: true,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8' }
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100, bottom: 10 }
      ],
      series: [
        {
          name: 'K线',
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
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: {
            color: (params: any) => {
              const dataIndex = params.dataIndex;
              const close = values[dataIndex][1];
              const open = values[dataIndex][0];
              return close >= open ? '#ef4444' : '#10b981';
            }
          }
        }
      ]
    };

    chartInstance.current.setOption(option);
    
    // 图表渲染完成后再关闭 loading
    requestAnimationFrame(() => {
      setLoading(false);
    });
    
    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
    } catch (e: any) {
      console.error('Chart initialization error:', e);
      setError('图表渲染失败: ' + (e.message || 'Unknown error'));
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()} style={{ maxWidth: '900px' }}>
        <div className="modal-header">
          <h3>📈 {code} {name} - K线图</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body" style={{ minHeight: '540px' }}>
          {loading && <div className="loading">加载K线数据中...</div>}
          {error && <div className="error-message">{error}</div>}
          <div 
            ref={chartRef} 
            style={{ 
              width: '100%', 
              height: '500px', 
              minHeight: '500px',
              visibility: loading || error ? 'hidden' : 'visible'
            }}
          />
        </div>
      </div>
    </div>
  );
}

// Results Table Component - dynamically renders any data structure
function ResultsTable({ data, onStockClick }: { data: any[], onStockClick?: (code: string, name: string) => void }) {
  if (!data || data.length === 0) return null;
  
  const flatRow = flattenObject(data[0]);
  const columns = Object.keys(flatRow);
  
  let displayColumns = columns.filter(col => 
    !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
  );
  
  const priorityCols = ['stock_code', 'stock_name'];
  displayColumns = [
    ...priorityCols.filter(c => displayColumns.includes(c)),
    ...displayColumns.filter(c => !priorityCols.includes(c))
  ];
  
  const formatHeader = (col: string) => {
    const translations: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'preclose': '昨收',
      'open': '开盘',
      'high': '最高',
      'low': '最低',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'industry': '行业',
      'sector': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'listing_date': '上市日期',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pe': '市盈率',
      'pb_ratio': '市净率',
      'pb': '市净率',
      'extra_data.cup_depth_pct': '杯深%',
      'extra_data.handle_date': '柄部日期',
      'extra_data.days_apart': '间隔天数',
      'extra_data.days_since_handle': '距柄部天数',
      'extra_data.volume_ratio': '量比',
      'extra_data.handle_price': '柄部价格',
      'extra_data.cup_rim_price': '杯沿价格',
      'extra_data.price_diff_pct': '价格差异%',
      'extra_data.breakout_price': '突破价',
      'extra_data.breakout_pct': '突破%',
      'extra_data.total_limit_up': '累计涨停',
      'extra_data.total_limit_down': '累计跌停',
      'extra_data.pe': '市盈率',
      'extra_data.pb': '市净率',
      'extra_data.market_cap': '市值',
      'extra_data.industry': '行业',
      'extra_data.anomaly_type': '异动类型',
      'extra_data.board': '板块',
      'extra_data.anomaly_reason': '异动原因',
      'extra_data.limit_up_days': '涨停天数',
      'extra_data.return_5d': '5日涨幅%',
      'extra_data.return_10d': '10日涨幅%',
      'extra_data.return_20d': '20日涨幅%',
      'extra_data.return_60d': '60日涨幅%',
      // 每日热冷股特有字段
      'extra_data._category': '类别',
      'extra_data._type': '类型',
      'extra_data.amount': '成交额',
      'extra_data.circulating_cap': '流通市值',
      'extra_data.total_market_cap': '总市值',
      'extra_data.listing_date': '上市日期',
      'created_at': '创建时间',
      'updated_at': '更新时间',
      // 全大写版本（后端返回的格式）
      'CATEGORY': '类别',
      'TYPE': '类型',
      'BOARD': '板块',
      'INDUSTRY': '行业',
      'SECTOR': '板块',
      'REASON': '原因',
      'SIGNAL': '信号',
      'STATUS': '状态',
      'SCORE': '评分',
      'RANK': '排名',
      'NOTE': '备注',
      'AMOUNT': '成交额',
      'VOLUME': '成交量',
      'CLOSE_PRICE': '收盘价',
      'CLOSE': '收盘价',
      'PCT_CHANGE': '涨幅%',
      'CHANGE': '涨幅%',
      'TURNOVER': '换手率%',
      'OPEN': '开盘',
      'HIGH': '最高',
      'LOW': '最低',
      'PRE_CLOSE': '昨收',
      'LISTING_DATE': '上市日期',
      'TOTAL_MARKET_CAP': '总市值',
      'CIRCULATING_MARKET_CAP': '流通市值',
      'CIRCULATING_CAP': '流通市值',
      'PE_RATIO': '市盈率',
      'PE': '市盈率',
      'PB_RATIO': '市净率',
      'PB': '市净率',
      'STOCK_CODE': '代码',
      'STOCK_NAME': '名称'
    };
    return translations[col] || translations[col.toLowerCase()] || translations[col.toUpperCase()] || col.replace(/_/g, ' ').replace(/\./g, ' ').replace(/^extra data/, '');
  };
  
  const formatValue = (val: any, col: string): string => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      if (col.includes('pct') || col.includes('ratio') || col.includes('change')) {
        return val.toFixed(2) + '%';
      }
      if (!Number.isInteger(val)) {
        return val.toFixed(2);
      }
      return val.toLocaleString();
    }
    return String(val);
  };
  
  const isStockCode = (col: string) => col === 'stock_code' || col === 'code';
  
  return (
    <table className="result-table">
      <thead>
        <tr>
          {displayColumns.map(col => (
            <th key={col}>{formatHeader(col)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => {
          const flatData = flattenObject(row);
          const stockCode = flatData['stock_code'] || flatData['code'];
          const stockName = flatData['stock_name'] || flatData['name'];
          return (
            <tr key={i}>
              {displayColumns.map(col => (
                <td key={col}>
                  {isStockCode(col) && onStockClick ? (
                    <span 
                      className="stock-code-link" 
                      onClick={() => onStockClick(stockCode, stockName)}
                      style={{ cursor: 'pointer', color: '#00274C', fontWeight: 600, textDecoration: 'underline' }}
                    >
                      {formatValue(flatData[col], col)}
                    </span>
                  ) : (
                    formatValue(flatData[col], col)
                  )}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// Results View with real query
function ResultsView({ screeners }: { screeners: Screener[] }) {
  // 从 URL 读取初始参数
  const getInitialParams = () => {
    const params = new URLSearchParams(window.location.search);
    const rawDate = params.get('date') || getYesterday();
    return {
      screener: params.get('screener') || screeners[0]?.name || '',
      date: toISODate(rawDate)  // 统一格式化日期
    };
  };
  
  const initialParams = getInitialParams();
  const [date, setDate] = useState(() => toISODate(initialParams.date));
  const [screenerName, setScreenerName] = useState(initialParams.screener);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [selectedStock, setSelectedStock] = useState<{code: string, name: string} | null>(null);
  const [autoQueried, setAutoQueried] = useState(false);

  // 如果有 URL 参数，自动查询
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'results' && params.get('screener') && !autoQueried) {
      setAutoQueried(true);
      handleQuery();
    }
  }, []);

  const handleQuery = async () => {
    if (!screenerName) {
      setError('请选择一个筛选器');
      return;
    }
    setLoading(true);
    setError('');
    try {
      // 统一格式化日期
      const formattedDate = formatDate(date);
      const params = new URLSearchParams({ screener: screenerName, date: formattedDate });
      const res = await fetch(`${API_BASE}/results?${params}`, { headers: { 'Authorization': AUTH_HEADER }});
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResults(data.results || []);
    } catch (e: any) {
      setError(e.message || '获取结果失败');
      setResults([]);
    }
    setLoading(false);
  };

  // 下载 CSV 功能 - Primary option
  const downloadCSV = () => {
    if (results.length === 0) return;
    
    // 获取所有列
    const flatRow = flattenObject(results[0]);
    let columns = Object.keys(flatRow).filter(col => 
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );
    
    // 股票代码和名称放最前面
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];
    
    // 表头翻译
    const headerMap: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pb_ratio': '市净率',
      'listing_date': '上市日期'
    };
    
    // 构建 CSV 内容
    const headers = columns.map(col => headerMap[col] || col).join(',');
    const rows = results.map(row => {
      const flatData = flattenObject(row);
      return columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '';
        // Escape values with commas or quotes
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',');
    });
    
    const csvContent = '\uFEFF' + [headers, ...rows].join('\n'); // Add BOM for Excel Chinese support
    
    // 下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screenerName}_${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 下载 Excel 功能 - Secondary option
  const downloadExcel = () => {
    if (results.length === 0) return;
    
    // 获取所有列
    const flatRow = flattenObject(results[0]);
    let columns = Object.keys(flatRow).filter(col => 
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );
    
    // 股票代码和名称放最前面
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];
    
    // 表头翻译
    const headerMap: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pb_ratio': '市净率',
      'listing_date': '上市日期'
    };
    
    // 构建 HTML table (Excel 可以打开)
    let html = '<table border="1">';
    html += '<tr>' + columns.map(col => `<th>${headerMap[col] || col}</th>`).join('') + '</tr>';
    
    results.forEach(row => {
      const flatData = flattenObject(row);
      html += '<tr>' + columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '<td></td>';
        return `<td>${val}</td>`;
      }).join('') + '</tr>';
    });
    
    html += '</table>';
    
    // 下载为 Excel (正确的 MIME 类型)
    const blob = new Blob([`
      <html xmlns:o="urn:schemas-microsoft-com:office:office" 
            xmlns:x="urn:schemas-microsoft-com:office:excel" 
            xmlns="http://www.w3.org/TR/REC-html40">
        <head>
          <meta charset="UTF-8">
          <!--[if gte mso 9]>
          <xml>
            <x:ExcelWorkbook>
              <x:ExcelWorksheets>
                <x:ExcelWorksheet>
                  <x:Name>筛选结果</x:Name>
                  <x:WorksheetOptions>
                    <x:DisplayGridlines/>
                  </x:WorksheetOptions>
                </x:ExcelWorksheet>
              </x:ExcelWorksheets>
            </x:ExcelWorkbook>
          </xml>
          <![endif]-->
        </head>
        <body>${html}</body>
      </html>
    `], { type: 'application/vnd.ms-excel;charset=utf-8' });
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screenerName}_${date}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <div className="page-header">
        <h2>筛选结果</h2>
        <span className="subtitle">查看历史筛选结果</span>
      </div>

      <div className="query-form">
        <input 
          type="date" 
          value={date} 
          onChange={e => setDate(e.target.value)} 
          min="2024-01-01"
          max={new Date().toISOString().split('T')[0]}
          className="wsj-input" 
        />
        <select value={screenerName} onChange={e => setScreenerName(e.target.value)} className="wsj-select">
          <option value="" disabled>选择筛选器...</option>
          {screeners.map(s => <option key={s.id} value={s.name}>{s.display_name}</option>)}
        </select>
        <button className="btn-primary" onClick={handleQuery} disabled={loading || !screenerName}>
          {loading ? '查询中...' : '查看结果'}
        </button>
      </div>

      {error && <div className="error-message" style={{ marginBottom: '16px' }}>{error}</div>}

      {results.length > 0 ? (
        <>
          <div className="download-bar">
            <span className="record-count">共 {results.length} 条记录</span>
            <div className="download-buttons">
              <Tooltip text="CSV works with all Excel versions">
                <button className="btn-csv-primary" onClick={downloadCSV}>
                  📄 Download CSV (Recommended)
                </button>
              </Tooltip>
              <button className="btn-excel-secondary" onClick={downloadExcel}>
                📊 Download Excel
              </button>
            </div>
          </div>
          <div className="results-table-container">
            <ResultsTable data={results} onStockClick={(code, name) => setSelectedStock({code, name})} />
          </div>
        </>
      ) : (
        <div className="placeholder">{loading ? '加载中...' : '无结果。选择日期并点击查看结果。'}</div>
      )}

      {selectedStock && (
        <StockChartModal 
          code={selectedStock.code} 
          name={selectedStock.name} 
          onClose={() => setSelectedStock(null)} 
        />
      )}
    </div>
  );
}

export default App;
