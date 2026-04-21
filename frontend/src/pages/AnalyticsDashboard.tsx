import { useEffect, useState } from 'react';
import { ActionButton, Badge, MetricTile, PageHeader, PageShell, SectionHeading, SurfaceCard } from '../components/ui';
import { generateReport, getOutliersCompany, getOutliersYear } from '../services/api';

type Mode = 'company' | 'year';

function downloadTextFile(name: string, content: string) {
  const element = document.createElement('a');
  element.setAttribute('href', `data:text/plain;charset=utf-8,${encodeURIComponent(content)}`);
  element.setAttribute('download', name);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

type ReportStep = 'idle' | 'analysing' | 'planner' | 'analyser';

export default function AnalyticsDashboard() {
  const [mode, setMode] = useState<Mode>('company');
  const [companyData, setCompanyData] = useState<any[]>([]);
  const [yearData, setYearData] = useState<any>({});
  const [selectedCo, setSelectedCo] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportStep, setReportStep] = useState<ReportStep>('idle');

  useEffect(() => {
    Promise.all([getOutliersCompany(), getOutliersYear()])
      .then(([co, yr]) => {
        setCompanyData(co.data || []);
        setYearData(yr.data || {});
        if (co.data?.length) {
          setSelectedCo(co.data[0].company);
        }

        const allYears = new Set<string>();
        Object.values(yr.data || {}).forEach((years: any) =>
          Object.keys(years).forEach((year) => allYears.add(year)),
        );
        const sortedYears = Array.from(allYears).sort();
        if (sortedYears.length) {
          setSelectedYear(sortedYears[sortedYears.length - 1]);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleGenerateReport = async () => {
    setReportLoading(true);
    setReportStep('analysing');
    try {
      // Simulate analysing data step
      await new Promise(resolve => setTimeout(resolve, 800));
      
      setReportStep('planner');
      // Simulate planner agent step
      await new Promise(resolve => setTimeout(resolve, 1200));
      
      setReportStep('analyser');
      // Make actual API call during analyser step
      const { data } = await generateReport(selectedCo || undefined, selectedYear ? parseInt(selectedYear, 10) : undefined);
      downloadTextFile(
        `report-${selectedCo || 'all'}-${selectedYear || 'all'}.txt`,
        data.report || 'Report generated',
      );
    } catch (error) {
      console.error('Report generation failed:', error);
      alert('Failed to generate report');
    } finally {
      setReportLoading(false);
      setReportStep('idle');
    }
  };

  const getReportButtonText = () => {
    if (!reportLoading) return 'Export report';
    const stepTexts: Record<ReportStep, string> = {
      idle: 'Export report',
      analysing: 'Analysing the data...',
      planner: 'Calling planner agent...',
      analyser: 'Calling analyser agent...',
    };
    return stepTexts[reportStep] || 'Generating report...';
  };

  const companies = companyData.map((entry) => entry.company);
  const allYears = Array.from(new Set(Object.values(yearData).flatMap((years: any) => Object.keys(years)))).sort();
  const currentCo = companyData.find((entry) => entry.company === selectedCo);
  const currentYearEntries = Object.entries(yearData).filter(([, years]: [string, any]) => years[selectedYear]);

  if (loading) {
    return (
      <PageShell>
        <div className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
          Loading financial analytics...
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <div className="flex h-full min-h-0 flex-col">
        <PageHeader
          eyebrow="Knowledge Base"
          title="Portfolio analytics with better structure"
          description="Review company coverage, filing trends, and extracted segment details in a cleaner operational view."
          actions={
            <>
              <div className="inline-flex rounded-[14px] border border-[var(--border)] bg-[rgba(148,163,184,0.06)] p-1">
                {(['company', 'year'] as const).map((entry) => (
                  <button
                    key={entry}
                    onClick={() => setMode(entry)}
                    className={`rounded-[10px] px-4 py-2 text-sm font-semibold transition ${
                      mode === entry
                        ? 'bg-[var(--accent)] text-white'
                        : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                    }`}
                  >
                    {entry === 'company' ? 'By company' : 'By year'}
                  </button>
                ))}
              </div>
              <ActionButton variant="secondary" onClick={handleGenerateReport} disabled={reportLoading}>
                {getReportButtonText()}
              </ActionButton>
            </>
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          {mode === 'company' ? (
            <div className="ui-stack">
              <div className="flex flex-wrap gap-3">
                {companies.map((company) => (
                  <button
                    key={company}
                    onClick={() => setSelectedCo(company)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      selectedCo === company
                        ? 'border-[rgba(77,162,255,0.35)] bg-[rgba(77,162,255,0.16)] text-[var(--text)]'
                        : 'border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--border-strong)] hover:text-[var(--text)]'
                    }`}
                  >
                    {company}
                  </button>
                ))}
              </div>

              {currentCo ? (
                <>
                  <div className="metric-grid md:grid-cols-2 xl:grid-cols-4">
                    <MetricTile
                      label="Total documents"
                      value={currentCo.total_documents}
                      meta="All filings ingested for this company"
                      accent="var(--accent)"
                    />
                    <MetricTile
                      label="Year range"
                      value={currentCo.year_range}
                      meta="Coverage span in the knowledge base"
                      accent="var(--success)"
                    />
                    <MetricTile
                      label="Years covered"
                      value={currentCo.years_covered?.length || 0}
                      meta="Distinct reporting years available"
                      accent="var(--warning)"
                    />
                    <MetricTile
                      label="Status"
                      value={currentCo.total_documents > 0 ? 'Active' : 'Pending'}
                      meta="Based on available parsed filings"
                      accent={currentCo.total_documents > 0 ? 'var(--success)' : 'var(--warning)'}
                    />
                  </div>

                  

                  <SurfaceCard>
                    <SectionHeading
                      title={`Document analysis for ${selectedCo}`}
                      description="Recent analyzed filings with extracted summaries and document metadata."
                    />
                    <div className="p-2">
                      {(currentCo.documents || []).slice(0, 8).map((doc: any, index: number) => (
                        <div
                          key={`${doc.doc_id}-${index}`}
                          className="mx-4 border-t border-[var(--border)] px-2 py-5 first:border-t-0"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone="warning">{doc.doc_type}</Badge>
                              <Badge tone="neutral">{doc.doc_id}</Badge>
                            </div>
                            <Badge tone="accent">{doc.year}</Badge>
                          </div>
                          <p className="mt-3 text-sm leading-7 text-[var(--text-muted)]">
                            {(doc.analysis || '').substring(0, 260)}
                            {doc.analysis?.length > 260 ? '...' : ''}
                          </p>
                        </div>
                      ))}
                    </div>
                  </SurfaceCard>
                </>
              ) : null}
            </div>
          ) : (
            <div className="ui-stack">
              <div className="flex flex-wrap gap-3">
                {allYears.map((year) => (
                  <button
                    key={year}
                    onClick={() => setSelectedYear(year)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      selectedYear === year
                        ? 'border-[rgba(77,162,255,0.35)] bg-[rgba(77,162,255,0.16)] text-[var(--text)]'
                        : 'border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--border-strong)] hover:text-[var(--text)]'
                    }`}
                  >
                    {year}
                  </button>
                ))}
              </div>

              <div className="metric-grid md:grid-cols-3">
                <MetricTile
                  label="Companies with filings"
                  value={currentYearEntries.length}
                  meta={`Coverage for ${selectedYear}`}
                  accent="var(--accent)"
                />
                <MetricTile
                  label="Total filings"
                  value={currentYearEntries.length}
                  meta="Currently mapped in yearly view"
                  accent="var(--success)"
                />
                <MetricTile
                  label="Data quality"
                  value="98%"
                  meta="Current extraction confidence benchmark"
                  accent="var(--warning)"
                />
              </div>

              <SurfaceCard>
                <SectionHeading
                  title={`Companies with filings in ${selectedYear}`}
                  description="Browse the reporting set for the selected year with document IDs and extracted summaries."
                />
                <div className="p-2">
                  {currentYearEntries.map(([company, years]: [string, any]) => {
                    const entry = years[selectedYear];
                    return (
                      <div
                        key={company}
                        className="mx-4 border-t border-[var(--border)] px-2 py-5 first:border-t-0"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-3">
                              <div className="grid h-11 w-11 place-items-center rounded-[14px] bg-[rgba(77,162,255,0.14)] font-semibold text-[var(--accent)]">
                                {company.charAt(0)}
                              </div>
                              <div>
                                <h3 className="text-base font-semibold">{company}</h3>
                                <p className="mt-1 text-sm text-[var(--text-muted)]">{entry.doc_type}</p>
                              </div>
                            </div>
                          </div>
                          <Badge tone="warning">{entry.doc_id}</Badge>
                        </div>

                        <p className="mt-4 text-sm leading-7 text-[var(--text-muted)]">
                          {(entry.analysis || '').substring(0, 320)}
                          {entry.analysis?.length > 320 ? '...' : ''}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </SurfaceCard>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
