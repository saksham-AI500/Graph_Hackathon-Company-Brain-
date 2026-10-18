import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './context/ThemeContext';
import { MotionWrapper } from './components/MotionWrapper';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { AskPage } from './pages/AskPage';
import { ComparePage } from './pages/ComparePage';
import { GraphPage } from './pages/GraphPage';
import { EvaluationPage } from './pages/EvaluationPage';

export default function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MotionWrapper>
          <BrowserRouter>
            <div className="min-h-screen bg-surface text-on-surface flex flex-col font-sans transition-colors duration-200">
              <Header />
              <main className="flex-1 pt-14 flex flex-col">
                <Routes>
                  <Route path="/" element={<Navigate to="/ask" replace />} />
                  <Route path="/ask" element={<AskPage />} />
                  <Route path="/compare" element={<ComparePage />} />
                  <Route path="/graph" element={<GraphPage />} />
                  <Route path="/evaluation" element={<EvaluationPage />} />
                  <Route path="*" element={<Navigate to="/ask" replace />} />
                </Routes>
              </main>
              <Footer />
            </div>
          </BrowserRouter>
        </MotionWrapper>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
