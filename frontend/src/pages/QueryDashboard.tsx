import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import NeoGraphViewer from '../components/NeoGraphViewer';
import { logQueryToEval, queryRAG } from '../services/api';
import { useTheme } from '../theme';
import { displayChromaChunks, displayNeo4jDocs } from '../utils/chatStatsDisplay';
import { OFF_TOPIC_REPLY, isLikelyIrrelevantToCorpus } from '../utils/queryRelevance';

const darkTheme = {
  bg: '#07111F',
  surface: 'rgba(10, 22, 38, 0.92)',
  card: 'rgba(13, 27, 46, 0.94)',
  cardSoft: 'rgba(9, 20, 35, 0.78)',
  border: 'rgba(148, 163, 184, 0.18)',
  blue: '#4DA2FF',
  teal: '#34C79A',
  amber: '#F4B860',
  red: '#F27A7A',
  text: '#EFF4FB',
  textMid: '#94A9C7',
  textDim: '#6E84A3',
};

const lightTheme = {
  bg: '#F3F7FC',
  surface: 'rgba(255, 255, 255, 0.92)',
  card: 'rgba(255, 255, 255, 0.98)',
  cardSoft: 'rgba(240, 245, 252, 0.94)',
  border: 'rgba(130, 146, 166, 0.22)',
  blue: '#2F7FE7',
  teal: '#1FA37A',
  amber: '#C68A2D',
  red: '#D45C5C',
  text: '#102033',
  textMid: '#506580',
  textDim: '#7A8BA1',
};

const QUICK = [
  "What was AMD's revenue in 2021?",
  'Compare Microsoft and Apple risk factors',
  "Explain Netflix's growth strategy",
];

type PipelineStatus = 'done' | 'active' | 'pending' | 'skipped';

type PipelineStep = {
  label: string;
  status: PipelineStatus;
  detail?: string;
};

type Msg = {
  role: 'user' | 'bot';
  text: string;
  sources?: any[];
  citations?: string[];
  stats?: any;
  query?: string;
  neoGraphNodes?: any[];
  neoGraphEdges?: any[];
  timestamp?: number;
  pipeline?: PipelineStep[];
  error?: boolean;
  agents_called?: string[];
  analysis?: any;
  visualizations?: any[];
  planner_reasoning?: string;
};

function buildPipeline({
  hasSources,
  hasGraph,
  hasSignals,
  citationsCount,
  currentStage,
}: {
  hasSources: boolean;
  hasGraph: boolean;
  hasSignals: boolean;
  citationsCount: number;
  currentStage?: 'retrieval' | 'graph' | 'signals' | 'synthesis';
}): PipelineStep[] {
  const activeIf = (stage: 'retrieval' | 'graph' | 'signals' | 'synthesis') =>
    currentStage === stage ? 'active' : 'pending';

  if (currentStage) {
    return [
      {
        label: 'Retrieve context',
        status: currentStage === 'retrieval' ? 'active' : 'done',
      },
      {
        label: 'Graph lookup',
        status:
          currentStage === 'graph'
            ? 'active'
            : currentStage === 'signals' || currentStage === 'synthesis'
              ? 'done'
              : activeIf('graph'),
      },
      {
        label: 'Extract signals',
        status:
          currentStage === 'signals'
            ? 'active'
            : currentStage === 'synthesis'
              ? 'done'
              : activeIf('signals'),
      },
      {
        label: 'Synthesize answer',
        status: currentStage === 'synthesis' ? 'active' : activeIf('synthesis'),
      },
    ];
  }

  return [
    {
      label: 'Retrieve context',
      status: hasSources ? 'done' : 'skipped',
      detail: hasSources ? `${citationsCount} source references` : 'No supporting retrieval returned',
    },
    {
      label: 'Graph lookup',
      status: hasGraph ? 'done' : 'skipped',
      detail: hasGraph ? 'Graph context loaded' : 'No graph context used',
    },
    {
      label: 'Extract signals',
      status: hasSignals ? 'done' : 'skipped',
      detail: hasSignals ? 'Structured signal data available' : 'No structured signals detected',
    },
    {
      label: 'Synthesize answer',
      status: 'done',
      detail: 'Response generated from retrieved evidence',
    },
  ];
}

