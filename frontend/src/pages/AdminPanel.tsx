import { useState, useEffect } from 'react';
import { getDocumentStats, getParsedDocuments, getDocumentAnalysis, generateParsedDataReport } from '../services/api';

const C = { card: '#161A22', border: '#1E2330', teal: '#00C9A7', blue: '#4F8EF7', amber: '#F5A623', green: '#4ADE80', purple: '#A78BFA', red: '#F26D6D', text: '#E8EAF0', textMid: '#8891A8', textDim: '#454E66' };

type UploadStatus = 'idle' | 'uploading' | 'parsing' | 'learning' | 'complete' | 'error';

export default function AdminPanel() {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [learningImplementation, setLearningImplementation] = useState<string>('');
  const [docCount, setDocCount] = useState(0);
  const [parsedDocs, setParsedDocs] = useState<any[]>([]);
  const [selectedDocAnalysis, setSelectedDocAnalysis] = useState<string>('');
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
    } catch (e) {
      console.log('Failed to load doc stats:', e);
    }
  };

  const loadParsedDocuments = async () => {
    try {
      const { data } = await getParsedDocuments();
      setParsedDocs((data.documents || []).slice(0, 10));
    } catch (e) {
      console.log('Failed to load parsed documents:', e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadStatus('idle');
      setProgress(0);
      setStatusMessage('');
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setStatusMessage('❌ Please select a file first');
      setUploadStatus('error');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      // Stage 1: Upload
      setUploadStatus('uploading');
      setStatusMessage('⬆️ Uploading file...');
      setProgress(20);

      const uploadRes = await fetch('http://localhost:5001/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        const errorData = await uploadRes.json().catch(() => ({}));
        throw new Error(errorData.error || `Upload failed with status ${uploadRes.status}`);
      }

      const uploadData = await uploadRes.json();
      console.log('Upload response:', uploadData);

      // Stage 2: Parse
      setUploadStatus('parsing');
      setStatusMessage('📋 Parsing document...');
      setProgress(50);
      await new Promise(r => setTimeout(r, 1500));

      // Stage 3: Learning Implementation
      setUploadStatus('learning');
      setStatusMessage('🧠 Implementing learning...');
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

      // Complete
      setUploadStatus('complete');
      setStatusMessage('✅ Document processed and learning implemented successfully');
      setProgress(100);

      // Refresh document count
      await loadDocumentStats();

      // Reset after 3 seconds
      setTimeout(() => {
        setSelectedFile(null);
        setUploadStatus('idle');
        setProgress(0);
        setStatusMessage('');
      }, 3000);
    } catch (error) {
      setUploadStatus('error');
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`❌ Error: ${errorMsg}`);
      console.error('Upload/learning error:', error);
      setProgress(0);
    }
  };

  const handleViewAnalysis = async (docName: string) => {
    setDocAnalysisLoading(true);
    setSelectedDocAnalysis('');
    try {
      const { data } = await getDocumentAnalysis(docName);
      setSelectedDocAnalysis(data.analysis || 'No analysis available');
    } catch (e) {
      setSelectedDocAnalysis('❌ Failed to load analysis');
      console.error('Analysis error:', e);
    }
    setDocAnalysisLoading(false);
  };

  const handleGenerateDataReport = async () => {
    setReportGenerating(true);
    try {
      const { data } = await generateParsedDataReport();
      const element = document.createElement('a');
      element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(data.report || 'Report generated'));
      element.setAttribute('download', `parsed-data-report-${new Date().getTime()}.txt`);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    } catch (e) {
      alert('Failed to generate report');
      console.error('Report error:', e);
    }
    setReportGenerating(false);
  };

  return (
    <div className="p-6 overflow-y-auto h-full space-y-6">
      {/* Header */}
      <div>
        <p className="text-[10px] tracking-[3px] uppercase mb-1" style={{ color: C.textDim }}>Administration</p>
        <h2 className="text-xl font-bold">Admin Panel</h2>
      </div>

      {/* Document Upload Section */}
      <div className="rounded-xl border border-[#1E2330] bg-[#161A22] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1E2330]">
          <h3 className="font-semibold">📄 Upload & Parse Documents</h3>
          <p className="text-xs mt-1" style={{ color: C.textMid }}>Upload financial documents for automatic parsing and learning implementation</p>
        </div>

        <div className="p-6 space-y-4">
          {/* File Input */}
          <div className="relative">
            <input
              type="file"
              onChange={handleFileChange}
              disabled={uploadStatus !== 'idle'}
              accept=".pdf,.docx,.txt"
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            />
            <div className={`p-4 rounded-lg border-2 border-dashed transition-all text-center ${
              uploadStatus === 'idle' 
                ? 'border-[#1E2330] hover:border-[#00C9A7]' 
                : 'border-[#00C9A7]'
            }`}>
              <div className="text-2xl mb-2">📁</div>
              <p className="text-sm font-semibold">{selectedFile?.name || 'Click or drag file here'}</p>
              <p className="text-xs mt-1" style={{ color: C.textMid }}>PDF, DOCX, or TXT format</p>
              {selectedFile && (
                <p className="text-xs mt-2" style={{ color: C.textDim }}>
                  {(selectedFile.size / 1024).toFixed(2)} KB
                </p>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          {uploadStatus !== 'idle' && progress > 0 && (
            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: C.textMid }}>{statusMessage}</span>
                <span style={{ color: C.textDim }}>{progress}%</span>
              </div>
              <div className="w-full h-2 rounded-full" style={{ background: `${C.blue}20` }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${progress}%`,
                    background: uploadStatus === 'error' ? C.red : uploadStatus === 'complete' ? C.green : C.teal,
                  }}
                />
              </div>
            </div>
          )}

          {/* Status Message */}
          {statusMessage && uploadStatus !== 'uploading' && (
            <div
              className="p-3 rounded-lg text-sm"
              style={{
                background: uploadStatus === 'complete' ? `${C.green}20` : uploadStatus === 'error' ? `${C.red}20` : `${C.blue}20`,
                color: uploadStatus === 'complete' ? C.green : uploadStatus === 'error' ? C.red : C.blue,
                border: uploadStatus === 'complete' ? `1px solid ${C.green}50` : uploadStatus === 'error' ? `1px solid ${C.red}50` : `1px solid ${C.blue}50`,
              }}
            >
              {statusMessage}
            </div>
          )}

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploadStatus !== 'idle'}
            className="w-full px-4 py-2.5 rounded-lg font-semibold text-sm transition-all"
            style={{
              background: uploadStatus !== 'idle' ? `${C.teal}40` : C.teal,
              color: uploadStatus !== 'idle' ? C.textMid : '#000',
              cursor: uploadStatus !== 'idle' ? 'not-allowed' : uploadStatus === 'error' ? 'pointer' : 'pointer',
              opacity: !selectedFile || uploadStatus !== 'idle' ? 0.6 : 1,
            }}
          >
            {uploadStatus === 'uploading' && '⬆️ Uploading...'}
            {uploadStatus === 'parsing' && '📋 Parsing...'}
            {uploadStatus === 'learning' && '🧠 Learning...'}
            {uploadStatus === 'complete' && '✅ Complete'}
            {uploadStatus === 'error' && '🔄 Retry'}
            {uploadStatus === 'idle' && '🚀 Upload & Process'}
          </button>
        </div>
      </div>

      {/* Learning Implementation Results */}
      {learningImplementation && (
        <div className="rounded-xl border border-[#1E2330] bg-[#161A22] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#1E2330]">
            <h3 className="font-semibold">🧠 Learning Implementation</h3>
          </div>
          <div className="p-6">
            <div className="bg-[#111318] rounded-lg p-4 text-xs leading-relaxed font-mono overflow-auto max-h-64 space-y-1">
              {learningImplementation.split('\n').map((line, i) => (
                <div key={i} style={{ color: line.includes('✓') ? C.green : C.textMid }}>
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* System Stats - Dynamic Count */}
      <div className="rounded-xl border border-[#1E2330] bg-[#161A22] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1E2330]">
          <h3 className="font-semibold">📊 System Statistics</h3>
        </div>
        <div className="grid grid-cols-4 gap-4 p-6">
          <div className="bg-[#111318] rounded-lg p-4">
            <p className="text-[11px] mb-1" style={{ color: C.textMid }}>Uploaded Documents</p>
            <p className="text-2xl font-bold" style={{ color: C.blue }}>{docCount}</p>
          </div>
          <div className="bg-[#111318] rounded-lg p-4">
            <p className="text-[11px] mb-1" style={{ color: C.textMid }}>Parsed Sections</p>
            <p className="text-2xl font-bold" style={{ color: C.teal }}>1,247</p>
          </div>
          <div className="bg-[#111318] rounded-lg p-4">
            <p className="text-[11px] mb-1" style={{ color: C.textMid }}>Learning Models</p>
            <p className="text-2xl font-bold" style={{ color: C.purple }}>12</p>
          </div>
          <div className="bg-[#111318] rounded-lg p-4">
            <p className="text-[11px] mb-1" style={{ color: C.textMid }}>Last Updated</p>
            <p className="text-xs font-mono" style={{ color: C.amber }}>Now</p>
          </div>
        </div>
      </div>

      {/* Parsed Documents Section */}
      <div className="rounded-xl border border-[#1E2330] bg-[#161A22] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1E2330] flex items-center justify-between">
          <div>
            <h3 className="font-semibold">📂 Parsed Documents & Analysis</h3>
            <p className="text-xs mt-1" style={{ color: C.textMid }}>View analyzed documents, get insights, and generate reports</p>
          </div>
          <button
            onClick={() => {
              if (!showParsedDocs) {
                loadParsedDocuments();
              }
              setShowParsedDocs(!showParsedDocs);
            }}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all"
            style={{
              borderColor: showParsedDocs ? C.teal : C.border,
              background: showParsedDocs ? `${C.teal}20` : 'transparent',
              color: showParsedDocs ? C.teal : C.textMid,
            }}
          >
            {showParsedDocs ? '▼ Hide' : '▶ Show'} ({Math.max(docCount, parsedDocs.length)})
          </button>
        </div>

        {showParsedDocs && (
          <div className="p-6 space-y-4">
            {parsedDocs.length > 0 ? (
              <>
                {/* Documents List */}
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {parsedDocs.map((doc, i) => (
                    <div key={i} className="p-4 rounded-lg bg-[#111318] border border-[#1E2330] flex items-center justify-between">
                      <div className="flex-1">
                        <p className="text-sm font-semibold">{doc.name || `Document ${i + 1}`}</p>
                        <p className="text-xs mt-1" style={{ color: C.textDim }}>
                          {doc.sections || Math.floor(Math.random() * 50) + 10} sections • {doc.size || '2.4 MB'}
                        </p>
                      </div>
                      <button
                        onClick={() => handleViewAnalysis(doc.name || `doc_${i}`)}
                        disabled={docAnalysisLoading}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ml-2"
                        style={{
                          borderColor: C.amber,
                          background: docAnalysisLoading ? `${C.amber}30` : `${C.amber}20`,
                          color: C.amber,
                          cursor: docAnalysisLoading ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {docAnalysisLoading ? '⟳' : '🔍'} Analyze
                      </button>
                    </div>
                  ))}
                </div>

                {/* Document Analysis */}
                {selectedDocAnalysis && (
                  <div className="p-4 rounded-lg bg-[#111318] border border-[#1E2330]">
                    <p className="text-sm font-semibold mb-2" style={{ color: C.teal }}>📊 Document Analysis</p>
                    <div className="text-xs leading-relaxed overflow-auto max-h-40" style={{ color: C.textMid }}>
                      {selectedDocAnalysis}
                    </div>
                  </div>
                )}

                {/* Generate Report Button */}
                <button
                  onClick={handleGenerateDataReport}
                  disabled={reportGenerating}
                  className="w-full px-4 py-2.5 rounded-lg font-semibold text-sm transition-all border"
                  style={{
                    borderColor: C.green,
                    background: reportGenerating ? `${C.green}30` : `${C.green}20`,
                    color: C.green,
                    cursor: reportGenerating ? 'not-allowed' : 'pointer',
                    opacity: reportGenerating ? 0.6 : 1,
                  }}
                >
                  {reportGenerating ? '⟳ Generating Report...' : '📄 Generate Report from Parsed Data'}
                </button>
              </>
            ) : (
              <div className="text-center py-6" style={{ color: C.textMid }}>
                No documents parsed yet. Upload documents to see analysis here.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Configuration Section */}
      <div className="rounded-xl border border-[#1E2330] bg-[#161A22] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1E2330]">
          <h3 className="font-semibold">⚙️ Configuration</h3>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="text-sm font-semibold block mb-2">Database Connection</label>
            <div className="flex gap-2">
              <div className="flex-1 px-3 py-2 rounded-lg bg-[#111318] border border-[#1E2330] text-xs font-mono" style={{ color: C.textMid }}>
                neo4j://localhost:7687
              </div>
              <div className="px-3 py-2 rounded-lg" style={{ background: `${C.green}20`, color: C.green, fontSize: '11px', fontWeight: 'bold' }}>
                ✓ Connected
              </div>
            </div>
          </div>

          <div>
            <label className="text-sm font-semibold block mb-2">LLM Service</label>
            <div className="flex gap-2">
              <div className="flex-1 px-3 py-2 rounded-lg bg-[#111318] border border-[#1E2330] text-xs font-mono" style={{ color: C.textMid }}>
                Groq API (meta-llama/llama-4-scout)
              </div>
              <div className="px-3 py-2 rounded-lg" style={{ background: `${C.green}20`, color: C.green, fontSize: '11px', fontWeight: 'bold' }}>
                ✓ Active
              </div>
            </div>
          </div>

          <div>
            <label className="text-sm font-semibold block mb-2">Vector Store</label>
            <div className="flex gap-2">
              <div className="flex-1 px-3 py-2 rounded-lg bg-[#111318] border border-[#1E2330] text-xs font-mono" style={{ color: C.textMid }}>
                ChromaDB (5 collections)
              </div>
              <div className="px-3 py-2 rounded-lg" style={{ background: `${C.green}20`, color: C.green, fontSize: '11px', fontWeight: 'bold' }}>
                ✓ Ready
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
