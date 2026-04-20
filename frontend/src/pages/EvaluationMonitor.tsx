import { useState, useEffect } from 'react';
import { getEvals } from '../services/api';

const C = { card: '#161A22', border: '#1E2330', teal: '#00C9A7', blue: '#4F8EF7', amber: '#F5A623', green: '#4ADE80', purple: '#A78BFA', red: '#F26D6D', text: '#E8EAF0', textMid: '#8891A8', textDim: '#454E66' };

const LAYER_CONFIG: Record<string, { metrics: string[]; color: string }> = {
  'Layer 1: Retrieval': { metrics: ['recall_at_k', 'precision_at_k', 'mrr', 'ndcg'], color: C.blue },
  'Layer 2: Context': { metrics: ['context_recall', 'context_precision', 'context_relevance'], color: C.purple },
  'Layer 3: Generation': { metrics: ['faithfulness', 'answer_relevancy', 'answer_correctness', 'semantic_similarity'], color: C.teal },
};

const THRESHOLDS: Record<string, number> = {
  recall_at_k: 0.7, precision_at_k: 0.5, mrr: 0.4, ndcg: 0.5,
  context_recall: 0.6, context_precision: 0.5, context_relevance: 0.5,
  faithfulness: 0.7, answer_relevancy: 0.7, answer_correctness: 0.7, semantic_similarity: 0.6,
};

const DIAG_COLORS: Record<string, string> = { ideal: C.green, mixed: C.amber, wrong_context: C.red, hallucination: '#FF4444', lucky_guess: C.purple };

function Bar({ value, color, threshold }: { value: number; color: string; threshold: number }) {
  const pct = Math.round(value * 100);
  const pass = value >= threshold;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: `${color}22` }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono min-w-[34px]" style={{ color: pass ? color : C.red }}>{pct}%</span>
    </div>
  );
}

