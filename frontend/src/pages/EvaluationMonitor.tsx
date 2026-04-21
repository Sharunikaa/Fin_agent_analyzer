import { useEffect, useState } from 'react';
import { Badge, MetricTile, PageHeader, PageShell, SectionHeading, SurfaceCard } from '../components/ui';
import { getEvals, getTunerState } from '../services/api';

const LAYER_CONFIG: Record<string, { metrics: string[]; color: string }> = {
  'Layer 1: Retrieval': {
    metrics: ['recall_at_k', 'precision_at_k', 'mrr', 'ndcg'],
    color: 'var(--accent)',
  },
  'Layer 2: Context': {
    metrics: ['context_recall', 'context_precision', 'context_relevance'],
    color: '#8ca7ff',
  },
  'Layer 3: Generation': {
    metrics: ['faithfulness', 'answer_relevancy', 'answer_correctness', 'semantic_similarity'],
    color: 'var(--success)',
  },
};

const THRESHOLDS: Record<string, number> = {
  recall_at_k: 0.7,
  precision_at_k: 0.5,
  mrr: 0.4,
  ndcg: 0.5,
  context_recall: 0.6,
  context_precision: 0.5,
  context_relevance: 0.5,
  faithfulness: 0.7,
  answer_relevancy: 0.7,
  answer_correctness: 0.7,
  semantic_similarity: 0.6,
};

const DIAGNOSIS_TONE: Record<string, 'success' | 'warning' | 'danger' | 'accent'> = {
  ideal: 'success',
  mixed: 'warning',
  wrong_context: 'danger',
  hallucination: 'danger',
  lucky_guess: 'accent',
};

function MetricBar({
  label,
  value,
  color,
  threshold,
}: {
  label: string;
  value: number;
  color: string;
  threshold: number;
}) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="text-[var(--text-muted)]">{label}</span>
        <span className="text-[var(--text-soft)]">Target {Math.round(threshold * 100)}%</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(148,163,184,0.14)]">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span
          className="min-w-[44px] text-right font-mono text-sm font-semibold"
          style={{ color: value >= threshold ? color : 'var(--warning)' }}
        >
          {pct}%
        </span>
      </div>
    </div>
  );
}

