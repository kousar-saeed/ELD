import React from 'react';

// Status row mapping
const ROW_MAP = {
  OFF: 0,
  SB: 1,
  D: 2,
  ON: 3,
};

const ROW_LABELS = [
  '1. OFF DUTY',
  '2. SLEEPER BERTH',
  '3. DRIVING',
  '4. ON DUTY (NOT DRIVING)',
];

export default function DayLogSVG({ logData, driverName = 'John Doe', carrier = 'ELD Planner Inc.' }) {
  if (!logData) return null;

  const { date, segments = [], totals = {} } = logData;

  // Grid Layout Constants
  const width = 840;
  const height = 220;
  const margin = { top: 30, right: 90, bottom: 25, left: 160 };

  const gridWidth = width - margin.left - margin.right; // 590px
  const gridHeight = height - margin.top - margin.bottom; // 165px
  const rowHeight = gridHeight / 4; // ~41.25px

  // Convert time "HH:MM" or "24:00" to X coordinate
  const timeToX = (timeStr) => {
    if (timeStr === '24:00') return margin.left + gridWidth;
    const [h, m] = timeStr.split(':').map(Number);
    const totalMinutes = h * 60 + m;
    return margin.left + (totalMinutes / 1440) * gridWidth;
  };

  // Convert status to Y center coordinate of its row
  const statusToY = (status) => {
    const rowIdx = ROW_MAP[status] ?? 0;
    return margin.top + rowIdx * rowHeight + rowHeight / 2;
  };

  // Generate SVG path for duty status line
  let polylinePoints = [];
  let prevY = null;

  segments.forEach((seg) => {
    const x1 = timeToX(seg.start);
    const x2 = timeToX(seg.end);
    const y = statusToY(seg.status);

    if (prevY !== null && prevY !== y) {
      // Add vertical transition line at status change
      polylinePoints.push(`${x1},${prevY}`);
    }
    polylinePoints.push(`${x1},${y}`);
    polylinePoints.push(`${x2},${y}`);
    prevY = y;
  });

  const pathD = polylinePoints.length > 0 ? `M ${polylinePoints.join(' L ')}` : '';

  return (
    <div className="day-log-sheet">
      {/* Log Sheet Header */}
      <div className="log-sheet-header">
        <div className="header-meta">
          <div className="meta-field">
            <span className="meta-label">DATE:</span>
            <span className="meta-value">{date}</span>
          </div>
          <div className="meta-field">
            <span className="meta-label">DRIVER:</span>
            <span className="meta-value">{driverName}</span>
          </div>
          <div className="meta-field">
            <span className="meta-label">CARRIER:</span>
            <span className="meta-value">{carrier}</span>
          </div>
        </div>
        <div className="fmcsa-badge">FMCSA 24-HR LOG GRID</div>
      </div>

      {/* SVG Grid Container */}
      <div className="svg-wrapper">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="fmcsa-svg-grid"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Background */}
          <rect x="0" y="0" width={width} height={height} fill="#0f172a" rx="8" />

          {/* Grid Rows Background & Label */}
          {ROW_LABELS.map((label, idx) => {
            const y = margin.top + idx * rowHeight;
            return (
              <g key={idx}>
                {/* Row Fill */}
                <rect
                  x={margin.left}
                  y={y}
                  width={gridWidth}
                  height={rowHeight}
                  fill={idx % 2 === 0 ? '#1e293b' : '#172033'}
                  stroke="#334155"
                  strokeWidth="0.75"
                />
                {/* Left Row Label */}
                <text
                  x={margin.left - 12}
                  y={y + rowHeight / 2 + 4}
                  fill="#94a3b8"
                  fontSize="11"
                  fontWeight="600"
                  textAnchor="end"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* Right Totals Header & Column */}
          <rect
            x={margin.left + gridWidth}
            y={margin.top}
            width={margin.right - 10}
            height={gridHeight}
            fill="#1e293b"
            stroke="#334155"
            strokeWidth="1"
          />
          <text
            x={margin.left + gridWidth + (margin.right - 10) / 2}
            y={margin.top - 10}
            fill="#38bdf8"
            fontSize="10"
            fontWeight="700"
            textAnchor="middle"
          >
            TOTAL HOURS
          </text>

          {['OFF', 'SB', 'D', 'ON'].map((statusKey, idx) => {
            const y = margin.top + idx * rowHeight + rowHeight / 2 + 4;
            const val = totals[statusKey] ?? 0;
            return (
              <text
                key={statusKey}
                x={margin.left + gridWidth + (margin.right - 10) / 2}
                y={y}
                fill={val > 0 ? '#f8fafc' : '#64748b'}
                fontSize="12"
                fontWeight="700"
                textAnchor="middle"
              >
                {val.toFixed(1)}h
              </text>
            );
          })}

          {/* Vertical Hour Grid Lines & Top Scale (0..24) */}
          {Array.from({ length: 25 }).map((_, hour) => {
            const x = margin.left + (hour / 24) * gridWidth;
            const isNoonOrMid = hour === 0 || hour === 12 || hour === 24;

            return (
              <g key={hour}>
                {/* Vertical Full Hour Line */}
                <line
                  x1={x}
                  y1={margin.top}
                  x2={x}
                  y2={margin.top + gridHeight}
                  stroke={isNoonOrMid ? '#64748b' : '#334155'}
                  strokeWidth={isNoonOrMid ? '1.5' : '0.75'}
                />

                {/* Top Hour Text */}
                <text
                  x={x}
                  y={margin.top - 10}
                  fill={isNoonOrMid ? '#38bdf8' : '#94a3b8'}
                  fontSize="10"
                  fontWeight={isNoonOrMid ? '700' : '500'}
                  textAnchor="middle"
                >
                  {hour === 0 ? 'M' : hour === 12 ? 'N' : hour === 24 ? 'M' : hour}
                </text>

                {/* Half Hour Ticks */}
                {hour < 24 && (
                  <line
                    x1={margin.left + ((hour + 0.5) / 24) * gridWidth}
                    y1={margin.top}
                    x2={margin.left + ((hour + 0.5) / 24) * gridWidth}
                    y2={margin.top + gridHeight}
                    stroke="#1e293b"
                    strokeDasharray="2,2"
                    strokeWidth="0.5"
                  />
                )}
              </g>
            );
          })}

          {/* Active Duty Status Red Line */}
          {pathD && (
            <path
              d={pathD}
              fill="none"
              stroke="#ef4444"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Points / Status Nodes */}
          {segments.map((seg, i) => {
            const x = timeToX(seg.start);
            const y = statusToY(seg.status);
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r="3.5"
                fill="#ffffff"
                stroke="#ef4444"
                strokeWidth="2"
              />
            );
          })}
        </svg>
      </div>

      {/* Remarks Section */}
      <div className="remarks-section">
        <h5 className="remarks-title">REMARKS / LOCATION LOG</h5>
        <div className="remarks-list">
          {segments
            .filter((s) => s.label)
            .map((seg, idx) => (
              <div key={idx} className="remark-item">
                <span className="remark-time">
                  [{seg.start} - {seg.end}]
                </span>
                <span className={`remark-status ${seg.status}`}>{seg.status}</span>
                <span className="remark-text">{seg.label}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
