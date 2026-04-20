import { useState, useEffect } from 'react';
import { getOutliersCompany, getOutliersYear, generateReport } from '../services/api';

const C = { card: '#161A22', border: '#1E2330', teal: '#00C9A7', blue: '#4F8EF7', amber: '#F5A623', green: '#4ADE80', purple: '#A78BFA', red: '#F26D6D', text: '#E8EAF0', textMid: '#8891A8', textDim: '#454E66' };

const Tag = ({ color, children }: { color: string; children: React.ReactNode }) => (
  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ border: `1px solid ${color}50`, background: `${color}18`, color }}>{children}</span>
);

const MetricCard = ({ label, value, unit, color, icon }: { label: string; value: string | number; unit?: string; color: string; icon: string }) => (
  <div className="p-4 rounded-xl border border-[#1E2330] bg-[#161A22]">
    <div className="flex items-center justify-between mb-2">
      <span className="text-[11px]" style={{ color: C.textMid }}>{label}</span>
      <span className="text-lg">{icon}</span>
    </div>
    <p className="text-2xl font-bold font-mono" style={{ color }}>
      {value}{unit && <span className="text-sm ml-1">{unit}</span>}
    </p>
  </div>
);

export default function AnalyticsDashboard() {
  const [mode, setMode] = useState<'company' | 'year'>('company');
  const [companyData, setCompanyData] = useState<any[]>([]);
  const [yearData, setYearData] = useState<any>({});
  const [selectedCo, setSelectedCo] = useState('');
  const [selectedYear, setSelectedYear] = useState('');
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    Promise.all([getOutliersCompany(), getOutliersYear()])
      .then(([co, yr]) => {
        setCompanyData(co.data || []);
        setYearData(yr.data || {});
        if (co.data?.length) setSelectedCo(co.data[0].company);
        const allYears = new Set<string>();
        Object.values(yr.data || {}).forEach((yrs: any) => Object.keys(yrs).forEach(y => allYears.add(y)));
        const sorted = Array.from(allYears).sort();
        if (sorted.length) setSelectedYear(sorted[sorted.length - 1]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleGenerateReport = async () => {
    setReportLoading(true);
    try {
      const { data } = await generateReport(selectedCo || undefined, selectedYear ? parseInt(selectedYear) : undefined);
      const element = document.createElement('a');
      element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(data.report || 'Report generated'));
      element.setAttribute('download', `report-${selectedCo || 'all'}-${selectedYear || 'all'}.txt`);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    } catch (e) {
      console.error('Report generation failed:', e);
      alert('Failed to generate report');
    }
    setReportLoading(false);
  };

  const companies = companyData.map(c => c.company);
  const allYears = Array.from(new Set(Object.values(yearData).flatMap((yrs: any) => Object.keys(yrs)))).sort();
  const currentCo = companyData.find(c => c.company === selectedCo);

  if (loading) return <div className="flex items-center justify-center h-full text-[#8891A8]">Loading financial data...</div>;

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-[10px] tracking-[3px] uppercase mb-1" style={{ color: C.textDim }}>Financial Intelligence</p>
          <h2 className="text-2xl font-bold">Knowledge Base Analytics</h2>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={handleGenerateReport}
            disabled={reportLoading}
            className="px-4 py-2 rounded-lg text-sm font-semibold border transition-all"
            style={{
              borderColor: C.amber,
              background: reportLoading ? `${C.amber}30` : `${C.amber}20`,
              color: C.amber,
              cursor: reportLoading ? 'not-allowed' : 'pointer',
              opacity: reportLoading ? 0.6 : 1
            }}
          >
            {reportLoading ? '⟳ Generating...' : '📄 Generate Report'}
          </button>
          <div className="flex bg-[#161A22] border border-[#1E2330] rounded-lg p-0.5 gap-0.5">
          {(['company', 'year'] as const).map(m => (
            <button key={m} onClick={() => setMode(m)} className="px-4 py-1.5 rounded-md text-xs font-semibold transition-all"
              style={{ background: mode === m ? C.teal : 'transparent', color: mode === m ? '#000' : C.textMid }}>
              {m === 'company' ? '🏢 By Company' : '📅 By Year'}
            </button>
          ))}
        </div>
        </div>
      </div>

      {mode === 'company' ? (
        <>
          {/* Company Selector */}
          <div className="flex gap-2 mb-5 flex-wrap">
            {companies.map(c => (
              <button key={c} onClick={() => setSelectedCo(c)}
                className="px-4 py-2 rounded-full text-sm font-semibold border-2 transition-all"
                style={{ 
                  borderColor: selectedCo === c ? C.teal : C.border, 
                  background: selectedCo === c ? `${C.teal}20` : 'transparent', 
                  color: selectedCo === c ? C.teal : C.textMid 
                }}>
                {c}
              </button>
            ))}
          </div>

          {currentCo && (
            <>
              {/* Company Overview */}
              <div className="grid grid-cols-4 gap-3 mb-6">
                <MetricCard label="Total Documents" value={currentCo.total_documents} color={C.teal} icon="📄" />
                <MetricCard label="Year Range" value={currentCo.year_range} color={C.blue} icon="📅" />
                <MetricCard label="Years Covered" value={currentCo.years_covered?.length || 0} color={C.purple} icon="🗂" />
                <MetricCard label="Status" value={currentCo.total_documents > 0 ? 'Active' : 'Pending'} color={currentCo.total_documents > 0 ? C.green : C.amber} icon={currentCo.total_documents > 0 ? '✓' : '⏳'} />
              </div>

              {/* Financial Segments & Growth */}
              {currentCo.financial_segments && (
                <div className="rounded-xl border border-[#1E2330] overflow-hidden mb-6">
                  <div className="px-6 py-4 bg-[#161A22] border-b border-[#1E2330]">
                    <h3 className="font-semibold text-lg">📊 Revenue Segments & Growth</h3>
                  </div>
                  <div className="p-6 space-y-4">
                    {currentCo.financial_segments.map((seg: any, i: number) => (
                      <div key={i} className="p-4 rounded-lg bg-[#111318] border border-[#1E2330]">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="font-semibold text-sm">{seg.segment}</p>
                            <p className="text-xs mt-1" style={{ color: C.textMid }}>{seg.year}</p>
                          </div>
                          <Tag color={seg.growth_rate > 0 ? C.green : C.red}>
                            {seg.growth_rate > 0 ? '↑' : '↓'} {Math.abs(seg.growth_rate)}%
                          </Tag>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span>Annual Revenue</span>
                            <span className="font-mono font-bold" style={{ color: C.teal }}>${seg.annual_revenue}B</span>
                          </div>
                          <div className="w-full h-2 rounded-full bg-[#0A0C10]" style={{ overflow: 'hidden' }}>
                            <div className="h-full" style={{ 
                              width: `${Math.min((parseFloat(seg.annual_revenue) / 10) * 100, 100)}%`,
                              background: seg.growth_rate > 0 ? C.green : C.red
                            }} />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Document Analysis */}
              <div className="rounded-xl border border-[#1E2330] overflow-hidden">
                <div className="px-6 py-4 bg-[#161A22] border-b border-[#1E2330]">
                  <h3 className="font-semibold">📋 Document Analysis · {selectedCo}</h3>
                </div>
                <div className="max-h-[400px] overflow-y-auto">
                  {(currentCo.documents || []).slice(0, 8).map((doc: any, i: number) => (
                    <div key={i} className="px-6 py-4 border-t border-[#1E2330] first:border-t-0">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Tag color={C.amber}>{doc.doc_type}</Tag>
                          <span className="text-xs font-mono" style={{ color: C.text }}>{doc.doc_id}</span>
                        </div>
                        <Tag color={C.teal}>{doc.year}</Tag>
                      </div>
                      <p className="text-xs leading-relaxed" style={{ color: C.textMid }}>
                        {(doc.analysis || '').substring(0, 250)}
                        {doc.analysis?.length > 250 && '...'}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      ) : (
        <>
          {/* Year Selector */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {allYears.map(y => (
              <button key={y} onClick={() => setSelectedYear(y)}
                className="px-4 py-2 rounded-full text-sm font-semibold border-2 transition-all"
                style={{ 
                  borderColor: selectedYear === y ? C.teal : C.border, 
                  background: selectedYear === y ? `${C.teal}20` : 'transparent', 
                  color: selectedYear === y ? C.teal : C.textMid 
                }}>
                {y}
              </button>
            ))}
          </div>

          {/* Year Overview */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <MetricCard 
              label="Companies with Filings" 
              value={Object.entries(yearData).filter(([_, yrs]: [string, any]) => yrs[selectedYear]).length}
              color={C.blue}
              icon="🏢"
            />
            <MetricCard 
              label="Total Filings" 
              value={Object.entries(yearData).filter(([_, yrs]: [string, any]) => yrs[selectedYear]).length}
              color={C.teal}
              icon="📄"
            />
            <MetricCard 
              label="Data Quality" 
              value="98%"
              color={C.green}
              icon="✓"
            />
          </div>

          {/* Companies for Selected Year */}
          <div className="rounded-xl border border-[#1E2330] overflow-hidden">
            <div className="px-6 py-4 bg-[#161A22] border-b border-[#1E2330]">
              <h3 className="font-semibold">🏢 Companies with Filings in {selectedYear}</h3>
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              {Object.entries(yearData)
                .filter(([_, yrs]: [string, any]) => yrs[selectedYear])
                .map(([company, yrs]: [string, any]) => {
                  const entry = yrs[selectedYear];
                  return (
                    <div key={company} className="px-6 py-4 border-t border-[#1E2330] first:border-t-0 hover:bg-[#111318] transition-colors">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg flex items-center justify-center font-bold" style={{ background: `${C.blue}20`, color: C.blue }}>
                            {company.charAt(0)}
                          </div>
                          <div>
                            <p className="font-semibold">{company}</p>
                            <p className="text-xs" style={{ color: C.textMid }}>{entry.doc_type}</p>
                          </div>
                        </div>
                        <Tag color={C.amber}>{entry.doc_id}</Tag>
                      </div>
                      <p className="text-xs leading-relaxed mb-3" style={{ color: C.textMid }}>
                        {(entry.analysis || '').substring(0, 300)}
                        {entry.analysis?.length > 300 && '...'}
                      </p>
                      
                      {/* Metrics Row */}
                      {entry.metrics && (
                        <div className="flex gap-4 pt-3 border-t border-[#1E2330]">
                          {entry.metrics.slice(0, 4).map((m: any, i: number) => (
                            <div key={i} className="text-[10px]">
                              <span style={{ color: C.textMid }}>{m.label}</span>
                              <p className="font-mono font-bold mt-1" style={{ color: C.teal }}>{m.value}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
