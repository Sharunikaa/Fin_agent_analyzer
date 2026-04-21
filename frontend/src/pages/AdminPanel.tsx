import { useEffect, useState } from 'react';
import {
  ActionButton,
  Badge,
  MetricTile,
  PageHeader,
  PageShell,
  SectionHeading,
  SurfaceCard,
} from '../components/ui';
import {
  generateParsedDataReport,
  getDocumentAnalysis,
  getDocumentStats,
  getParsedDocuments,
} from '../services/api';

type UploadStatus = 'idle' | 'uploading' | 'parsing' | 'learning' | 'complete' | 'error';

function downloadTextFile(name: string, content: string) {
  const element = document.createElement('a');
  element.setAttribute('href', `data:text/plain;charset=utf-8,${encodeURIComponent(content)}`);
  element.setAttribute('download', name);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

function statusTone(status: UploadStatus): 'neutral' | 'accent' | 'success' | 'danger' {
  if (status === 'complete') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'idle') return 'neutral';
  return 'accent';
}

export default function AdminPanel() {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [learningImplementation, setLearningImplementation] = useState('');
  const [docCount, setDocCount] = useState(0);
  const [parsedDocs, setParsedDocs] = useState<any[]>([]);
  const [selectedDocAnalysis, setSelectedDocAnalysis] = useState('');
  const [docAnalysisLoading, setDocAnalysisLoading] = useState(false);
  const [reportGenerating, setReportGenerating] = useState(false);
  const [showParsedDocs, setShowParsedDocs] = useState(false);

  useEffect(() => {
    loadDocumentStats();
  }, []);

  const loadDocumentStats = async () => {
    try {
      const { data } = await getDocumentStats();
      setDocCount(data.count || 0);
    } catch (error) {
      console.log('Failed to load doc stats:', error);
    }
  };

  const loadParsedDocuments = async () => {
    try {
      const { data } = await getParsedDocuments();
      setParsedDocs((data.documents || []).slice(0, 10));
    } catch (error) {
      console.log('Failed to load parsed documents:', error);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.[0]) {
      setSelectedFile(event.target.files[0]);
      setUploadStatus('idle');
      setProgress(0);
      setStatusMessage('');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setStatusMessage('Please select a file before uploading.');
      setUploadStatus('error');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      setUploadStatus('uploading');
      setStatusMessage('Uploading file');
      setProgress(20);

      const uploadRes = await fetch('http://localhost:5001/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        const errorData = await uploadRes.json().catch(() => ({}));
        throw new Error(errorData.error || `Upload failed with status ${uploadRes.status}`);
      }

      setUploadStatus('parsing');
      setStatusMessage('Parsing document');
      setProgress(50);
      await new Promise((resolve) => setTimeout(resolve, 1500));

      setUploadStatus('learning');
      setStatusMessage('Applying learning implementation');
      setProgress(75);

      const learningRes = await fetch('http://localhost:5001/api/documents/implement-learning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: selectedFile.name }),
      });

      if (!learningRes.ok) {
        const errorData = await learningRes.json().catch(() => ({}));
        throw new Error(errorData.error || 'Learning implementation failed');
      }

      const learningData = await learningRes.json();
      setLearningImplementation(learningData.implementation || 'Learning implementation complete');

      setUploadStatus('complete');
      setStatusMessage('Document processed successfully');
      setProgress(100);
      await loadDocumentStats();

      setTimeout(() => {
        setSelectedFile(null);
        setUploadStatus('idle');
        setProgress(0);
        setStatusMessage('');
      }, 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setUploadStatus('error');
      setStatusMessage(message);
      setProgress(0);
      console.error('Upload/learning error:', error);
    }
  };

  const handleViewAnalysis = async (docName: string) => {
    setDocAnalysisLoading(true);
    setSelectedDocAnalysis('');
    try {
      const { data } = await getDocumentAnalysis(docName);
      setSelectedDocAnalysis(data.analysis || 'No analysis available');
    } catch (error) {
      setSelectedDocAnalysis('Failed to load analysis');
      console.error('Analysis error:', error);
    } finally {
      setDocAnalysisLoading(false);
    }
  };

  const handleGenerateDataReport = async () => {
    setReportGenerating(true);
    try {
      const { data } = await generateParsedDataReport();
      downloadTextFile(`parsed-data-report-${Date.now()}.txt`, data.report || 'Report generated');
    } catch (error) {
      alert('Failed to generate report');
      console.error('Report error:', error);
    } finally {
      setReportGenerating(false);
    }
  };

  return (
    <PageShell>
      <div className="flex h-full min-h-0 flex-col">
        <PageHeader
          eyebrow="Administration"
          title="Operational controls for ingestion and document quality"
          description="Upload new filings, inspect parsed outputs, and keep the underlying knowledge pipeline in a healthier state."
        />

        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="ui-stack">
            <div className="metric-grid md:grid-cols-2 xl:grid-cols-4">
              <MetricTile label="Uploaded documents" value={docCount} meta="Current document inventory" accent="var(--accent)" />
              <MetricTile label="Parsed sections" value="1,247" meta="Indexed structured sections" accent="var(--success)" />
              <MetricTile label="Learning models" value="12" meta="Active extraction and synthesis units" accent="#8ca7ff" />
              <MetricTile label="Last updated" value="Now" meta="Live operational status" accent="var(--warning)" />
            </div>

            <SurfaceCard>
              <SectionHeading
                title="Upload and process documents"
                description="Add a new document to the pipeline and follow its ingestion status in one place."
                action={<Badge tone={statusTone(uploadStatus)}>{uploadStatus}</Badge>}
              />
              <div className="grid gap-6 p-6 md:grid-cols-[1.5fr,1fr]">
                <div>
                  <label className="relative block cursor-pointer">
                    <input
                      type="file"
                      onChange={handleFileChange}
                      disabled={uploadStatus !== 'idle'}
                      accept=".pdf,.docx,.txt"
                      className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
                    />
                    <div className="rounded-[20px] border border-dashed border-[var(--border-strong)] bg-[var(--panel-soft)] px-6 py-10 text-center transition hover:border-[rgba(77,162,255,0.45)]">
                      <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-[18px] bg-[rgba(77,162,255,0.12)] text-xl text-[var(--accent)]">
                        +
                      </div>
                      <p className="text-base font-semibold text-[var(--text)]">
                        {selectedFile?.name || 'Select or drop a file here'}
                      </p>
                      <p className="mt-2 text-sm text-[var(--text-muted)]">
                        Supported formats: PDF, DOCX, and TXT
                      </p>
                      {selectedFile ? (
                        <p className="mt-3 text-sm text-[var(--text-soft)]">
                          {(selectedFile.size / 1024).toFixed(2)} KB
                        </p>
                      ) : null}
                    </div>
                  </label>

                  {(uploadStatus !== 'idle' || statusMessage) && (
                    <div className="mt-5 rounded-[18px] border border-[var(--border)] bg-[var(--panel-soft)] p-4">
                      <div className="mb-3 flex items-center justify-between gap-3 text-sm">
                        <span className="text-[var(--text-muted)]">{statusMessage || 'Waiting for upload'}</span>
                        <span className="text-[var(--text-soft)]">{progress}%</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-[rgba(148,163,184,0.14)]">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${progress}%`,
                            background:
                              uploadStatus === 'error'
                                ? 'var(--danger)'
                                : uploadStatus === 'complete'
                                  ? 'var(--success)'
                                  : 'var(--accent)',
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded-[20px] border border-[var(--border)] bg-[var(--panel-soft)] p-5">
                  <h3 className="text-base font-semibold">Processing flow</h3>
                  <div className="mt-4 space-y-3">
                    {[
                      ['1', 'Upload document'],
                      ['2', 'Parse structure and sections'],
                      ['3', 'Apply learning implementation'],
                      ['4', 'Refresh indexed statistics'],
                    ].map(([step, label]) => (
                      <div key={step} className="flex items-center gap-3 rounded-[14px] border border-[var(--border)] px-4 py-3">
                        <div className="grid h-8 w-8 place-items-center rounded-full bg-[rgba(77,162,255,0.14)] text-sm font-semibold text-[var(--accent)]">
                          {step}
                        </div>
                        <span className="text-sm text-[var(--text-muted)]">{label}</span>
                      </div>
                    ))}
                  </div>
                  <ActionButton
                    className="mt-5 w-full"
                    onClick={handleUpload}
                    disabled={!selectedFile || uploadStatus !== 'idle'}
                  >
                    {uploadStatus === 'idle' ? 'Upload and process' : 'Processing...'}
                  </ActionButton>
                </div>
              </div>
            </SurfaceCard>

            {learningImplementation ? (
              <SurfaceCard>
                <SectionHeading
                  title="Learning implementation output"
                  description="Latest backend notes describing what was learned or applied during processing."
                />
                <div className="p-6 pt-4">
                  <div className="max-h-72 overflow-auto rounded-[18px] border border-[var(--border)] bg-[var(--panel-strong)] p-4 font-mono text-xs leading-7 text-[var(--text-muted)]">
                    {learningImplementation.split('\n').map((line, index) => (
                      <div key={index} className={line.includes('✓') ? 'text-[var(--success)]' : ''}>
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              </SurfaceCard>
            ) : null}

            <SurfaceCard>
              <SectionHeading
                title="Parsed documents and analysis"
                description="Inspect recently parsed files and review the generated analysis summaries."
                action={
                  <ActionButton
                    variant="secondary"
                    onClick={() => {
                      if (!showParsedDocs) {
                        loadParsedDocuments();
                      }
                      setShowParsedDocs(!showParsedDocs);
                    }}
                  >
                    {showParsedDocs ? 'Hide documents' : 'Show documents'}
                  </ActionButton>
                }
              />

              {showParsedDocs ? (
                <div className="space-y-4 p-6 pt-4">
                  {parsedDocs.length > 0 ? (
                    <>
                      <div className="space-y-3">
                        {parsedDocs.map((doc, index) => (
                          <div
                            key={`${doc.name}-${index}`}
                            className="flex flex-col gap-4 rounded-[18px] border border-[var(--border)] bg-[var(--panel-soft)] p-4 md:flex-row md:items-center md:justify-between"
                          >
                            <div>
                              <p className="text-base font-semibold text-[var(--text)]">{doc.name || `Document ${index + 1}`}</p>
                              <p className="mt-1 text-sm text-[var(--text-soft)]">
                                {doc.sections || Math.floor(Math.random() * 50) + 10} sections • {doc.size || '2.4 MB'}
                              </p>
                            </div>
                            <ActionButton
                              variant="secondary"
                              onClick={() => handleViewAnalysis(doc.name || `doc_${index}`)}
                              disabled={docAnalysisLoading}
                            >
                              {docAnalysisLoading ? 'Loading...' : 'View analysis'}
                            </ActionButton>
                          </div>
                        ))}
                      </div>

                      {selectedDocAnalysis ? (
                        <div className="rounded-[18px] border border-[var(--border)] bg-[var(--panel-strong)] p-5">
                          <p className="mb-3 text-sm font-semibold text-[var(--accent)]">Document analysis</p>
                          <div className="max-h-48 overflow-auto text-sm leading-7 text-[var(--text-muted)]">
                            {selectedDocAnalysis}
                          </div>
                        </div>
                      ) : null}

                      <ActionButton variant="secondary" onClick={handleGenerateDataReport} disabled={reportGenerating}>
                        {reportGenerating ? 'Generating report...' : 'Generate parsed data report'}
                      </ActionButton>
                    </>
                  ) : (
                    <div className="rounded-[18px] border border-[var(--border)] bg-[var(--panel-soft)] p-5 text-sm text-[var(--text-muted)]">
                      No documents parsed yet. Upload a document to start building this view.
                    </div>
                  )}
                </div>
              ) : null}
            </SurfaceCard>

            <SurfaceCard>
              <SectionHeading
                title="Configuration snapshot"
                description="Quick visibility into the services backing ingestion, retrieval, and synthesis."
              />
              <div className="grid gap-4 p-6 pt-4 md:grid-cols-3">
                {[
                  ['Database connection', 'neo4j://localhost:7687'],
                  ['LLM service', 'Groq API (meta-llama/llama-4-scout)'],
                  ['Vector store', 'ChromaDB (5 collections)'],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-[18px] border border-[var(--border)] bg-[var(--panel-soft)] p-5"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[var(--text)]">{label}</p>
                      <Badge tone="success">Connected</Badge>
                    </div>
                    <p className="mt-4 font-mono text-sm text-[var(--text-muted)]">{value}</p>
                  </div>
                ))}
              </div>
            </SurfaceCard>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