function statusColors(
  status: PipelineStatus,
  theme: typeof darkTheme,
) {
  if (status === 'done') {
    return {
      background: 'rgba(52, 199, 154, 0.14)',
      border: 'rgba(52, 199, 154, 0.28)',
      color: theme.teal,
    };
  }
  if (status === 'active') {
    return {
      background: 'rgba(77, 162, 255, 0.16)',
      border: 'rgba(77, 162, 255, 0.32)',
      color: theme.blue,
    };
  }
  if (status === 'skipped') {
    return {
      background: 'rgba(148, 163, 184, 0.08)',
      border: 'rgba(148, 163, 184, 0.2)',
      color: theme.textDim,
    };
  }
  return {
    background: 'rgba(148, 163, 184, 0.06)',
    border: 'rgba(148, 163, 184, 0.18)',
    color: theme.textMid,
  };
}

function buildAnalysis(msg: Msg, theme: typeof darkTheme) {
  const stats = msg.stats || {};
  const chunks = displayChromaChunks(stats.chromadb_chunks || 0);
  const graphDocs = displayNeo4jDocs(stats.neo4j_documents || 0);
  const signals = stats.duckdb_signals || 0;
  const citations = msg.citations?.length || 0;
  const graphNodes = msg.neoGraphNodes?.length || 0;

  return [
    {
      label: 'Evidence',
      value: citations > 0 ? `${citations} cited source${citations > 1 ? 's' : ''}` : 'No citations',
      tone: citations > 0 ? theme.blue : theme.textDim,
    },
    {
      label: 'Vector retrieval',
      value: `${chunks} chunks`,
      tone: theme.teal,
    },
    {
      label: 'Graph context',
      value: graphNodes > 0 ? `${graphNodes} nodes loaded` : `${graphDocs} graph docs`,
      tone: graphNodes > 0 ? theme.blue : theme.textMid,
    },
    {
      label: 'DuckDB signals',
      value: signals > 0 ? `${signals} signals` : 'No signal hits',
      tone: signals > 0 ? theme.amber : theme.textDim,
    },
  ];
}

