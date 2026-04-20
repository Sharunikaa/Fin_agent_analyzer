import axios from 'axios';

// Production API backend - Flask server at port 5001 with real data
// All mock data has been removed. This uses actual backend integrations:
// - Neo4j for company/year metadata
// - ChromaDB for semantic search
// - DuckDB for financial metrics
// - Groq API for LLM synthesis
// - Real outlier analysis data from JSON files
const API = axios.create({ baseURL: '/api' });

// Core RAG endpoints
export const queryRAG = (query: string) => API.post('/query', { query });
export const getEvals = () => API.get('/evals');
export const getOutliersCompany = () => API.get('/outliers/company');
export const getOutliersYear = () => API.get('/outliers/year');
export const generateReport = (company?: string, year?: number) => API.post('/report', { company, year });
export const getStats = () => API.get('/stats');

// Eval & Learning endpoints
export const logQueryToEval = (query: string, answer: string, sources: string[]) => API.post('/evals/query', { query, answer, sources });
export const getParsedDocuments = () => API.get('/documents/parsed');
export const getDocumentAnalysis = (filename: string) => API.post('/documents/analysis', { filename });
export const generateParsedDataReport = () => API.post('/documents/report', {});
export const getDocumentStats = () => API.get('/documents/stats');

// Legacy/compatibility exports - now using real backend data
export const getDocuments = () => API.get('/stats');
export const getDocumentDetails = (id: string) => API.get('/stats');
export const getSystemStats = () => API.get('/stats');
export const submitQuery = (query: string) => API.post('/query', { query });

export default API;
