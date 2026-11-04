import { useState, useEffect } from 'react';
import { useToast } from '../hooks/useToast';
import { API_BASE, getPreferences, savePreferences } from '../api';
import {
  Settings,
  Server,
  Mail,
  Sliders,
  Save,
  Check,
  Shield,
  Info,
  Lock,
} from 'lucide-react';

export default function SettingsPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState('general');

  // Preferences from localStorage
  const [prefs, setPrefs] = useState(() => getPreferences());
  const [saved, setSaved] = useState(false);

  const handleSavePreferences = (e) => {
    e.preventDefault();
    savePreferences(prefs);
    setSaved(true);
    toast.success('Frontend preferences saved successfully.');
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 animate-fadeIn max-w-5xl">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
          System & Dashboard Settings
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Configure API endpoints, default issuing policies, and inspect SMTP relay parameters.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 space-x-6 text-sm font-medium">
        <button
          type="button"
          onClick={() => setActiveTab('general')}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'general'
              ? 'border-emerald-600 text-emerald-600 dark:text-emerald-400 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Server className="w-4 h-4" />
          <span>General & Environment</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('email')}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'email'
              ? 'border-emerald-600 text-emerald-600 dark:text-emerald-400 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Mail className="w-4 h-4" />
          <span>Email Relay (SMTP)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('defaults')}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'defaults'
              ? 'border-emerald-600 text-emerald-600 dark:text-emerald-400 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Licence Defaults</span>
        </button>
      </div>

      {/* Tab: General & Environment */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm space-y-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Server className="w-5 h-5 text-emerald-600" />
              <span>API Gateway Configuration</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">
                  Active API Base URL
                </label>
                <div className="px-3.5 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-800 dark:text-gray-200 select-all">
                  {API_BASE}
                </div>
                <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                  Resolved via Vite environment build variable <code className="font-mono">VITE_API_BASE_URL</code>
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">
                  Dashboard Client Version
                </label>
                <div className="px-3.5 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-800 dark:text-gray-200">
                  v1.0.0 (Production Release)
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-gray-100 dark:border-gray-700/80">
              <div className="flex items-start gap-3 p-3.5 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/60 dark:border-emerald-800/60 text-xs text-emerald-900 dark:text-emerald-200">
                <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Secured Bearer Auth:</span>{' '}
                  All dashboard API requests use JSON Web Token headers issued by the cryptographic session authority.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Email Relay (SMTP) */}
      {activeTab === 'email' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <Mail className="w-5 h-5 text-emerald-600" />
                <span>SMTP Outbound Dispatch Settings</span>
              </h3>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60 font-medium">
                Backend Managed
              </span>
            </div>

            <p className="text-xs text-gray-500 dark:text-gray-400">
              The licensing server reads these variables from its private environment configuration file. To change SMTP credentials, update{' '}
              <code className="font-mono bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-800 dark:text-gray-200">
                .env
              </code>{' '}
              in your server deployment.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  SMTP Host
                </label>
                <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-600 dark:text-gray-400">
                  smtp.gmail.com / mail.prakshal.com
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  SMTP Port
                </label>
                <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-600 dark:text-gray-400">
                  587 (TLS) / 465 (SSL)
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Sender From Email
                </label>
                <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-600 dark:text-gray-400">
                  licensing@scanora.prakshal.com
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Authentication Security
                </label>
                <div className="px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-mono text-gray-600 dark:text-gray-400">
                  STARTTLS enabled
                </div>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>
                <strong>Mock Delivery Safeguard:</strong> When valid SMTP credentials are omitted, the backend will gracefully simulate key deliveries, marking records as <code>MOCK</code> in the logs without crashing client operations.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Licence Defaults */}
      {activeTab === 'defaults' && (
        <form onSubmit={handleSavePreferences} className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-emerald-600" />
                <span>Licence Generation Defaults</span>
              </h3>
              <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60">
                Frontend preference · saved to localStorage
              </span>
            </div>

            <p className="text-xs text-gray-500 dark:text-gray-400">
              These initial values will be automatically pre-selected when opening the licence generation dialog.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Default Licence Type
                </label>
                <select
                  value={prefs.defaultType}
                  onChange={(e) => setPrefs({ ...prefs, defaultType: e.target.value })}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="TRIAL">Trial (30 days)</option>
                  <option value="THREE_MONTHS">3 Months</option>
                  <option value="SIX_MONTHS">6 Months</option>
                  <option value="ONE_YEAR">1 Year (Standard)</option>
                  <option value="LIFETIME">Lifetime</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Default Device Concurrency Limit
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={prefs.defaultMaxDevices}
                  onChange={(e) => setPrefs({ ...prefs, defaultMaxDevices: Number(e.target.value) })}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Trial Duration (Days)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={prefs.trialDays}
                  onChange={(e) => setPrefs({ ...prefs, trialDays: Number(e.target.value) })}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-center pt-6">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-gray-700 dark:text-gray-300 select-none">
                  <input
                    type="checkbox"
                    checked={prefs.autoEmailOnCreate}
                    onChange={(e) => setPrefs({ ...prefs, autoEmailOnCreate: e.target.checked })}
                    className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Dispatch activation key email immediately upon creation</span>
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end pt-4 border-t border-gray-100 dark:border-gray-700">
              <button
                type="submit"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-all"
              >
                {saved ? <Check className="w-4 h-4 text-white" /> : <Save className="w-4 h-4" />}
                <span>{saved ? 'Saved!' : 'Save Preferences'}</span>
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
