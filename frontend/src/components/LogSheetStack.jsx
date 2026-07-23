import React, { useState } from 'react';
import DayLogSVG from './DayLogSVG';
import { Calendar, FileText, Download } from 'lucide-react';

export default function LogSheetStack({ dailyLogs, warnings = [] }) {
  const [activeDayIdx, setActiveDayIdx] = useState(0);

  if (!dailyLogs || dailyLogs.length === 0) {
    return null;
  }

  const activeLog = dailyLogs[activeDayIdx] || dailyLogs[0];

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="log-sheet-stack-card">
      <div className="stack-header">
        <div className="stack-title-area">
          <div className="title-icon">
            <FileText className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h3>FMCSA Daily Log Sheets</h3>
            <p className="card-subtitle">
              Generated 24-hour log grids for {dailyLogs.length} calendar day(s) touched by trip
            </p>
          </div>
        </div>

        <button onClick={handlePrint} className="print-btn" title="Print/Export Logs">
          <Download className="w-4 h-4" />
          Print / Export
        </button>
      </div>

      {/* Warnings Banner if any */}
      {warnings && warnings.length > 0 && (
        <div className="warnings-banner">
          <div className="warning-heading">HOS Engine Automated Notices:</div>
          <ul>
            {warnings.map((w, idx) => (
              <li key={idx}>• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Days Tabs Bar */}
      <div className="days-tabs-bar">
        {dailyLogs.map((log, idx) => (
          <button
            key={log.date}
            className={`day-tab-btn ${idx === activeDayIdx ? 'active' : ''}`}
            onClick={() => setActiveDayIdx(idx)}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>Day {idx + 1}</span>
            <span className="tab-date">{log.date}</span>
          </button>
        ))}
      </div>

      {/* Active Day Overview Stats */}
      <div className="day-summary-bar">
        <div className="summary-pill">
          <span className="pill-label">Driving (D):</span>
          <span className="pill-val text-emerald-400">{activeLog.totals?.D ?? 0}h</span>
        </div>
        <div className="summary-pill">
          <span className="pill-label">On Duty (ON):</span>
          <span className="pill-val text-indigo-400">{activeLog.totals?.ON ?? 0}h</span>
        </div>
        <div className="summary-pill">
          <span className="pill-label">Off Duty (OFF):</span>
          <span className="pill-val text-slate-300">{activeLog.totals?.OFF ?? 0}h</span>
        </div>
        <div className="summary-pill">
          <span className="pill-label">Sleeper (SB):</span>
          <span className="pill-val text-purple-400">{activeLog.totals?.SB ?? 0}h</span>
        </div>
      </div>

      {/* Day Log SVG Component */}
      <DayLogSVG logData={activeLog} />
    </div>
  );
}