export default function EvaluationMonitor() {
  const [data, setData] = useState<any>(null);
  const [tuner, setTuner] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getEvals().then((r) => setData(r.data)).catch(() => {}),
      getTunerState().then((r) => setTuner(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PageShell>
        <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
          Loading evaluation metrics...
        </div>
      </PageShell>
    );
  }

  if (!data?.latest) {
    return (
      <PageShell>
        <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
          No evaluation data found. Run `python evals/run_evals.py` to populate this dashboard.
        </div>
      </PageShell>
    );
  }

  const { latest, results } = data;
  const avg = latest.average_metrics || {};
  const diagnoses = latest.diagnoses || {};
  const byCategory = latest.by_category || {};

  return (
    <PageShell>
      <div className="flex h-full min-h-0 flex-col">
        <PageHeader
          eyebrow="RAG Evaluation"
          title="Quality metrics in a more readable operational format"
          description="Track retrieval, context construction, and generation quality with clearer thresholds and per-query diagnostics."
        />

        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="ui-stack">
            <div className="metric-grid md:grid-cols-2 xl:grid-cols-4">
              <MetricTile
                label="Overall score"
                value={`${Math.round((latest.average_overall || 0) * 100)}%`}
                meta="Blended performance across the latest eval run"
                accent="var(--accent)"
              />
              <MetricTile
                label="Total evals"
                value={`${data.live_count || latest.total_evaluations || 0}`}
                meta={`${data.live_count || 0} live · ${data.batch_count || 0} batch`}
                accent="var(--success)"
              />
              <MetricTile
                label="Ideal diagnoses"
                value={diagnoses.ideal || 0}
                meta="Queries that met the desired outcome pattern"
                accent="var(--success)"
              />
              <MetricTile
                label="Hallucinations"
                value={diagnoses.hallucination || 0}
                meta="Cases flagged as unsupported generation"
                accent="var(--danger)"
              />
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              {Object.entries(LAYER_CONFIG).map(([layer, config]) => (
                <SurfaceCard key={layer}>
                  <SectionHeading
                    title={layer}
                    description="Threshold-aware metric view for this layer of the pipeline."
                  />
                  <div className="space-y-5 p-6 pt-4">
                    {config.metrics.map((metric) => (
                      <MetricBar
                        key={metric}
                        label={metric.replace(/_/g, ' ')}
                        value={avg[metric] || 0}
                        color={config.color}
                        threshold={THRESHOLDS[metric]}
                      />
                    ))}
                  </div>
                </SurfaceCard>
              ))}
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <SurfaceCard>
                <SectionHeading
                  title="Diagnosis distribution"
                  description="How the latest evaluation batch is partitioned by outcome diagnosis."
                />
                <div className="space-y-4 p-6 pt-4">
                  {Object.entries(diagnoses).map(([diagnosis, count]) => {
                    const percent = ((count as number) / (latest.total_evaluations || 1)) * 100;
                    return (
                      <div key={diagnosis}>
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <Badge tone={DIAGNOSIS_TONE[diagnosis] || 'accent'}>{diagnosis}</Badge>
                          <span className="text-sm text-[var(--text-muted)]">{count as number}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-[rgba(148,163,184,0.14)]">
                          <div
                            className="h-full rounded-full bg-[var(--accent)]"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </SurfaceCard>

              <SurfaceCard>
                <SectionHeading
                  title="Performance by category"
                  description="Average score and query volume segmented by your evaluation categories."
                />
                <div className="space-y-4 p-6 pt-4">
                  {Object.entries(byCategory).map(([category, info]: [string, any]) => (
                    <div
                      key={category}
                      className="flex items-center justify-between gap-4 rounded-[16px] border border-[var(--border)] bg-[var(--panel-soft)] px-4 py-4"
                    >
                      <div>
                        <div className="text-sm font-semibold text-[var(--text)]">{category}</div>
                        <div className="mt-1 text-sm text-[var(--text-soft)]">{info.total} queries</div>
                      </div>
                      <div className="font-mono text-lg font-semibold text-[var(--success)]">
                        {Math.round(info.avg_score * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </SurfaceCard>
            </div>

            <SurfaceCard>
              <SectionHeading
                title="Per-query breakdown"
                description="Low-level scores for the latest run to help pinpoint failure modes faster."
              />
              <div className="overflow-x-auto p-2">
                <table className="ui-table">
                  <thead>
                    <tr>
                      {['Query', 'Faith', 'Relevancy', 'Correct', 'Recall@k', 'Ctx Recall', 'Diagnosis', 'Latency'].map((heading) => (
                        <th key={heading}>{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(results || []).map((result: any, index: number) => {
                      const evaluation = result.evaluation || {};
                      const generation = evaluation.layer3_generation || {};
                      const retrieval = evaluation.layer1_retrieval || {};
                      const context = evaluation.layer2_context || {};
                      const ts = result.timestamp ? new Date(result.timestamp).toLocaleTimeString() : '';

                      return (
                        <tr key={index}>
                          <td className="max-w-[280px]">
                            <div className="truncate text-[var(--text)]">{result.query}</div>
                            {ts && <div className="text-xs text-[var(--text-muted)]">{ts}</div>}
                          </td>
                          <td className="font-mono">{Math.round((generation.faithfulness || 0) * 100)}%</td>
                          <td className="font-mono">{Math.round((generation.answer_relevancy || 0) * 100)}%</td>
                          <td className="font-mono">{Math.round((generation.answer_correctness || 0) * 100)}%</td>
                          <td className="font-mono">{Math.round((retrieval.recall_at_k || 0) * 100)}%</td>
                          <td className="font-mono">{Math.round((context.context_recall || 0) * 100)}%</td>
                          <td>
                            <Badge tone={DIAGNOSIS_TONE[evaluation.diagnosis] || 'accent'}>
                              {evaluation.diagnosis}
                            </Badge>
                          </td>
                          <td className="font-mono text-[var(--success)]">
                            {(evaluation.latency || 0).toFixed(1)}s
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SurfaceCard>

            {/* ── Auto-Tuner Feedback Loop ── */}
            {tuner && (
              <div className="grid gap-6 xl:grid-cols-2">
                <SurfaceCard>
                  <SectionHeading
                    title="🔄 Auto-Tuner — Live Parameters"
                    description={`Last tuned: ${tuner.last_tuned ? new Date(tuner.last_tuned).toLocaleString() : 'never'} · ${tuner.recent_eval_count || 0} evals analyzed`}
                  />
                  <div className="space-y-3 p-6 pt-4">
                    {Object.entries(tuner.params || {}).map(([key, value]: [string, any]) => {
                      const def = (tuner.defaults || {})[key];
                      const [lo, hi] = (tuner.bounds || {})[key] || [0, 100];
                      const changed = def !== undefined && value !== def;
                      const pct = typeof value === 'number' ? ((value - lo) / (hi - lo)) * 100 : 0;
                      return (
                        <div key={key}>
                          <div className="mb-1 flex items-center justify-between text-sm">
                            <span className="text-[var(--text-muted)]">{key.replace(/_/g, ' ')}</span>
                            <span className={`font-mono font-semibold ${changed ? 'text-[var(--warning)]' : 'text-[var(--text-soft)]'}`}>
                              {typeof value === 'number' && value % 1 !== 0 ? value.toFixed(3) : value}
                              {changed && <span className="ml-1 text-xs text-[var(--text-muted)]">(default: {def})</span>}
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(148,163,184,0.14)]">
                            <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${Math.min(100, Math.max(2, pct))}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </SurfaceCard>

                <SurfaceCard>
                  <SectionHeading
                    title="📜 Tuning History"
                    description="Recent auto-adjustments based on diagnosis patterns"
                  />
                  <div className="space-y-3 p-6 pt-4 max-h-[400px] overflow-y-auto">
                    {(tuner.history || []).slice().reverse().map((entry: any, i: number) => (
                      <div key={i} className="rounded-[12px] border border-[var(--border)] bg-[var(--panel-soft)] p-3">
                        <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                          <span>{new Date(entry.timestamp).toLocaleString()}</span>
                          <span>{entry.evals_analyzed} evals</span>
                        </div>
                        <div className="mt-2 space-y-1">
                          {(entry.reasons || []).map((reason: string, j: number) => (
                            <div key={j} className="text-sm text-[var(--warning)]">⚡ {reason}</div>
                          ))}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(entry.new_params || {}).map(([k, v]: [string, any]) => {
                            const old = (entry.old_params || {})[k];
                            if (old === v) return null;
                            const arrow = (v as number) > (old as number) ? '↑' : '↓';
                            return (
                              <span key={k} className="rounded-md bg-[var(--bg)] px-2 py-0.5 text-xs font-mono text-[var(--text-soft)]">
                                {k.replace(/_/g, ' ')}: {typeof old === 'number' && old % 1 !== 0 ? (old as number).toFixed(2) : old} → {typeof v === 'number' && (v as number) % 1 !== 0 ? (v as number).toFixed(2) : v} {arrow}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                    {(!tuner.history || tuner.history.length === 0) && (
                      <div className="text-sm text-[var(--text-muted)]">No tuning adjustments yet. The tuner runs every 25 queries.</div>
                    )}
                  </div>
                </SurfaceCard>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
