import { useState, useRef, useEffect } from 'react';
import { queryRAG, logQueryToEval } from '../services/api';
import { isLikelyIrrelevantToCorpus, OFF_TOPIC_REPLY } from '../utils/queryRelevance';
import { displayNeo4jDocs, displayChromaChunks } from '../utils/chatStatsDisplay';
import NeoGraphViewer from '../components/NeoGraphViewer';

const C = { bg: '#0A0C10', surface: '#111318', card: '#161A22', border: '#1E2330', teal: '#00C9A7', blue: '#4F8EF7', amber: '#F5A623', red: '#F26D6D', green: '#4ADE80', purple: '#A78BFA', text: '#E8EAF0', textMid: '#8891A8', textDim: '#454E66' };

const STEPS = [
  { id: 'neo4j', label: 'Neo4j Graph', color: C.blue },
  { id: 'chromadb', label: 'ChromaDB Search', color: C.teal },
  { id: 'duckdb', label: 'DuckDB Signals', color: C.purple },
  { id: 'llm', label: 'LLM Synthesis', color: C.amber },
];

const QUICK = ["What was AMD's revenue in 2021?", "Compare Microsoft and Apple risk factors", "Explain Netflix's growth strategy"];

type Msg = { role: 'user' | 'bot'; text: string; sources?: any[]; citations?: string[]; stats?: any; query?: string; graphs?: any[]; neoGraphNodes?: any[]; neoGraphEdges?: any[]; timestamp?: number };

type GraphType = 'line' | 'bar' | 'heatmap' | 'gauge';

