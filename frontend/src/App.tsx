import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { Dashboard } from './pages/Dashboard';
import { About } from './pages/About';
import { Help } from './pages/Help';
import { Settings } from './pages/Settings';

// Candidate Assessment Flow
import { ExamList } from './pages/candidate/ExamList';
import { PreExamCheck } from './pages/candidate/PreExamCheck';
import { ExamRoom } from './pages/candidate/ExamRoom';
import { ExamResult } from './pages/candidate/ExamResult';

// Admin Assessment Management
import { AdminExamList } from './pages/admin/AdminExamList';
import { AdminExamBuilder } from './pages/admin/AdminExamBuilder';
import { AdminExamSessions } from './pages/admin/AdminExamSessions';

// Error & Fallback Routes
import { NotFound } from './pages/NotFound';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen bg-background flex flex-col">
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              {/* Public Pages */}
              <Route path="/" element={<Home />} />
              <Route path="/about" element={<About />} />

              {/* Authenticated Dashboard */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />

              {/* Authenticated Help & Settings */}
              <Route
                path="/help"
                element={
                  <ProtectedRoute>
                    <Help />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              />

            {/* Candidate Flow */}
            <Route
              path="/exams"
              element={
                <ProtectedRoute>
                  <ExamList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/exams/:examId/check"
              element={
                <ProtectedRoute>
                  <PreExamCheck />
                </ProtectedRoute>
              }
            />
            <Route
              path="/exams/:examId/take"
              element={
                <ProtectedRoute>
                  <ExamRoom />
                </ProtectedRoute>
              }
            />
            <Route
              path="/exams/:examId/result"
              element={
                <ProtectedRoute>
                  <ExamResult />
                </ProtectedRoute>
              }
            />

            {/* Admin Flow */}
            <Route
              path="/admin/exams"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminExamList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/exams/create"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminExamBuilder />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/exams/:examId/builder"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminExamBuilder />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/exams/:examId/sessions"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminExamSessions />
                </ProtectedRoute>
              }
            />

            {/* Auth Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
