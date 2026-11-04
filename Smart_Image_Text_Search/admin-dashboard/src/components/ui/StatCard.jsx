export default function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  tone = 'green',
  sublabel,
  loading = false,
}) {
  const tones = {
    green: {
      bg: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400',
      border: 'hover:border-emerald-200 dark:hover:border-emerald-800',
      badge: 'text-emerald-700 bg-emerald-100/70 dark:bg-emerald-900/40 dark:text-emerald-300',
    },
    blue: {
      bg: 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400',
      border: 'hover:border-blue-200 dark:hover:border-blue-800',
      badge: 'text-blue-700 bg-blue-100/70 dark:bg-blue-900/40 dark:text-blue-300',
    },
    purple: {
      bg: 'bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400',
      border: 'hover:border-purple-200 dark:hover:border-purple-800',
      badge: 'text-purple-700 bg-purple-100/70 dark:bg-purple-900/40 dark:text-purple-300',
    },
    red: {
      bg: 'bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400',
      border: 'hover:border-rose-200 dark:hover:border-rose-800',
      badge: 'text-rose-700 bg-rose-100/70 dark:bg-rose-900/40 dark:text-rose-300',
    },
    amber: {
      bg: 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400',
      border: 'hover:border-amber-200 dark:hover:border-amber-800',
      badge: 'text-amber-700 bg-amber-100/70 dark:bg-amber-900/40 dark:text-amber-300',
    },
    gray: {
      bg: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400',
      border: 'hover:border-gray-300 dark:hover:border-gray-600',
      badge: 'text-gray-700 bg-gray-200 dark:bg-gray-700 dark:text-gray-300',
    },
  };

  const style = tones[tone] || tones.green;

  return (
    <div
      className={`relative overflow-hidden bg-white dark:bg-gray-800/90 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm transition-all duration-200 hover:shadow-md ${style.border}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </span>
        {Icon && (
          <div className={`p-2.5 rounded-lg ${style.bg} transition-colors`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        {loading ? (
          <div className="h-9 w-20 bg-gray-200 dark:bg-gray-700 animate-pulse rounded"></div>
        ) : (
          <span className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
            {value ?? '—'}
          </span>
        )}
        {trend && (
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${style.badge}`}>
            {trend}
          </span>
        )}
      </div>

      {sublabel && (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          {sublabel}
        </p>
      )}
    </div>
  );
}