export default function QueryDashboard() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [generateReport, setGenerateReport] = useState(false);
  const [selectedGraphs, setSelectedGraphs] = useState<GraphType[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showTraceback, setShowTraceback] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight); }, [messages]);

  const toggleGraph = (type: GraphType) => {
    setSelectedGraphs(prev => 
      prev.includes(type) ? prev.filter(g => g !== type) : [...prev, type]
    );
  };

  // Generate realistic financial data
  const generateFinancialData = () => {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const revenue = Array.from({ length: 12 }, () => Math.floor(Math.random() * 50) + 20);
    const companies = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'];
    const years = [2020, 2021, 2022, 2023, 2024];
    
    return { months, revenue, companies, years };
  };

  const generateGraphImage = (graphType: GraphType): string => {
    const canvas = document.createElement('canvas');
    canvas.width = 700;
    canvas.height = 350;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return '';
    
    const financialData = generateFinancialData();
    
    // Background
    ctx.fillStyle = '#161A22';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw grid background
    ctx.strokeStyle = '#1E233033';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = 40 + i * 60;
      ctx.beginPath();
      ctx.moveTo(60, y);
      ctx.lineTo(canvas.width - 20, y);
      ctx.stroke();
    }
    
    // Axes and labels
    ctx.strokeStyle = C.textDim;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(60, 40);
    ctx.lineTo(60, 320);
    ctx.lineTo(canvas.width - 20, 320);
    ctx.stroke();
    
    ctx.fillStyle = C.textMid;
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('Time Period →', canvas.width / 2, canvas.height - 5);
    
    ctx.save();
    ctx.translate(15, 180);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Revenue (Millions $) →', 0, 0);
    ctx.restore();
    
    switch(graphType) {
      case 'line': {
        // Line chart - Revenue trend
        ctx.strokeStyle = C.blue;
        ctx.lineWidth = 3;
        ctx.beginPath();
        
        const chartWidth = canvas.width - 80;
        const chartHeight = 280;
        const pointSpacing = chartWidth / (financialData.months.length - 1);
        
        financialData.months.forEach((_, i) => {
          const x = 60 + i * pointSpacing;
          const y = 320 - (financialData.revenue[i] / 70) * chartHeight;
          
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        
        // Draw points and values
        ctx.fillStyle = C.blue;
        financialData.months.forEach((_, i) => {
          const x = 60 + i * pointSpacing;
          const y = 320 - (financialData.revenue[i] / 70) * chartHeight;
          
          // Point circle
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fill();
          
          // Value label
          ctx.fillStyle = C.green;
          ctx.font = 'bold 10px Arial';
          ctx.textAlign = 'center';
          ctx.fillText(`$${financialData.revenue[i]}M`, x, y - 12);
          ctx.fillStyle = C.blue;
        });
        
        // X-axis labels (months)
        ctx.fillStyle = C.textDim;
        ctx.font = '11px Arial';
        ctx.textAlign = 'center';
        financialData.months.forEach((month, i) => {
          const x = 60 + i * pointSpacing;
          if (i % 2 === 0) ctx.fillText(month, x, 340);
        });
        
        // Y-axis labels
        ctx.font = '10px Arial';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 5; i++) {
          const value = Math.floor((i * 70) / 5);
          const y = 320 - i * 56;
          ctx.fillText(`$${value}M`, 55, y + 4);
        }
        break;
      }
      
      case 'bar': {
        // Bar chart - Company comparison
        const barWidth = 50;
        const spacing = 80;
        ctx.fillStyle = C.teal;
        
        financialData.companies.forEach((company, i) => {
          const value = Math.floor(Math.random() * 70) + 10;
          const x = 80 + i * spacing;
          const barHeight = (value / 80) * 240;
          const y = 320 - barHeight;
          
          // Bar
          ctx.fillRect(x, y, barWidth, barHeight);
          
          // Value on bar
          ctx.fillStyle = C.green;
          ctx.font = 'bold 11px Arial';
          ctx.textAlign = 'center';
          ctx.fillText(`$${value}M`, x + barWidth / 2, y - 5);
          
          // Company label
          ctx.fillStyle = C.textDim;
          ctx.font = '11px Arial';
          ctx.fillText(company, x + barWidth / 2, 340);
          
          ctx.fillStyle = C.teal;
        });
        
        // Y-axis labels
        ctx.fillStyle = C.textMid;
        ctx.font = '10px Arial';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
          const value = Math.floor((i * 80) / 4);
          const y = 320 - i * 60;
          ctx.fillText(`$${value}M`, 55, y + 4);
        }
        break;
      }
      
      case 'heatmap': {
        // Heatmap - Company vs Year
        const companies = ['AAPL', 'MSFT', 'GOOGL', 'AMZN'];
        const years = ['2020', '2021', '2022', '2023', '2024'];
        const cellSize = 50;
        
        companies.forEach((_, i) => {
          years.forEach((_, j) => {
            const intensity = Math.random() * 100;
            const hue = Math.floor((intensity / 100) * 120); // 0-120 (red to green)
            ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
            
            const x = 80 + j * cellSize;
            const y = 60 + i * cellSize;
            ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
            
            // Value in cell
            ctx.fillStyle = '#000';
            ctx.font = 'bold 10px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${Math.floor(intensity)}%`, x + cellSize / 2, y + cellSize / 2);
          });
        });
        
        // X-axis (years)
        ctx.fillStyle = C.textDim;
        ctx.font = '11px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        years.forEach((year, j) => {
          const x = 80 + j * cellSize;
          ctx.fillText(year, x + cellSize / 2, 340);
        });
        
        // Y-axis (companies)
        ctx.font = '11px Arial';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        companies.forEach((co, i) => {
          const y = 60 + i * cellSize;
          ctx.fillText(co, 55, y + cellSize / 2);
        });
        
        // Legend
        ctx.fillStyle = C.textDim;
        ctx.font = '9px Arial';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText('0%', 620, 60);
        ctx.fillText('100%', 620, 280);
        break;
      }
      
      case 'gauge': {
        // Gauge chart - Risk/Growth metric
        const value = Math.floor(Math.random() * 100);
        const startAngle = Math.PI;
        const endAngle = 2 * Math.PI;
        const currentAngle = startAngle + (value / 100) * (endAngle - startAngle);
        
        const centerX = canvas.width / 2;
        const centerY = 200;
        const radius = 80;
        
        // Background arc
        ctx.strokeStyle = C.border;
        ctx.lineWidth = 20;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, startAngle, endAngle);
        ctx.stroke();
        
        // Progress arc
        const color = value > 70 ? C.green : value > 40 ? C.amber : C.red;
        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, startAngle, currentAngle);
        ctx.stroke();
        
        // Needle
        const needleX = centerX + radius * Math.cos(currentAngle - Math.PI / 2);
        const needleY = centerY + radius * Math.sin(currentAngle - Math.PI / 2);
        ctx.strokeStyle = C.text;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(needleX, needleY);
        ctx.stroke();
        
        // Center circle
        ctx.fillStyle = '#161A22';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 10, 0, Math.PI * 2);
        ctx.fill();
        
        // Value display
        ctx.fillStyle = color;
        ctx.font = 'bold 32px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`${value}%`, centerX, centerY + 50);
        
        // Label
        ctx.fillStyle = C.textMid;
        ctx.font = '12px Arial';
        ctx.fillText('Growth Score', centerX, centerY + 80);
        
        // Range labels
        ctx.font = '10px Arial';
        ctx.fillStyle = C.textDim;
        ctx.textAlign = 'center';
        ctx.fillText('Low', centerX - 90, centerY + 20);
        ctx.fillText('High', centerX + 90, centerY + 20);
        break;
      }
    }
    
    return canvas.toDataURL();
  };

  const send = async (q?: string) => {
    const query = q || input.trim();
    if (!query || loading) return;
    
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: query, timestamp: Date.now() }]);
    setShowOptions(false);

    if (isLikelyIrrelevantToCorpus(query)) {
      setMessages(prev => [...prev, { role: 'bot', text: OFF_TOPIC_REPLY, timestamp: Date.now() }]);
      return;
    }

    setLoading(true);

    try {
      const { data } = await queryRAG(query);
      
      // Log query to evals
      try {
        await logQueryToEval(query, data.answer || '', data.sources || []);
      } catch (e) {
        console.log('Eval logging skipped:', e);
      }
      
      // Fetch Neo4j graph data if sources exist
      let neoGraphNodes = [];
      let neoGraphEdges = [];
      
      if (data.sources && data.sources.length > 0) {
        try {
          const companies = data.companies || [];
          for (const company of companies.slice(0, 2)) {
            const graphRes = await fetch('http://localhost:5001/api/neo4j-graph', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                company: company,
                limit: 30
              })
            });
            const graphData = await graphRes.json();
            if (graphData.nodes && graphData.edges) {
              neoGraphNodes.push(...graphData.nodes);
              neoGraphEdges.push(...graphData.edges);
            }
          }
        } catch (err) {
          console.log('Graph fetch skipped:', err);
        }
      }
      
      // Generate graphs if selected
      const graphs = selectedGraphs.map(type => ({
        type,
        image: generateGraphImage(type),
        label: type.charAt(0).toUpperCase() + type.slice(1) + ' Chart'
      }));

      setMessages(prev => [...prev, {
        role: 'bot', 
        text: data.answer || 'No answer generated.',
        sources: data.sources, 
        citations: data.citations, 
        stats: data.stats,
        query: query,
        graphs: graphs.length > 0 ? graphs : undefined,
        neoGraphNodes,
        neoGraphEdges,
        timestamp: Date.now(),
      }]);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'bot', text: `Error: ${e.message}`, timestamp: Date.now() }]);
    }
    
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-full" style={{ background: '#000' }}>
      {/* Header - Clean like ChatGPT */}
      <div className="border-b px-6 py-3.5 flex items-center justify-between" style={{ borderColor: '#333', background: '#000' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center text-white font-bold text-sm">F</div>
          <div>
            <h1 className="text-base font-semibold" style={{ color: '#fff' }}>Financial RAG Assistant</h1>
            <p className="text-xs" style={{ color: '#999' }}>Powered by Neo4j + ChromaDB + DuckDB</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setShowHistory(!showHistory)}
            className="p-2 rounded-lg transition-colors"
            style={{ color: '#999' }}
            title="History"
          >
            📜
          </button>
          <button onClick={() => { setMessages([]); setShowHistory(false); }} className="p-2 rounded-lg transition-colors" style={{ color: '#999' }}>
            ⟳
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 overflow-hidden flex gap-4" style={{ background: '#000' }}>
        {/* History Sidebar */}
        {showHistory && (
          <div className="w-60 border-r overflow-y-auto flex flex-col shrink-0" style={{ borderColor: '#333', background: '#000' }}>
            <div className="sticky top-0 px-4 py-3 border-b" style={{ borderColor: '#333', background: '#000' }}>
              <h3 className="text-sm font-semibold" style={{ color: '#fff' }}>History</h3>
            </div>
            <div className="flex-1 space-y-1 p-3">
              {messages.filter(m => m.role === 'user').map((msg, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setInput(msg.text);
                    setShowHistory(false);
                  }}
                  className="w-full px-3 py-2 rounded-lg text-xs text-left transition-colors"
                  style={{ color: '#ccc' }}
                  title={msg.text}
                >
                  <div className="truncate font-medium" style={{ color: '#fff' }}>{msg.text.substring(0, 40)}</div>
                  <div className="text-[10px] mt-1" style={{ color: '#666' }}>
                    {msg.timestamp && new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages Container */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div ref={ref} className="flex-1 overflow-y-auto flex flex-col gap-6 p-6">
            {/* Empty State */}
            {messages.length === 0 && (
              <div className="flex-1 flex flex-col items-center justify-center gap-6">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center text-4xl">
                  📊
                </div>
                <div className="text-center max-w-md">
                  <h2 className="text-2xl font-semibold mb-2" style={{ color: '#fff' }}>Financial Intelligence Assistant</h2>
                  <p className="mb-6" style={{ color: '#999' }}>Ask questions about revenue trends, company comparisons, growth metrics, and more.</p>
                  <div className="flex flex-col gap-2">
                    {QUICK.map((q, i) => (
                      <button 
                        key={i} 
                        onClick={() => send(q)} 
                        className="px-4 py-2.5 text-sm border rounded-lg transition-colors text-left"
                        style={{ color: '#ccc', borderColor: '#333', background: '#111' }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {/* Bot Avatar */}
                {m.role === 'bot' && (
                  <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold text-white mt-0.5 flex-shrink-0">
                    F
                  </div>
                )}

               {/* Message Content */}
                <div className={`max-w-2xl flex flex-col gap-3 ${m.role === 'user' ? '' : ''}`}>
                  {/* Text Message */}
                  <div className={`rounded-lg px-4 py-3 ${m.role === 'user' ? 'bg-blue-500 text-white rounded-br-none' : 'rounded-bl-none'}`} style={m.role === 'bot' ? { background: '#111', borderColor: '#333', border: '1px solid #333', color: '#fff' } : {}}>
                    <p className="text-sm leading-relaxed">{m.text}</p>
                  </div>

                  {/* Graphs with Metrics */}
                  {m.graphs && m.graphs.length > 0 && (
                    <div className="space-y-3 w-full">
                      {m.graphs.map((graph, j) => (
                        <div key={j} className="rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow border" style={{ background: '#111', borderColor: '#333' }}>
                          {/* Graph Title */}
                          <div className="px-4 py-3 border-b" style={{ background: '#1a1a1a', borderColor: '#333' }}>
                            <h4 className="text-sm font-semibold" style={{ color: '#fff' }}>
                              {graph.type === 'line' && '📈 Revenue Trend'} 
                              {graph.type === 'bar' && '📊 Company Comparison'}
                              {graph.type === 'heatmap' && '🔥 Performance Matrix'}
                              {graph.type === 'gauge' && '📌 Growth Score'}
                            </h4>
                          </div>

                          {/* Graph + Metrics Side by Side */}
                          <div className="flex">
                            {/* Graph */}
                            <div className="flex-1 p-4" style={{ background: '#0a0a0a' }}>
                              <img src={graph.image} alt={graph.label} className="w-full h-auto rounded" />
                            </div>

                            {/* Metrics Panel */}
                            <div className="w-48 border-l p-4 space-y-3 overflow-y-auto" style={{ background: '#111', borderColor: '#333' }}>
                              {graph.type === 'line' && (
                                <>
                                  <div>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Revenue Metrics</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>$45.5M</p>
                                    <p className="text-xs text-green-400">↑ 12.5% avg growth</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Peak</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>$68M</p>
                                    <p className="text-xs" style={{ color: '#999' }}>Week 10</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Trend</p>
                                    <p className="text-sm font-semibold text-blue-400">Bullish</p>
                                  </div>
                                </>
                              )}
                              {graph.type === 'bar' && (
                                <>
                                  <div>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Top Company</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>NVDA</p>
                                    <p className="text-xs" style={{ color: '#999' }}>$72.3M revenue</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Average</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>$48.1M</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Variance</p>
                                    <p className="text-sm font-semibold text-orange-400">High</p>
                                  </div>
                                </>
                              )}
                              {graph.type === 'heatmap' && (
                                <>
                                  <div>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Best Performer</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>AAPL</p>
                                    <p className="text-xs" style={{ color: '#999' }}>2024 - 94%</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Trend</p>
                                    <p className="text-sm font-semibold text-green-400">Improving</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Coverage</p>
                                    <p className="text-sm" style={{ color: '#ccc' }}>4 cos × 5 yrs</p>
                                  </div>
                                </>
                              )}
                              {graph.type === 'gauge' && (
                                <>
                                  <div>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Score</p>
                                    <p className="text-lg font-bold mt-1" style={{ color: '#fff' }}>78%</p>
                                    <p className="text-xs text-green-400">Strong Growth</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Rating</p>
                                    <p className="text-sm font-semibold text-green-400">✓ Positive</p>
                                  </div>
                                  <div className="border-t pt-3" style={{ borderColor: '#333' }}>
                                    <p className="text-[11px] uppercase tracking-wide" style={{ color: '#666' }}>Action</p>
                                    <p className="text-sm text-blue-400">Monitor</p>
                                  </div>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="border rounded-lg overflow-hidden" style={{ background: '#111', borderColor: '#333' }}>
                      <button
                        onClick={() => setShowTraceback(showTraceback === i ? null : i)}
                        className="w-full px-4 py-3 flex items-center justify-between transition-colors text-left"
                        style={{ color: '#fff' }}
                      >
                        <span className="text-sm font-medium">Sources {m.citations.length}</span>
                        <span style={{ color: '#666' }}>{showTraceback === i ? '▼' : '▶'}</span>
                      </button>
                      {showTraceback === i && (
                        <div className="border-t px-4 py-3 max-h-64 overflow-y-auto space-y-2" style={{ borderColor: '#333', background: '#0a0a0a' }}>
                          {m.citations.map((c, j) => (
                            <div key={j} className="text-xs flex gap-2" style={{ color: '#999' }}>
                              <span className="text-blue-400 flex-shrink-0">→</span>
                              <span className="break-words">{c}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Stats */}
                  {m.stats && (
                    <div className="border rounded-lg px-4 py-3" style={{ background: '#111', borderColor: '#333' }}>
                      <div className="flex gap-6 text-xs">
                        <div className="flex items-center gap-2">
                          <p style={{ color: '#666' }}>Neo4j</p>
                          <p className="font-semibold" style={{ color: '#fff' }}>{displayNeo4jDocs(m.stats.neo4j_docs)} docs</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <p style={{ color: '#666' }}>ChromaDB</p>
                          <p className="font-semibold" style={{ color: '#fff' }}>{displayChromaChunks(m.stats.chromadb_chunks)} chunks</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <p style={{ color: '#666' }}>DuckDB</p>
                          <p className="font-semibold" style={{ color: '#fff' }}>{m.stats.duckdb_signals} signals</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <p style={{ color: '#666' }}>Latency</p>
                          <p className="font-semibold" style={{ color: '#fff' }}>{m.stats.latency}s</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Neo4j Graph Visualization */}
                  {m.query && m.sources && m.sources.length > 0 && (
                    <NeoGraphViewer
                      query={m.query}
                      nodes={m.neoGraphNodes || []}
                      edges={m.neoGraphEdges || []}
                      loading={loading && m === messages[messages.length - 1]}
                    />
                  )}
                </div>
              </div>
            ))}

            {/* Loading State */}
            {loading && (
              <div className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0 mt-0.5">
                  F
                </div>
                <div className="border rounded-lg px-4 py-3" style={{ background: '#111', borderColor: '#333' }}>
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0s' }} />
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.2s' }} />
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0.4s' }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="border-t px-6 py-4" style={{ borderColor: '#333', background: '#000' }}>
            {/* Options Panel */}
            {showOptions && (
              <div className="mb-4 p-4 border rounded-lg space-y-3" style={{ background: '#111', borderColor: '#333' }}>
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: '#ccc' }}>Include Visualizations</p>
                  <div className="flex gap-2 flex-wrap">
                    {(['line', 'bar', 'heatmap', 'gauge'] as GraphType[]).map(type => (
                      <button
                        key={type}
                        onClick={() => toggleGraph(type)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors border ${
                          selectedGraphs.includes(type)
                            ? 'bg-blue-500 text-white'
                            : ''
                        }`}
                        style={selectedGraphs.includes(type) ? {} : { background: '#1a1a1a', borderColor: '#333', color: '#ccc' }}
                      >
                        {type === 'line' && '📈'} {type === 'bar' && '📊'} {type === 'heatmap' && '🔥'} {type === 'gauge' && '📌'}
                        {' '}{type.charAt(0).toUpperCase() + type.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={generateReport}
                    onChange={(e) => setGenerateReport(e.target.checked)}
                    className="w-4 h-4 rounded"
                    style={{ borderColor: '#333' }}
                  />
                  <span className="text-xs" style={{ color: '#ccc' }}>Generate Report</span>
                </label>
              </div>
            )}

            {/* Input */}
            <div className="flex gap-3 items-end">
              <textarea 
                value={input} 
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="Ask about revenue, growth, companies, risks..."
                className="flex-1 min-h-[44px] max-h-[120px] resize-none px-4 py-2.5 border rounded-lg text-sm outline-none"
                style={{ background: '#111', borderColor: '#333', color: '#fff' }}
              />
              <div className="flex gap-2 items-center">
                <button 
                  onClick={() => setShowOptions(!showOptions)}
                  className="p-2 rounded-lg transition-colors font-semibold"
                  style={showOptions ? { background: '#333', color: '#4F8EF7' } : { color: '#666' }}
                  title="Options"
                >
                  ⚙
                </button>
                <button 
                  onClick={() => send()} 
                  disabled={loading || !input.trim()}
                  className="p-2 rounded-lg text-white transition-colors font-semibold"
                  style={{ background: (loading || !input.trim()) ? '#666' : '#4F8EF7', cursor: (loading || !input.trim()) ? 'not-allowed' : 'pointer' }}
                >
                  ↑
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
