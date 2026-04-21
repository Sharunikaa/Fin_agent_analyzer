import { useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ScatterChart, Scatter } from 'recharts';
import NeoGraphViewer from './NeoGraphViewer';

const C = {
  bg: '#0A0C10',
  surface: '#111318',
  card: '#161A22',
  border: '#1E2330',
  teal: '#00C9A7',
  blue: '#4F8EF7',
  amber: '#F5A623',
  red: '#F26D6D',
  green: '#4ADE80',
  purple: '#A78BFA',
  text: '#E8EAF0',
  textMid: '#8891A8',
  textDim: '#454E66',
};

interface GraphAnalyticsProps {
  query: string;
  nodes: any[];
  edges: any[];
  loading?: boolean;
}

// Generate sample analytics data
const generateAnalyticsData = () => {
  // Line chart data - Performance over time
  const lineData = Array.from({ length: 12 }, (_, i) => ({
    month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i],
    revenue: Math.random() * 100 + 50,
    growth: Math.random() * 30 + 10,
    forecast: Math.random() * 120 + 40,
  }));

  // Bar chart data - Company comparison
  const barData = [
    { name: 'Apple', value: 92, change: 5.2 },
    { name: 'Microsoft', value: 88, change: 3.8 },
    { name: 'Amazon', value: 85, change: 6.1 },
    { name: 'Google', value: 90, change: 4.5 },
    { name: 'Tesla', value: 78, change: -2.3 },
  ];

  // Heatmap data - Performance matrix
  const heatmapData = Array.from({ length: 5 }, (_, i) => {
    const row: any = { name: ['2020', '2021', '2022', '2023', '2024'][i] };
    ['Q1', 'Q2', 'Q3', 'Q4'].forEach((q, j) => {
      row[q] = Math.floor(Math.random() * 100);
    });
    return row;
  });

  // Gauge data
  const gaugeData = {
    score: 78,
    rating: 'Strong',
    color: C.green,
  };

  return { lineData, barData, heatmapData, gaugeData };
};

const HeatmapCell = ({ x, y, value, color }: any) => {
  const intensity = value / 100;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={40}
        height={40}
        fill={color}
        opacity={0.3 + intensity * 0.7}
        stroke={C.border}
        strokeWidth={1}
      />
      <text
        x={x + 20}
        y={y + 25}
        textAnchor="middle"
        fill={C.text}
        fontSize={12}
        fontWeight="bold"
      >
        {value}
      </text>
    </g>
  );
};

const GaugeChart = ({ score, rating, color }: any) => {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center">
      <div style={{ position: 'relative', width: 150, height: 150 }}>
        <svg width={150} height={150} viewBox="0 0 150 150">
          {/* Background circle */}
          <circle
            cx={75}
            cy={75}
            r={45}
            fill="none"
            stroke={C.border}
            strokeWidth={8}
          />
          {/* Progress circle */}
          <circle
            cx={75}
            cy={75}
            r={45}
            fill="none"
            stroke={color}
            strokeWidth={8}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transform: 'rotate(-90deg)', transformOrigin: '75px 75px', transition: 'all 0.5s' }}
          />
          {/* Center text */}
          <text
            x={75}
            y={75}
            textAnchor="middle"
            dy="0.3em"
            fill={C.text}
            fontSize={32}
            fontWeight="bold"
          >
            {score}%
          </text>
        </svg>
      </div>
      <p className="text-sm font-semibold mt-2" style={{ color }}>
        {rating}
      </p>
    </div>
  );
};

export default function GraphAnalytics({ query, nodes, edges, loading = false }: GraphAnalyticsProps) {
  const [activeTab, setActiveTab] = useState<'graph' | 'analytics'>('graph');
  const { lineData, barData, heatmapData, gaugeData } = generateAnalyticsData();

  const quarters = ['Q1', 'Q2', 'Q3', 'Q4'];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: C.bg }}>
      {/* Tab Headers */}
      <div
        className="flex gap-0 border-b"
        style={{ borderColor: C.border, background: C.surface }}
      >
        <button
          onClick={() => setActiveTab('graph')}
          className="flex-1 px-4 py-3 text-sm font-semibold transition-all border-b-2"
          style={{
            background: activeTab === 'graph' ? C.card : 'transparent',
            color: activeTab === 'graph' ? C.blue : C.textMid,
            borderColor: activeTab === 'graph' ? C.blue : 'transparent',
          }}
        >
          📊 Neo4j Graph
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          className="flex-1 px-4 py-3 text-sm font-semibold transition-all border-b-2"
          style={{
            background: activeTab === 'analytics' ? C.card : 'transparent',
            color: activeTab === 'analytics' ? C.blue : C.textMid,
            borderColor: activeTab === 'analytics' ? C.blue : 'transparent',
          }}
        >
          📈 Analytics
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Neo4j Graph Tab */}
        {activeTab === 'graph' && (
          <NeoGraphViewer query={query} nodes={nodes} edges={edges} loading={loading} />
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="p-4 space-y-6">
            {/* Line Chart */}
            <div className="rounded-lg p-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: C.text }}>
                📈 Performance Trend
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={lineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke={C.textDim} />
                  <YAxis tick={{ fontSize: 10 }} stroke={C.textDim} />
                  <Tooltip
                    contentStyle={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: '6px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke={C.blue}
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="growth"
                    stroke={C.green}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Bar Chart */}
            <div className="rounded-lg p-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: C.text }}>
                📊 Company Performance Score
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke={C.textDim} />
                  <YAxis tick={{ fontSize: 10 }} stroke={C.textDim} />
                  <Tooltip
                    contentStyle={{
                      background: C.surface,
                      border: `1px solid ${C.border}`,
                      borderRadius: '6px',
                    }}
                  />
                  <Bar dataKey="value" fill={C.blue}>
                    {barData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.change > 0 ? C.green : C.red}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Heatmap */}
            <div className="rounded-lg p-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: C.text }}>
                🔥 Performance Matrix (Quarters)
              </h3>
              <div className="overflow-x-auto">
                <svg width="100%" height={300} viewBox="0 0 500 200">
                  {/* Headers */}
                  {quarters.map((q, i) => (
                    <text
                      key={`header-${i}`}
                      x={100 + i * 90}
                      y={20}
                      textAnchor="middle"
                      fill={C.textMid}
                      fontSize={12}
                      fontWeight="bold"
                    >
                      {q}
                    </text>
                  ))}
                  {/* Year labels and heatmap cells */}
                  {heatmapData.map((row, rowIdx) => (
                    <g key={`row-${rowIdx}`}>
                      <text
                        x={20}
                        y={60 + rowIdx * 50}
                        textAnchor="end"
                        fill={C.textMid}
                        fontSize={12}
                        fontWeight="bold"
                      >
                        {row.name}
                      </text>
                      {quarters.map((q, colIdx) => (
                        <HeatmapCell
                          key={`cell-${rowIdx}-${colIdx}`}
                          x={80 + colIdx * 90}
                          y={50 + rowIdx * 50}
                          value={row[q]}
                          color={C.blue}
                        />
                      ))}
                    </g>
                  ))}
                </svg>
              </div>
            </div>

            {/* Gauge Chart */}
            <div className="rounded-lg p-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: C.text }}>
                📈 Overall Score
              </h3>
              <div className="flex justify-center">
                <GaugeChart
                  score={gaugeData.score}
                  rating={gaugeData.rating}
                  color={gaugeData.color}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
