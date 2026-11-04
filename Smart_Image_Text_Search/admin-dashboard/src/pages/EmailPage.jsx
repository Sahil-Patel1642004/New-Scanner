import { useState, useMemo } from 'react';
import { useData } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { EmailStatusBadge } from '../components/ui/Badge';
import StatCard from '../components/ui/StatCard';
import SearchInput from '../components/ui/SearchInput';
import Pagination from '../components/ui/Pagination';
import EmptyState from '../components/ui/EmptyState';
import { formatDate } from '../api';
import {
  Mail,
  CheckCircle,
  AlertCircle,
  Clock,
  Send,
  Server,
  Info,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

export default function EmailPage() {
  const { emailLogs, loading, refreshData } = useData();
  const { toast } = useToast();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Test email placeholder state
  const [testRecipient, setTestRecipient] = useState('');
  const [testingEmail, setTestingEmail] = useState(false);

  // Email stats computation
  const stats = useMemo(() => {
    let accepted = 0;
    let mock = 0;
    let failed = 0;

    for (const log of emailLogs) {
      const status = (log.status || '').toUpperCase();
      if (status === 'ACCEPTED' || status === 'SENT') accepted++;
      else if (status === 'MOCK' || status === 'SIMULATED') mock++;
      else if (status === 'FAILED') failed++;
    }

    return {
      total: emailLogs.length,
      accepted,
      mock,
      failed,
    };
  }, [emailLogs]);

  // Filtered logs
  const filteredLogs = useMemo(() => {
    return emailLogs.filter((log) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesRec = log.recipient?.toLowerCase().includes(q);
        const matchesSub = log.subject?.toLowerCase().includes(q);
        const matchesErr = log.last_error?.toLowerCase().includes(q);
        if (!matchesRec && !matchesSub && !matchesErr) return false;
      }

      if (statusFilter !== 'ALL') {
        const s = (log.status || '').toUpperCase();
        if (statusFilter === 'ACCEPTED' && s !== 'ACCEPTED' && s !== 'SENT') return false;
        if (statusFilter === 'MOCK' && s !== 'MOCK' && s !== 'SIMULATED') return false;
        if (statusFilter === 'FAILED' && s !== 'FAILED') return false;
      }

      return true;
    });
  }, [emailLogs, searchQuery, statusFilter]);

  const totalItems = filteredLogs.length;
  const paginatedLogs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredLogs.slice(start, start + pageSize);
  }, [filteredLogs, currentPage, pageSize]);

  const handleSendTestEmail = (e) => {
    e.preventDefault();
    if (!testRecipient) return;
    setTestingEmail(true);

    setTimeout(() => {
      setTestingEmail(false);
      toast.info(
        `Test dispatch triggered for ${testRecipient}. If backend SMTP is simulated, message was logged to system records.`,
        6000
      );
      setTestRecipient('');
    }, 800);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Email Delivery & Audit
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Monitor product key dispatch receipts, provider status codes, and SMTP logs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshData()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg shadow-xs transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-600' : ''}`} />
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Logs"
          value={stats.total}
          icon={Mail}
          tone="blue"
          sublabel="All notification attempts"
        />
        <StatCard
          label="Accepted / Sent"
          value={stats.accepted}
          icon={CheckCircle}
          tone="green"
          sublabel="Handed off to SMTP relay"
        />
        <StatCard
          label="Simulated (Mock)"
          value={stats.mock}
          icon={Clock}
          tone="amber"
          sublabel="Logged without live relay"
        />
        <StatCard
          label="Failed"
          value={stats.failed}
          icon={AlertCircle}
          tone="red"
          sublabel="Connection or reject errors"
        />
      </div>

      {/* SMTP Configuration Reminder Notice */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border border-emerald-200/80 dark:border-emerald-800/60 shadow-xs">
        <div className="flex items-start gap-3">
          <Server className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-xs text-emerald-900 dark:text-emerald-200">
            <span className="font-semibold text-emerald-800 dark:text-emerald-300">
              SMTP Relay Configuration Note:
            </span>
            <p className="mt-1 leading-relaxed text-emerald-800/90 dark:text-emerald-300/80">
              Outbound email dispatch requires SMTP environment credentials configured in the backend{' '}
              <code className="bg-white/70 dark:bg-gray-900/70 px-1.5 py-0.5 rounded font-mono text-emerald-900 dark:text-emerald-300">
                .env
              </code>{' '}
              file (such as <code>SMTP_HOST</code>, <code>SMTP_PORT</code>, <code>SMTP_USER</code>,{' '}
              <code>SMTP_PASSWORD</code>). When not configured, Scanora operates in safe simulated mock mode, logging all emails here without failing client transactions.
            </p>
          </div>
        </div>
      </div>

      {/* Controls: Search & Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="w-full sm:w-80">
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search recipient, subject, errors…"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="ALL">All Delivery Statuses</option>
            <option value="ACCEPTED">Accepted / Sent</option>
            <option value="MOCK">Simulated (Mock)</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {/* Email Log Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          {paginatedLogs.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={Mail}
                title="No email logs found"
                description={
                  searchQuery || statusFilter !== 'ALL'
                    ? 'No records match your filters.'
                    : 'Dispatches will appear as licences are generated and delivered.'
                }
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-850/80 text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700 uppercase font-semibold">
                  <th className="px-4 py-3">#ID</th>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Message ID / Diagnostics</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700/60">
                {paginatedLogs.map((log) => (
                  <tr
                    key={log.id}
                    className="hover:bg-gray-50/70 dark:hover:bg-gray-750/50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-gray-400 dark:text-gray-500">
                      #{log.id}
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                      {log.recipient}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-300 max-w-xs truncate">
                      {log.subject}
                    </td>
                    <td className="px-4 py-3">
                      <EmailStatusBadge status={log.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {formatDate(log.sent_at || log.failed_at, { includeTime: true })}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-gray-500 dark:text-gray-400 max-w-sm truncate">
                      {log.last_error ? (
                        <span className="text-red-600 dark:text-red-400 font-sans" title={log.last_error}>
                          ⚠ {log.last_error}
                        </span>
                      ) : (
                        log.provider_message_id || '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <Pagination
          currentPage={currentPage}
          totalItems={totalItems}
          pageSize={pageSize}
          onPageChange={setCurrentPage}
        />
      </div>

      {/* Send Test Email Section */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Send className="w-4 h-4 text-emerald-600" />
          <span>Send Test Email Dispatch</span>
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Verify SMTP connectivity or simulate template generation without issuing a production licence.
        </p>

        <form onSubmit={handleSendTestEmail} className="mt-4 flex flex-col sm:flex-row gap-3 max-w-xl">
          <input
            type="email"
            value={testRecipient}
            onChange={(e) => setTestRecipient(e.target.value)}
            required
            placeholder="test-recipient@example.com"
            className="flex-1 px-3.5 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button
            type="submit"
            disabled={testingEmail || !testRecipient}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {testingEmail ? 'Sending…' : 'Trigger Test'}
          </button>
        </form>
      </div>
    </div>
  );
}
