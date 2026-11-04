import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useData } from '../hooks/useApi';
import StatCard from '../components/ui/StatCard';
import { LicenceStatusBadge, EmailStatusBadge } from '../components/ui/Badge';
import EmptyState from '../components/ui/EmptyState';
import { formatDate, todayString } from '../api';
import {
  Key,
  Users,
  CheckCircle,
  Clock,
  Mail,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  Copy,
  Eye,
  EyeOff,
  Plus,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
} from 'recharts';
import { useToast } from '../hooks/useToast';

export default function DashboardPage() {
  const {
    loading,
    dashboard,
    customers,
    licences,
    emailLogs,
    revealProductKey,
  } = useData();

  const { toast } = useToast();
  const [revealedKeys, setRevealedKeys] = useState({});
  const [loadingKeyId, setLoadingKeyId] = useState(null);

  const summary = dashboard?.dashboard || {};
  const today = todayString();

  // Robust metric computations:
  // If licences array is loaded, calculate directly from actual data records;
  // otherwise, fall back to backend summary.
  const totalLicences = Math.max(licences.length, summary.total_licences || 0);
  const totalCustomers = Math.max(customers.length, summary.total_customers || 0);

  const computedActive = licences.filter(
    (l) => l.is_enabled && !l.is_revoked && (!l.expiry_date || l.expiry_date >= today)
  ).length;
  const activeCount = summary.active_licences ? Math.max(summary.active_licences, computedActive) : computedActive;

  const computedExpired = licences.filter(
    (l) => (l.expiry_date && l.expiry_date < today) || l.status === 'EXPIRED'
  ).length;
  const expiredCount = summary.expired_licences !== undefined && summary.expired_licences > 0
    ? summary.expired_licences
    : computedExpired;

  const disabledCount = licences.filter((l) => !l.is_enabled && !l.is_revoked).length;
  const revokedCount = licences.filter((l) => l.is_revoked).length;
  const emailsSent = Math.max(emailLogs.length, summary.emails_sent || 0);

  // Recent items (last 5)
  const recentLicences = [...licences].slice(0, 5);
  const recentEmails = [...emailLogs].slice(0, 5);

  // Status breakdown data for Recharts BarChart
  const statusChartData = [
    { name: 'Active', count: activeCount, fill: '#16a34a' },
    { name: 'Expired', count: expiredCount, fill: '#dc2626' },
    { name: 'Disabled', count: disabledCount, fill: '#d97706' },
    { name: 'Revoked', count: revokedCount, fill: '#64748b' },
  ];

  // Dummy monthly trend data (clearly labelled as requested)
  const monthlyTrendData = [
    { month: 'Jun', licences: Math.max(1, Math.round(totalLicences * 0.15)) },
    { month: 'Jul', licences: Math.max(1, Math.round(totalLicences * 0.3)) },
    { month: 'Aug', licences: Math.max(2, Math.round(totalLicences * 0.45)) },
    { month: 'Sep', licences: Math.max(2, Math.round(totalLicences * 0.65)) },
    { month: 'Oct', licences: Math.max(3, Math.round(totalLicences * 0.85)) },
    { month: 'Nov', licences: totalLicences },
  ];

  const handleToggleKey = async (licence) => {
    if (revealedKeys[licence.id]) {
      setRevealedKeys((prev) => {
        const next = { ...prev };
        delete next[licence.id];
        return next;
      });
      return;
    }

    setLoadingKeyId(licence.id);
    try {
      const res = await revealProductKey(licence.id);
      setRevealedKeys((prev) => ({ ...prev, [licence.id]: res.product_key }));
    } catch (err) {
      toast.error(err.message || 'Could not reveal key');
    } finally {
      setLoadingKeyId(null);
    }
  };

  const handleCopyKey = async (keyText) => {
    try {
      await navigator.clipboard.writeText(keyText);
      toast.success('Key copied to clipboard');
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Licensing Overview
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Real-time telemetry, active customer entitlements, and security activity.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/licences"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm shadow-emerald-600/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Manage Licences</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="Total Licences"
          value={totalLicences}
          icon={Key}
          tone="purple"
          sublabel="All issued licences"
          loading={loading}
        />
        <StatCard
          label="Active Licences"
          value={activeCount}
          icon={CheckCircle}
          tone="green"
          trend="Healthy"
          sublabel="Ready for activation"
          loading={loading}
        />
        <StatCard
          label="Expired"
          value={expiredCount}
          icon={Clock}
          tone="red"
          sublabel="Past validity date"
          loading={loading}
        />
        <StatCard
          label="Total Customers"
          value={totalCustomers}
          icon={Users}
          tone="blue"
          sublabel="Registered accounts"
          loading={loading}
        />
        <StatCard
          label="Emails Logged"
          value={emailsSent}
          icon={Mail}
          tone="amber"
          sublabel="Delivery audit logs"
          loading={loading}
        />
      </div>

      {/* Visual Analytics / Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution Bar Chart */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Licence Status Distribution
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Breakdown across active, expired, disabled, and revoked states
              </p>
            </div>
          </div>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: 'rgba(0,0,0,0.04)' }}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Issuance Trend Area Chart */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                  Licence Growth Trend
                </h3>
                <span className="text-[10px] font-medium bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  Cumulative
                </span>
              </div>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Trend data - connect to analytics API for live metrics
              </p>
            </div>
          </div>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monthlyTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="emeraldGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="licences"
                  stroke="#10b981"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#emeraldGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Two Columns: Recent Licences & Recent Email Delivery */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Licences Table (2 cols) */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col">
          <div className="p-5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                Recent Licences
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Latest customer product activations
              </p>
            </div>
            <Link
              to="/licences"
              className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 flex items-center gap-1 transition-colors"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto flex-1">
            {recentLicences.length === 0 ? (
              <EmptyState
                icon={Key}
                title="No licences generated yet"
                description="Issue your first product activation key from the Licences tab."
              />
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-850/80 text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700 uppercase font-semibold">
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Key</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Valid Until</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700/60">
                  {recentLicences.map((lic) => {
                    const cust = customers.find((c) => c.id === lic.customer_id);
                    const isRevealed = Boolean(revealedKeys[lic.id]);
                    const keyString = isRevealed ? revealedKeys[lic.id] : lic.masked_product_key;

                    return (
                      <tr key={lic.id} className="hover:bg-gray-50 dark:hover:bg-gray-750/50 transition-colors">
                        <td className="px-4 py-3 font-mono text-gray-400">#{lic.id}</td>
                        <td className="px-4 py-3">
                          <div className="font-semibold text-gray-900 dark:text-white">
                            {cust?.name || `Customer #${lic.customer_id}`}
                          </div>
                          <div className="text-gray-500 dark:text-gray-400 truncate max-w-[140px]">
                            {cust?.email}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <code className="bg-gray-100 dark:bg-gray-900 px-2 py-0.5 rounded font-mono text-[11px] text-gray-800 dark:text-gray-200">
                              {keyString}
                            </code>
                            <button
                              type="button"
                              onClick={() => handleToggleKey(lic)}
                              disabled={loadingKeyId === lic.id}
                              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                              title={isRevealed ? 'Hide' : 'Reveal Key'}
                            >
                              {isRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </button>
                            {isRevealed && (
                              <button
                                type="button"
                                onClick={() => handleCopyKey(keyString)}
                                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                                title="Copy"
                              >
                                <Copy className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <LicenceStatusBadge
                            status={lic.status}
                            isEnabled={lic.is_enabled}
                            isRevoked={lic.is_revoked}
                          />
                        </td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-300 whitespace-nowrap">
                          {formatDate(lic.expiry_date)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Recent Email Activity (1 col) */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col">
          <div className="p-5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                Email Delivery
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recent licence notifications
              </p>
            </div>
            <Link
              to="/email"
              className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 flex items-center gap-1 transition-colors"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="p-4 flex-1">
            {recentEmails.length === 0 ? (
              <EmptyState
                icon={Mail}
                title="No email logs"
                description="Delivery records will appear when licence keys are emailed."
              />
            ) : (
              <div className="space-y-3">
                {recentEmails.map((log) => (
                  <div
                    key={log.id}
                    className="p-3 rounded-lg bg-gray-50 dark:bg-gray-850/60 border border-gray-100 dark:border-gray-700/60 flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-xs text-gray-900 dark:text-white truncate">
                        {log.recipient}
                      </span>
                      <EmailStatusBadge status={log.status} />
                    </div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400 truncate">
                      {log.subject}
                    </div>
                    <div className="text-[10px] text-gray-400 dark:text-gray-500">
                      {formatDate(log.sent_at || log.failed_at, { includeTime: true })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