export default function EvaluationMonitor() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getEvals().then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-full text-[#8891A8]">Loading evals...</div>;
  if (!data?.latest) return <div className="flex items-center justify-center h-full text-[#8891A8]">No eval data found. Run: python evals/run_evals.py</div>;

  const { latest, results } = data;
  const avg = latest.average_metrics || {};
  const diagnoses = latest.diagnoses || {};
  const byCategory = latest.by_category || {};

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="mb-5">
        <p className="text-[10px] tracking-[3px] uppercase mb-1" style={{ color: C.textDim }}>3-Layer RAG Evaluation</p>
        <h2 className="text-xl font-bold">Eval Metrics</h2>
      </div>

      {/* Overall Score */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <div className="p-4 rounded-xl border" style={{ borderColor: C.teal, background: `${C.teal}12` }}>
          <p className="text-[11px] mb-2" style={{ color: C.textMid }}>Overall Score</p>
          <p className="text-3xl font-bold font-mono" style={{ color: C.teal }}>{Math.round((latest.average_overall || 0) * 100)}%</p>
        </div>
        <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
          <p className="text-[11px] mb-2" style={{ color: C.textMid }}>Total Evals</p>
          <p className="text-3xl font-bold font-mono" style={{ color: C.blue }}>{latest.total_evaluations || 0}</p>
        </div>
        <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
          <p className="text-[11px] mb-2" style={{ color: C.textMid }}>Ideal Diagnoses</p>
          <p className="text-3xl font-bold font-mono" style={{ color: C.green }}>{diagnoses.ideal || 0}</p>
        </div>
        <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
          <p className="text-[11px] mb-2" style={{ color: C.textMid }}>Hallucinations</p>
          <p className="text-3xl font-bold font-mono" style={{ color: diagnoses.hallucination ? C.red : C.green }}>{diagnoses.hallucination || 0}</p>
        </div>
      </div>

      {/* 3-Layer Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        {Object.entries(LAYER_CONFIG).map(([layer, cfg]) => (
          <div key={layer} className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
            <p className="text-xs font-semibold mb-3" style={{ color: cfg.color }}>{layer}</p>
            <div className="flex flex-col gap-3">
              {cfg.metrics.map(m => (
                <div key={m}>
                  <div className="flex justify-between mb-1">
                    <span className="text-[10px]" style={{ color: C.textMid }}>{m.replace(/_/g, ' ')}</span>
                    <span className="text-[10px]" style={{ color: C.textDim }}>thresh: {Math.round(THRESHOLDS[m] * 100)}%</span>
                  </div>
                  <Bar value={avg[m] || 0} color={cfg.color} threshold={THRESHOLDS[m]} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Diagnosis Distribution + Category Breakdown */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
          <p className="text-xs mb-3" style={{ color: C.textMid }}>Diagnosis Distribution</p>
          <div className="flex flex-col gap-2">
            {Object.entries(diagnoses).map(([d, count]) => (
              <div key={d} className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-sm" style={{ background: DIAG_COLORS[d] || C.textDim }} />
                <span className="text-[11px] flex-1" style={{ color: C.textMid }}>{d}</span>
                <span className="text-[11px] font-mono" style={{ color: DIAG_COLORS[d] || C.textDim }}>{count as number}</span>
                <div className="w-20 h-1.5 rounded-full" style={{ background: `${C.border}` }}>
                  <div className="h-full rounded-full" style={{ width: `${((count as number) / (latest.total_evaluations || 1)) * 100}%`, background: DIAG_COLORS[d] || C.textDim }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
          <p className="text-xs mb-3" style={{ color: C.textMid }}>Performance by Category</p>
          <div className="flex flex-col gap-2">
            {Object.entries(byCategory).map(([cat, info]: [string, any]) => (
              <div key={cat} className="flex items-center gap-3">
                <span className="text-[11px] flex-1 truncate" style={{ color: C.textMid }}>{cat}</span>
                <span className="text-[11px] font-mono" style={{ color: C.teal }}>{Math.round(info.avg_score * 100)}%</span>
                <span className="text-[10px]" style={{ color: C.textDim }}>{info.total} queries</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Per-Query Table */}
      <div className="rounded-xl border border-[#1E2330] overflow-hidden">
        <div className="px-4 py-2.5 bg-[#161A22] border-b border-[#1E2330]">
          <p className="text-xs" style={{ color: C.textMid }}>Per-query eval breakdown</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr style={{ background: '#111318' }}>
                {['Query', 'Faith', 'Relevancy', 'Correct', 'Recall@k', 'Ctx Recall', 'Diagnosis', 'Latency'].map(h => (
                  <th key={h} className="px-3 py-2 text-left font-medium uppercase tracking-wider" style={{ color: C.textDim, fontSize: 10 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(results || []).map((r: any, i: number) => {
                const e = r.evaluation || {};
                const g = e.layer3_generation || {};
                const ret = e.layer1_retrieval || {};
                const ctx = e.layer2_context || {};
                return (
                  <tr key={i} className="border-t border-[#1E2330]">
                    <td className="px-3 py-2.5 max-w-[200px] truncate" style={{ color: C.textMid }}>{r.query}</td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: (g.faithfulness || 0) >= 0.7 ? C.green : C.red }}>{Math.round((g.faithfulness || 0) * 100)}%</td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: (g.answer_relevancy || 0) >= 0.7 ? C.teal : C.amber }}>{Math.round((g.answer_relevancy || 0) * 100)}%</td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: (g.answer_correctness || 0) >= 0.7 ? C.green : C.red }}>{Math.round((g.answer_correctness || 0) * 100)}%</td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: (ret.recall_at_k || 0) >= 0.7 ? C.blue : C.amber }}>{Math.round((ret.recall_at_k || 0) * 100)}%</td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: (ctx.context_recall || 0) >= 0.6 ? C.purple : C.amber }}>{Math.round((ctx.context_recall || 0) * 100)}%</td>
                    <td className="px-3 py-2.5"><span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ border: `1px solid ${DIAG_COLORS[e.diagnosis] || C.textDim}50`, background: `${DIAG_COLORS[e.diagnosis] || C.textDim}18`, color: DIAG_COLORS[e.diagnosis] || C.textDim }}>{e.diagnosis}</span></td>
                    <td className="px-3 py-2.5 font-mono" style={{ color: C.green }}>{(e.latency || 0).toFixed(1)}s</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
