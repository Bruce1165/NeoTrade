import React, { useState, useEffect, useMemo } from 'react';
import { PipelineColumn } from '../components/monitor/PipelineColumn';
import '../components/monitor/Monitor.css';

const API_BASE = import.meta.env.DEV ? '/api' : `${window.location.origin}/api`;
const AUTH_HEADER = 'Basic ' + btoa('user:NeoTrade2025');

interface DailyCheck {
  day: number;
  date: string;
  status: string;
  close_price?: number;
  note?: string;
}

interface Pick {
  id: number;
  screener_id: string;
  stock_code: string;
  entry_date: string;
  entry_price: number;
  expected_exit_date: string;
  status: 'active' | 'graduated' | 'failed';
  exit_date?: string;
  exit_reason?: string;
  daily_checks: DailyCheck[];
  created_at: string;
  cup_rim_price?: number;
  cup_bottom_price?: number;
  max_price_seen?: number;
}

interface Screener {
  id: number;
  name: string;
  display_name: string;
  pick_count: number;
}

interface PipelineData {
  screener_id: string;
  picks: Pick[];
  stats: {
    total: number;
    active: number;
    graduated: number;
    failed: number;
    win_rate: number;
  };
}

interface GroupedPicks {
  NEW: Pick[];
  EARLY: Pick[];
  MID: Pick[];
  LATE: Pick[];
  GRADUATED: Pick[];
  FAILED: Pick[];
}

const STAGES = [
  { key: 'NEW' as const, title: '今天新进', subtitle: 'Day 0', dayRange: [0, 0] },
  { key: 'EARLY' as const, title: '早期跟踪', subtitle: 'Day 1-5', dayRange: [1, 5] },
  { key: 'MID' as const, title: '中期跟踪', subtitle: 'Day 6-15', dayRange: [6, 15] },
  { key: 'LATE' as const, title: '后期跟踪', subtitle: 'Day 16-24', dayRange: [16, 24] },
  { key: 'GRADUATED' as const, title: '成功毕业', subtitle: 'Day 25+', dayRange: [25, 999] },
  { key: 'FAILED' as const, title: '已失败', subtitle: 'Stopped', dayRange: [-1, -1] },
];

