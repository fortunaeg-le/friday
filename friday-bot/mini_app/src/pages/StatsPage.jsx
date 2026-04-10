/**
 * Страница статистики — полный дашборд.
 * Этап 10B.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { fetchStats } from '../api/client';

// ---------------------------------------------------------------------------
// Круговой прогресс (SVG)
// ---------------------------------------------------------------------------
function CircularProgress({ pct }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;

  return (
    <svg width="140" height="140" className="block mx-auto">
      <circle cx="70" cy="70" r={r} fill="none" stroke="var(--tg-theme-secondary-bg-color,#1c1c1e)"
        strokeWidth="12" />
      <circle cx="70" cy="70" r={r} fill="none" stroke="var(--tg-theme-button-color,#3478f6)"
        strokeWidth="12" strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 70 70)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      <text x="70" y="66" textAnchor="middle" dominantBaseline="middle"
        fontSize="22" fontWeight="700" fill="var(--tg-theme-text-color,#fff)">
        {pct}%
      </text>
      <text x="70" y="86" textAnchor="middle" fontSize="11"
        fill="var(--tg-theme-hint-color,#888)">выполнено</text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Переключатель периода
// ---------------------------------------------------------------------------
const PERIODS = [
  { id: 'week',  label: 'Неделя' },
  { id: 'month', label: 'Месяц' },
  { id: 'all',   label: 'Всё время' },
];

function PeriodSelector({ active, onChange }) {
  return (
    <div className="flex rounded-xl overflow-hidden border border-tg-hint/20 mb-5">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          onClick={() => onChange(p.id)}
          className={`flex-1 py-2 text-sm transition-colors
            ${active === p.id
              ? 'bg-tg-button text-white font-medium'
              : 'bg-tg-secondary text-tg-hint'}`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Прогресс-бар категории
// ---------------------------------------------------------------------------
const CAT_COLORS = {
  работа:    '#3478f6',
  здоровье:  '#34c759',
  личное:    '#ff9f0a',
  другое:    '#636366',
};

function CategoryBar({ category, rate }) {
  const color = CAT_COLORS[category] || '#636366';
  const pct = Math.round(rate * 100);
  return (
    <div className="mb-2">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-tg-text capitalize">{category}</span>
        <span className="text-tg-hint">{pct}%</span>
      </div>
      <div className="h-2 bg-tg-hint/20 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Кнопка «Поделиться»
// ---------------------------------------------------------------------------
function ShareButton({ cardRef }) {
  const [sharing, setSharing] = useState(false);

  const handleShare = async () => {
    if (!cardRef.current) return;
    setSharing(true);
    try {
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(cardRef.current, { useCORS: true, scale: 2 });
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'friday-stats.png';
        a.click();
        URL.revokeObjectURL(url);
      }, 'image/png');
    } catch (e) {
      console.error('Share error', e);
    } finally {
      setSharing(false);
    }
  };

  return (
    <button
      onClick={handleShare}
      disabled={sharing}
      className="w-full py-3 mt-4 rounded-xl border border-tg-button text-tg-button text-sm font-medium disabled:opacity-50"
    >
      {sharing ? 'Генерируем...' : '📤 Поделиться'}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Названия дней недели
// ---------------------------------------------------------------------------
const WD_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

// ---------------------------------------------------------------------------
// Главный компонент
// ---------------------------------------------------------------------------
export default function StatsPage() {
  const [period, setPeriod]   = useState('week');
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const cardRef = useRef(null);

  const loadStats = useCallback(async (p) => {
    setLoading(true);
    setError('');
    try {
      const d = await fetchStats(p);
      setData(d);
    } catch (e) {
      setError(e.message || 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(period); }, [period, loadStats]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-tg-hint">Загрузка...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  const pct = data ? Math.round(data.completion_rate * 100) : 0;
  const trend = data?.trend_delta ?? 0;
  const trendStr = trend === 0 ? 'без изменений'
    : `${trend > 0 ? '+' : ''}${trend}% к прошлому периоду`;

  // Данные для бар-чарта по дням недели
  const barData = (data?.best_days ?? [])
    .map((d) => ({ name: WD_LABELS[d.weekday], rate: Math.round(d.rate * 100) }))
    .sort((a, b) => WD_LABELS.indexOf(a.name) - WD_LABELS.indexOf(b.name));

  return (
    <div className="p-4 pb-6 overflow-y-auto">
      <PeriodSelector active={period} onChange={setPeriod} />

      {/* Карточка для шаринга */}
      <div ref={cardRef} className="bg-tg-bg">

        {/* Круговой прогресс */}
        <div className="flex flex-col items-center mb-5">
          <CircularProgress pct={pct} />
          <p className="text-tg-text mt-2">
            <span className="font-semibold">{Math.round(data?.completed_tasks ?? 0)}</span>
            <span className="text-tg-hint"> из {data?.total_tasks ?? 0} задач</span>
          </p>
        </div>

        {/* Тренд + серия */}
        <div className="flex gap-3 mb-5">
          <div className="flex-1 bg-tg-secondary rounded-xl p-3 text-center">
            <p className="text-xs text-tg-hint mb-1">Тренд</p>
            <p className={`font-semibold text-sm ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {trendStr}
            </p>
          </div>
          <div className="flex-1 bg-tg-secondary rounded-xl p-3 text-center">
            <p className="text-xs text-tg-hint mb-1">Серия</p>
            <p className="font-semibold text-sm text-tg-text">
              🔥 {data?.streak ?? 0} дн.
            </p>
          </div>
        </div>

        {/* Bar chart по дням недели */}
        {barData.length > 0 && (
          <div className="bg-tg-secondary rounded-xl p-4 mb-4">
            <p className="text-sm font-medium text-tg-text mb-3">По дням недели</p>
            <ResponsiveContainer width="100%" height={120}>
              <BarChart data={barData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--tg-theme-hint-color,#888)' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color,#888)' }}
                  tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(v) => [`${v}%`, 'Выполнено']}
                  contentStyle={{ background: 'var(--tg-theme-secondary-bg-color,#1c1c1e)', border: 'none', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill="var(--tg-theme-button-color,#3478f6)" fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Категории */}
        {(data?.category_stats ?? []).length > 0 && (
          <div className="bg-tg-secondary rounded-xl p-4 mb-4">
            <p className="text-sm font-medium text-tg-text mb-3">По категориям</p>
            {data.category_stats.map((c) => (
              <CategoryBar key={c.category} category={c.category} rate={c.rate} />
            ))}
          </div>
        )}

        {/* Топ невыполняемых */}
        {(data?.most_skipped ?? []).length > 0 && (
          <div className="bg-tg-secondary rounded-xl p-4 mb-4">
            <p className="text-sm font-medium text-tg-text mb-2">Чаще всего не выполняется</p>
            {data.most_skipped.map((t, i) => (
              <div key={i} className="flex justify-between text-sm py-1">
                <span className="text-tg-text truncate mr-2">{t.title}</span>
                <span className="text-tg-hint whitespace-nowrap">{t.skip_count} раз</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <ShareButton cardRef={cardRef} />
    </div>
  );
}
