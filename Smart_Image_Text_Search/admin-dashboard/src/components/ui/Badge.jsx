export function Badge({ children, variant = 'gray', className = '', dot = true }) {
  const variants = {
    green: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60',
    red: 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800/60',
    amber: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/60',
    blue: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800/60',
    purple: 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-800/60',
    gray: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700',
  };

  const dots = {
    green: 'bg-emerald-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
    gray: 'bg-gray-400',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant] || variants.gray} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dots[variant] || dots.gray}`} />}
      {children}
    </span>
  );
}

export function LicenceStatusBadge({ status, isRevoked, isEnabled }) {
  if (isRevoked) {
    return <Badge variant="gray">Revoked</Badge>;
  }
  if (!isEnabled) {
    return <Badge variant="amber">Disabled</Badge>;
  }
  if (status === 'ACTIVE') {
    return <Badge variant="green">Active</Badge>;
  }
  if (status === 'UNUSED') {
    return <Badge variant="green">Active · Ready</Badge>;
  }
  if (status === 'EXPIRED') {
    return <Badge variant="red">Expired</Badge>;
  }
  return <Badge variant="gray">{status}</Badge>;
}

export function EmailStatusBadge({ status }) {
  const normalized = (status || '').toUpperCase();
  if (normalized === 'ACCEPTED' || normalized === 'SENT') {
    return <Badge variant="green">Sent</Badge>;
  }
  if (normalized === 'MOCK' || normalized === 'SIMULATED') {
    return <Badge variant="amber">Simulated</Badge>;
  }
  if (normalized === 'FAILED') {
    return <Badge variant="red">Failed</Badge>;
  }
  return <Badge variant="blue">{status || 'Queued'}</Badge>;
}

export default Badge;
