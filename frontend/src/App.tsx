import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import QueryDashboard from './pages/QueryDashboard';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import EvaluationMonitor from './pages/EvaluationMonitor';
import AdminPanel from './pages/AdminPanel';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/query" replace />} />
            <Route path="query" element={<QueryDashboard />} />
            <Route path="analytics" element={<AnalyticsDashboard />} />
            <Route path="evaluation" element={<EvaluationMonitor />} />
            <Route path="admin" element={<AdminPanel />} />
          </Route>
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
