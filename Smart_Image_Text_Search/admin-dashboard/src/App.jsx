import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { getToken, logout as apiLogout } from './api';
import { ToastProvider } from './hooks/useToast';
import { DataProvider, useData } from './hooks/useApi';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import LicencesPage from './pages/LicencesPage';
import CustomersPage from './pages/CustomersPage';
import EmailPage from './pages/EmailPage';
import SettingsPage from './pages/SettingsPage';

function AuthenticatedApp({ adminEmail, onLogout }) {
  return (
    <Routes>
      <Route element={<AppShell adminEmail={adminEmail} onLogout={onLogout} />}>
        <Route index element={<DashboardPage />} />
        <Route path="licences" element={<LicencesPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="email" element={<EmailPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function MainApp() {
  const { authToken, setAuthToken } = useData();
  const navigate = useNavigate();
  const adminEmail = import.meta.env.VITE_ADMIN_EMAIL || 'admin@scanora.prakshal.com';

  const handleLoginSuccess = (token) => {
    setAuthToken(token);
    navigate('/', { replace: true });
  };

  const handleLogout = async () => {
    await apiLogout();
    setAuthToken('');
    navigate('/', { replace: true });
  };

  if (!authToken) {
    return (
      <LoginPage
        onLoginSuccess={handleLoginSuccess}
        defaultEmail={adminEmail}
      />
    );
  }

  return (
    <AuthenticatedApp
      adminEmail={adminEmail}
      onLogout={handleLogout}
    />
  );
}

export default function App() {
  return (
    <ToastProvider>
      <DataProvider>
        <MainApp />
      </DataProvider>
    </ToastProvider>
  );
}