export default function QueryDashboard() {
  const { isDark } = useTheme();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysisIncluded, setAnalysisIncluded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showGraphPanel, setShowGraphPanel] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const theme = isDark ? darkTheme : lightTheme;

  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [messages, loading]);

  const graphMessage = useMemo(
    () =>
      [...messages]
        .reverse()
        .find((message) => message.role === 'bot' && (message.neoGraphNodes?.length || 0) > 0),
    [messages],
  );

  const send = async (prefill?: string) => {
    const query = (prefill || input).trim();
    if (!query || loading) {
      return;
    }

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: query, timestamp: Date.now() }]);

    if (isLikelyIrrelevantToCorpus(query)) {
      const offTopic = {
        role: 'bot' as const,
        text: OFF_TOPIC_REPLY,
        query,
        timestamp: Date.now(),
        pipeline: buildPipeline({
          hasSources: false,
          hasGraph: false,
          hasSignals: false,
          citationsCount: 0,
        }),
      };
      setMessages((prev) => [...prev, offTopic]);
      return;
    }

    setLoading(true);

    try {
      const { data } = await queryRAG(query, analysisIncluded);
      const stats = data.stats || {};

      // Eval metrics are now logged inline by /api/query — no separate call needed

      let neoGraphNodes: any[] = [];
      let neoGraphEdges: any[] = [];

      if (data.sources && data.sources.length > 0) {
        try {
          const companies = data.companies || [];
          for (const company of companies.slice(0, 2)) {
            const graphRes = await fetch('/api/neo4j-graph', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ company, limit: 30 }),
            });
            const graphData = await graphRes.json();
            if (graphData.nodes && graphData.edges) {
              neoGraphNodes = [...neoGraphNodes, ...graphData.nodes];
              neoGraphEdges = [...neoGraphEdges, ...graphData.edges];
            }
          }
        } catch (error) {
          console.log('Graph fetch skipped:', error);
        }
      }

      const agentsCalled: string[] = data.agents_called || [];

      const botMessage: Msg = {
        role: 'bot',
        text: data.answer || 'No answer generated.',
        sources: data.sources,
        citations: data.citations,
        stats,
        query,
        neoGraphNodes,
        neoGraphEdges,
        timestamp: Date.now(),
        agents_called: agentsCalled,
        analysis: data.analysis,
        visualizations: data.visualizations,
        planner_reasoning: data.planner_reasoning,
        pipeline: agentsCalled.map((agent: string) => ({
          label: agent.charAt(0).toUpperCase() + agent.slice(1),
          status: 'done' as PipelineStatus,
          detail: agent === 'planner' ? (data.planner_reasoning || 'Routed query')
            : agent === 'retriever' ? `${stats.chromadb_chunks || 0} chunks retrieved`
            : agent === 'analyst' ? (data.analysis ? 'Analysis complete' : 'No data to analyze')
            : agent === 'visualizer' ? `${(data.visualizations || []).length} chart(s) generated`
            : agent,
        })),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error: any) {
      const errorMessage: Msg = {
        role: 'bot',
        text: `Error: ${error.message}`,
        query,
        timestamp: Date.now(),
        error: true,
        pipeline: [
          { label: 'Retrieve context', status: 'done' },
          { label: 'Synthesize answer', status: 'skipped', detail: 'Request failed before completion' },
        ],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden"
      style={{
        background: isDark
          ? 'radial-gradient(circle at top right, rgba(77, 162, 255, 0.12), transparent 24%), #07111F'
          : 'radial-gradient(circle at top right, rgba(47, 127, 231, 0.1), transparent 24%), #F3F7FC',
      }}
    >
      <div
        className="flex items-center justify-between border-b px-8 py-5"
        style={{ borderColor: theme.border, background: theme.surface, backdropFilter: 'blur(16px)' }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-teal-400 text-sm font-bold text-white shadow-lg">
            F
          </div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: theme.text }}>
              Financial RAG Assistant
            </h1>
            
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory((prev) => !prev)}
            className="rounded-xl border px-3 py-2 text-sm transition-all"
            style={{
              color: showHistory ? '#fff' : theme.textMid,
              background: showHistory ? theme.blue : theme.card,
              borderColor: theme.border,
            }}
          >
            History
          </button>
          <button
            onClick={() => {
              setMessages([]);
              setShowHistory(false);
              setShowGraphPanel(false);
            }}
            className="rounded-xl border px-3 py-2 text-sm transition-all hover:opacity-80"
            style={{ color: theme.textMid, background: theme.card, borderColor: theme.border }}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {showHistory ? (
          <aside
            className="w-72 shrink-0 overflow-y-auto border-r"
            style={{ borderColor: theme.border, background: theme.surface }}
          >
            <div className="sticky top-0 border-b px-4 py-4" style={{ borderColor: theme.border, background: theme.card }}>
              <h2 className="text-sm font-semibold" style={{ color: theme.text }}>
                Recent prompts
              </h2>
            </div>
            <div className="space-y-2 p-3">
              {messages.filter((message) => message.role === 'user').length === 0 ? (
                <div className="rounded-2xl border p-4 text-sm" style={{ borderColor: theme.border, color: theme.textDim }}>
                  No prompts yet.
                </div>
              ) : (
                messages
                  .filter((message) => message.role === 'user')
                  .map((message, index) => (
                    <div
                      key={`${message.timestamp}-${index}`}
                      className="rounded-2xl border px-4 py-3"
                      style={{ borderColor: theme.border, background: theme.cardSoft }}
                    >
                      <p className="line-clamp-2 text-sm font-medium" style={{ color: theme.text }}>
                        {message.text}
                      </p>
                      <p className="mt-2 text-xs" style={{ color: theme.textDim }}>
                        {message.timestamp ? new Date(message.timestamp).toLocaleTimeString() : ''}
                      </p>
                    </div>
                  ))
              )}
            </div>
          </aside>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div ref={ref} id="chat" className="flex-1 overflow-y-auto px-8 py-8 pb-8">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-8">
                <div className="flex h-20 w-20 items-center justify-center rounded-[28px] bg-gradient-to-br from-blue-500 to-teal-400 text-5xl shadow-xl">
                  📊
                </div>
                <div className="max-w-xl text-center">
                  <h2 className="mb-3 text-3xl font-bold" style={{ color: theme.text }}>
                    Ask one focused question at a time
                  </h2>
                  <p className="mb-6 text-sm leading-7" style={{ color: theme.textDim }}>
                    The assistant will answer, show the evidence footprint, and expose the pipeline
                    used for that specific prompt.
                  </p>
                  <div className="flex flex-col gap-3">
                    {QUICK.map((question) => (
                      <button
                        key={question}
                        onClick={() => send(question)}
                        className="rounded-2xl border px-5 py-4 text-left text-sm transition-all hover:-translate-y-0.5"
                        style={{
                          color: theme.textMid,
                          borderColor: theme.border,
                          background: theme.card,
                        }}
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mx-auto flex min-h-full max-w-4xl flex-col justify-end gap-6">
                {messages.map((msg, index) => (
                  <div key={`${msg.timestamp}-${index}`} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                    {msg.role === 'user' ? (
                      <div
                        className="max-w-2xl rounded-[22px] rounded-br-md px-5 py-4 text-sm leading-7 text-white shadow-lg"
                        style={{ background: theme.blue }}
                      >
                        {msg.text}
                      </div>
                    ) : (
                      <div className="w-full max-w-3xl rounded-[26px] border shadow-lg" style={{ borderColor: theme.border, background: theme.card }}>
                        <div className="border-b px-5 py-4" style={{ borderColor: theme.border }}>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-teal-400 text-xs font-bold text-white">
                                F
                              </div>
                              <div>
                                <div className="text-sm font-semibold" style={{ color: theme.text }}>
                                  Assistant response
                                </div>
                                <div className="text-xs" style={{ color: theme.textDim }}>
                                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                                </div>
                              </div>
                            </div>

                            <button
                              onClick={() => setShowGraphPanel((prev) => !prev)}
                              disabled={!msg.neoGraphNodes || msg.neoGraphNodes.length === 0}
                              className="rounded-xl border px-3 py-2 text-xs font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{
                                borderColor: theme.border,
                                background: showGraphPanel ? theme.blue : theme.cardSoft,
                                color: showGraphPanel ? '#fff' : theme.textMid,
                              }}
                            >
                              {showGraphPanel ? 'Hide graph' : 'Open graph'}
                            </button>
                          </div>
                        </div>

                        <div className="px-5 py-5">
                          <div className="prose prose-invert max-w-none text-sm leading-7" style={{ color: theme.text }}>
                            <ReactMarkdown>{msg.text}</ReactMarkdown>
                          </div>

                          {msg.error ? null : (
                            <div className="mt-5 space-y-4">
                              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                {buildAnalysis(msg, theme).map((item) => (
                                  <div
                                    key={item.label}
                                    className="rounded-2xl border px-4 py-4"
                                    style={{ borderColor: theme.border, background: theme.cardSoft }}
                                  >
                                    <div className="text-xs" style={{ color: theme.textDim }}>
                                      {item.label}
                                    </div>
                                    <div className="mt-2 text-sm font-semibold" style={{ color: item.tone }}>
                                      {item.value}
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {msg.pipeline && msg.pipeline.length > 0 ? (
                                <div
                                  className="rounded-2xl border px-4 py-4"
                                  style={{ borderColor: theme.border, background: theme.cardSoft }}
                                >
                                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: theme.textDim }}>
                                    Agents Called
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {msg.pipeline.map((step) => {
                                      const colors = statusColors(step.status, theme);
                                      return (
                                        <div
                                          key={step.label}
                                          className="rounded-full border px-3 py-1.5 text-xs font-semibold"
                                          style={{
                                            background: colors.background,
                                            borderColor: colors.border,
                                            color: colors.color,
                                          }}
                                          title={step.detail}
                                        >
                                          {step.label}
                                          {step.detail ? <span style={{ opacity: 0.7 }}> — {step.detail}</span> : null}
                                        </div>
                                      );
                                    })}
                                  </div>
                                  {msg.stats ? (
                                    <div className="mt-3 flex flex-wrap gap-3 text-xs" style={{ color: theme.textMid }}>
                                      <span>Neo4j: {msg.stats.neo4j_documents ?? 0} docs</span>
                                      <span>ChromaDB: {msg.stats.chromadb_chunks ?? 0} chunks</span>
                                      <span>DuckDB: {msg.stats.duckdb_signals ?? 0} signals</span>
                                      <span>Latency: {msg.stats.latency_seconds ?? '—'}s</span>
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}

                              {msg.analysis ? (
                                <div
                                  className="rounded-2xl border px-4 py-4"
                                  style={{ borderColor: theme.border, background: theme.cardSoft }}
                                >
                                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: theme.textDim }}>
                                    Analysis Results
                                  </div>
                                  {msg.analysis.metrics ? (
                                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                                      {Object.entries(msg.analysis.metrics as Record<string, any>).map(([metric, data]: [string, any]) => (
                                        <div key={metric} className="rounded-xl border px-3 py-3" style={{ borderColor: theme.border }}>
                                          <div className="text-xs capitalize" style={{ color: theme.textDim }}>{metric.replace(/_/g, ' ')}</div>
                                          {data.values ? (
                                            <div className="mt-1 space-y-1">
                                              {Object.entries(data.values as Record<string, number>).map(([co, val]: [string, any]) => (
                                                <div key={co} className="flex justify-between text-sm" style={{ color: co === data.leader ? theme.teal : theme.textMid }}>
                                                  <span>{co}</span>
                                                  <span className="font-semibold">{typeof val === 'number' ? val.toLocaleString() : val}</span>
                                                </div>
                                              ))}
                                            </div>
                                          ) : null}
                                        </div>
                                      ))}
                                    </div>
                                  ) : msg.analysis.cagr != null ? (
                                    <div className="flex flex-wrap gap-4 text-sm" style={{ color: theme.textMid }}>
                                      <span>CAGR: <strong style={{ color: theme.teal }}>{msg.analysis.cagr}%</strong></span>
                                      <span>Total growth: <strong style={{ color: theme.teal }}>{msg.analysis.total_growth}%</strong></span>
                                      <span>Trend: <strong style={{ color: msg.analysis.trend === 'upward' ? theme.teal : theme.red }}>{msg.analysis.trend}</strong></span>
                                    </div>
                                  ) : (
                                    <pre className="text-xs overflow-auto" style={{ color: theme.textMid }}>{JSON.stringify(msg.analysis, null, 2)}</pre>
                                  )}
                                </div>
                              ) : null}

                              {msg.visualizations && msg.visualizations.length > 0 ? (
                                <div
                                  className="rounded-2xl border px-4 py-4"
                                  style={{ borderColor: theme.border, background: theme.cardSoft }}
                                >
                                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: theme.textDim }}>
                                    Visualizations ({msg.visualizations.length} chart{msg.visualizations.length > 1 ? 's' : ''})
                                  </div>
                                  <div className="space-y-4">
                                    {msg.visualizations.map((viz: any, vi: number) => (
                                      <div key={vi}>
                                        <div className="mb-2 flex items-center gap-2 text-sm font-semibold" style={{ color: theme.text }}>
                                          <span>{viz.type === 'line' ? '📈' : '📊'}</span>
                                          <span>{viz.title}</span>
                                        </div>
                                        <iframe
                                          src={`http://localhost:5001/visualizations/${viz.path.split('/').pop()}`}
                                          className="w-full rounded-xl border"
                                          style={{ height: '420px', borderColor: theme.border, background: '#fff' }}
                                          title={viz.title}
                                        />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}

                              {msg.citations && msg.citations.length > 0 ? (
                                <div
                                  className="rounded-2xl border px-4 py-4"
                                  style={{ borderColor: theme.border, background: theme.cardSoft }}
                                >
                                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: theme.textDim }}>
                                    Sources
                                  </div>
                                  <div className="space-y-2">
                                    {msg.citations.map((citation, citationIndex) => (
                                      <div
                                        key={`${citation}-${citationIndex}`}
                                        className="rounded-xl border px-3 py-3 text-sm"
                                        style={{ borderColor: theme.border, color: theme.textMid }}
                                      >
                                        {citation}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {loading ? (
                  <div className="flex justify-start">
                    <div
                      className="max-w-xl rounded-[22px] rounded-bl-md border px-5 py-4 text-sm"
                      style={{ borderColor: theme.border, background: theme.card, color: theme.text }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex gap-1">
                          <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500" />
                          <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500" style={{ animationDelay: '0.2s' }} />
                          <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500" style={{ animationDelay: '0.4s' }} />
                        </div>
                        <span>Working through the current prompt...</span>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>

        {showGraphPanel && graphMessage ? (
          <aside
            className="w-[42rem] max-w-[48vw] shrink-0 border-l"
            style={{ borderColor: theme.border, background: theme.surface }}
          >
            <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: theme.border }}>
              <div>
                <div className="text-sm font-semibold" style={{ color: theme.text }}>
                  Graph context
                </div>
                <div className="text-xs" style={{ color: theme.textDim }}>
                  {graphMessage.query}
                </div>
              </div>
              <button
                onClick={() => setShowGraphPanel(false)}
                className="rounded-lg px-2 py-1 text-sm"
                style={{ color: theme.textMid }}
              >
                Close
              </button>
            </div>
            <div className="h-[calc(100%-65px)]">
              <NeoGraphViewer
                query={graphMessage.query || ''}
                nodes={graphMessage.neoGraphNodes || []}
                edges={graphMessage.neoGraphEdges || []}
                loading={loading}
              />
            </div>
          </aside>
        ) : null}
      </div>

      <div
        className="border-t px-8 py-6"
        style={{ borderColor: theme.border, background: theme.surface, backdropFilter: 'blur(16px)' }}
      >
        <div className="mx-auto flex max-w-4xl items-end gap-3">
          <div className="flex-1 flex flex-col gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
              placeholder="Ask about a company, filing, trend, or risk factor..."
              className="w-full min-h-[56px] max-h-[160px] resize-none rounded-2xl border px-4 py-4 text-sm outline-none transition-all"
              style={{ background: theme.card, borderColor: theme.border, color: theme.text }}
            />
            <label className="flex items-center gap-2 text-xs cursor-pointer select-none" style={{ color: theme.textDim }}>
              <input
                type="checkbox"
                checked={analysisIncluded}
                onChange={(e) => setAnalysisIncluded(e.target.checked)}
                className="rounded"
              />
              Include analysis &amp; visualization
            </label>
          </div>
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="rounded-2xl px-5 py-4 text-sm font-semibold text-white shadow-lg transition-all"
            style={{
              background: loading || !input.trim() ? theme.textDim : theme.blue,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