export const Monitor: React.FC = () => {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [selectedScreener, setSelectedScreener] = useState<string>('');
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPick, setSelectedPick] = useState<Pick | null>(null);

  // Fetch screeners on mount
  useEffect(() => {
    fetch(`${API_BASE}/monitor/screeners`, { 
      headers: { 'Authorization': AUTH_HEADER }
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        setScreeners(data.screeners || []);
        if (data.screeners?.length > 0) {
          setSelectedScreener(data.screeners[0].name);
        }
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  // Fetch pipeline data when screener changes
  useEffect(() => {
    if (!selectedScreener) return;
    
    setLoading(true);
    fetch(`${API_BASE}/monitor/pipeline?screener_id=${selectedScreener}`, {
      headers: { 'Authorization': AUTH_HEADER }
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        setPipelineData(data);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [selectedScreener]);

  // Group picks by stage
  const groupedPicks: GroupedPicks = useMemo(() => {
    if (!pipelineData?.picks) {
      return { NEW: [], EARLY: [], MID: [], LATE: [], GRADUATED: [], FAILED: [] };
    }

    const groups: GroupedPicks = {
      NEW: [],
      EARLY: [],
      MID: [],
      LATE: [],
      GRADUATED: [],
      FAILED: [],
    };

    pipelineData.picks.forEach(pick => {
      // First check status
      if (pick.status === 'graduated') {
        groups.GRADUATED.push(pick);
        return;
      }
      if (pick.status === 'failed') {
        groups.FAILED.push(pick);
        return;
      }

      // Then check day count for active picks
      const dayCount = pick.daily_checks?.length || 0;
      
      if (dayCount === 0) {
        groups.NEW.push(pick);
      } else if (dayCount >= 1 && dayCount <= 5) {
        groups.EARLY.push(pick);
      } else if (dayCount >= 6 && dayCount <= 15) {
        groups.MID.push(pick);
      } else if (dayCount >= 16 && dayCount <= 24) {
        groups.LATE.push(pick);
      } else {
        groups.GRADUATED.push(pick);
      }
    });

    return groups;
  }, [pipelineData]);

  // Get stats from pipeline data
  const stats = pipelineData?.stats || { total: 0, active: 0, graduated: 0, failed: 0, win_rate: 0 };

  if (loading && !pipelineData) {
    return (
      <div className="monitor-page">
        <div className="loading-container">
          <div className="loading-spinner" />
          <span>Loading monitor data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="monitor-page">
      {/* Page Header */}
      <div className="monitor-header">
        <div className="header-left">
          <h2>📊 Screener Monitor</h2>
          <span className="subtitle">Track picks through 25-day pipeline</span>
        </div>
        
        {/* Screener Selector */}
        <div className="screener-selector">
          <label>Select Screener:</label>
          <select 
            value={selectedScreener}
            onChange={(e) => setSelectedScreener(e.target.value)}
            className="wsj-select"
          >
            {screeners.map(s => (
              <option key={s.id} value={s.name}>
                {s.display_name} ({s.pick_count} picks)
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat-item">
          <span className="stat-icon">📈</span>
          <div className="stat-content">
            <span className="stat-value">{stats.active}</span>
            <span className="stat-label">Active Picks</span>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-icon">🎓</span>
          <div className="stat-content">
            <span className="stat-value">{stats.graduated}</span>
            <span className="stat-label">Graduated</span>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-icon">⚠️</span>
          <div className="stat-content">
            <span className="stat-value">{stats.failed}</span>
            <span className="stat-label">Failed</span>
          </div>
        </div>
        <div className="stat-item win-rate">
          <span className="stat-icon">🏆</span>
          <div className="stat-content">
            <span className={`stat-value ${stats.win_rate >= 50 ? 'positive' : 'negative'}`}>
              {stats.win_rate}%
            </span>
            <span className="stat-label">Win Rate</span>
          </div>
        </div>
        <div className="stat-item total">
          <span className="stat-icon">📋</span>
          <div className="stat-content">
            <span className="stat-value">{stats.total}</span>
            <span className="stat-label">Total</span>
          </div>
        </div>
      </div>

      {/* Pipeline Board */}
      <div className="pipeline-board">
        {STAGES.map(stage => (
          <PipelineColumn
            key={stage.key}
            stage={stage.key}
            title={stage.title}
            subtitle={stage.subtitle}
            picks={groupedPicks[stage.key]}
            onPickClick={setSelectedPick}
          />
        ))}
      </div>

      {/* Pick Detail Modal */}
      {selectedPick && (
        <PickDetailModal 
          pick={selectedPick} 
          onClose={() => setSelectedPick(null)}
        />
      )}
    </div>
  );
};

// Pick Detail Modal Component
const PickDetailModal: React.FC<{ pick: Pick; onClose: () => void }> = ({ pick, onClose }) => {
  const currentDay = pick.daily_checks?.length || 0;
  const latestCheck = pick.daily_checks?.[pick.daily_checks.length - 1];
  const currentPrice = latestCheck?.close_price || pick.entry_price;
  const performance = ((currentPrice - pick.entry_price) / pick.entry_price * 100);
  const failureLine = pick.cup_rim_price && pick.cup_bottom_price
    ? (pick.cup_rim_price + pick.cup_bottom_price) / 2
    : null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide pick-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>📈 {pick.stock_code} - Pick Details</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {/* Quick Stats */}
          <div className="detail-stats">
            <div className="detail-stat">
              <span className="label">Status</span>
              <span className={`value status-${pick.status}`}>
                {pick.status === 'active' ? '✓ Active' : 
                 pick.status === 'graduated' ? '🎓 Graduated' : '✗ Failed'}
              </span>
            </div>
            <div className="detail-stat">
              <span className="label">Current Day</span>
              <span className="value">{currentDay} / 25</span>
            </div>
            <div className="detail-stat">
              <span className="label">Entry Price</span>
              <span className="value">¥{pick.entry_price.toFixed(2)}</span>
            </div>
            <div className="detail-stat">
              <span className="label">Current Price</span>
              <span className="value">¥{currentPrice.toFixed(2)}</span>
            </div>
            <div className="detail-stat">
              <span className="label">Performance</span>
              <span className={`value ${performance >= 0 ? 'positive' : 'negative'}`}>
                {performance >= 0 ? '+' : ''}{performance.toFixed(2)}%
              </span>
            </div>
          </div>

          {/* Coffee Cup Pattern Info */}
          {pick.screener_id === 'coffee_cup_screener' && (
            <div className="pattern-info">
              <h4>☕ Cup Pattern Levels</h4>
              <div className="pattern-levels">
                {pick.cup_rim_price && (
                  <div className="level">
                    <span className="level-label">Cup Rim</span>
                    <span className="level-value">¥{pick.cup_rim_price.toFixed(2)}</span>
                    <span className="level-desc">Resistance level</span>
                  </div>
                )}
                {pick.cup_bottom_price && (
                  <div className="level">
                    <span className="level-label">Cup Bottom</span>
                    <span className="level-value">¥{pick.cup_bottom_price.toFixed(2)}</span>
                    <span className="level-desc">Support level</span>
                  </div>
                )}
                {failureLine && (
                  <div className="level failure">
                    <span className="level-label">Failure Line</span>
                    <span className="level-value">¥{failureLine.toFixed(2)}</span>
                    <span className="level-desc">Exit if price closes below</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Daily History */}
          <div className="daily-history">
            <h4>📅 Daily History</h4>
            {pick.daily_checks?.length > 0 ? (
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Date</th>
                    <th>Close Price</th>
                    <th>Change</th>
                    <th>Status</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {pick.daily_checks.map((check, idx) => {
                    const prevPrice = idx > 0 ? pick.daily_checks[idx - 1].close_price : pick.entry_price;
                    const change = check.close_price && prevPrice 
                      ? ((check.close_price - prevPrice) / prevPrice * 100)
                      : 0;
                    return (
                      <tr key={idx}>
                        <td>{check.day}</td>
                        <td>{check.date}</td>
                        <td>¥{check.close_price?.toFixed(2) || '-'}</td>
                        <td className={change >= 0 ? 'positive' : 'negative'}>
                          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                        </td>
                        <td>
                          <span className={`badge-${check.status}`}>
                            {check.status === 'pass' ? '✓' : 
                             check.status === 'fail' ? '✗' : '○'}
                          </span>
                        </td>
                        <td>{check.note || '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="no-data">No daily checks recorded yet.</p>
            )}
          </div>

          {/* Entry Info */}
          <div className="entry-info">
            <h4>📝 Entry Information</h4>
            <div className="info-grid">
              <div className="info-item">
                <span className="label">Entry Date</span>
                <span className="value">{pick.entry_date}</span>
              </div>
              <div className="info-item">
                <span className="label">Expected Exit</span>
                <span className="value">{pick.expected_exit_date}</span>
              </div>
              {pick.exit_date && (
                <div className="info-item">
                  <span className="label">Exit Date</span>
                  <span className="value">{pick.exit_date}</span>
                </div>
              )}
              {pick.exit_reason && (
                <div className="info-item">
                  <span className="label">Exit Reason</span>
                  <span className="value">{pick.exit_reason}</span>
                </div>
              )}
              {pick.max_price_seen && (
                <div className="info-item">
                  <span className="label">Max Price Seen</span>
                  <span className="value">¥{pick.max_price_seen.toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Monitor;
