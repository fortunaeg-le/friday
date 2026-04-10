/**
 * Страница настроек уведомлений.
 * Этап 12.
 */
import { useState, useEffect, useCallback } from 'react';
import { fetchSettings, updateSetting } from '../api/client';

const TYPE_LABELS = {
  morning_summary:    '🌅 Утренняя сводка',
  task_reminder:      '⏰ Напоминания о задачах',
  completion_check:   '✅ Проверки выполнения',
  window_suggestion:  '💡 Рекомендации в окна',
  weekly_report:      '📊 Еженедельный отчёт',
  monthly_report:     '📅 Ежемесячный отчёт',
  evening_reflection: '🌙 Вечерний дневник',
  quiet_day_summary:  '🌿 Сводка тихого дня',
};

function Toggle({ value, onChange }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        value ? 'bg-tg-button' : 'bg-tg-hint/30'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          value ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

function SettingRow({ setting, onUpdate }) {
  const [saving, setSaving] = useState(false);
  const [editMin, setEditMin] = useState(false);
  const [minVal, setMinVal] = useState(String(setting.remind_before_min ?? 15));

  const label = TYPE_LABELS[setting.type] || setting.type;

  const handleToggle = async (field, value) => {
    setSaving(true);
    try {
      await onUpdate(setting.type, { [field]: value });
    } finally {
      setSaving(false);
    }
  };

  const saveMin = async () => {
    const n = parseInt(minVal, 10);
    if (!n || n <= 0) return;
    setSaving(true);
    try {
      await onUpdate(setting.type, { remind_before_min: n });
      setEditMin(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`bg-tg-secondary rounded-xl p-4 mb-3 ${saving ? 'opacity-60' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-tg-text font-medium">{label}</span>
        <Toggle value={setting.enabled} onChange={(v) => handleToggle('enabled', v)} />
      </div>

      {setting.enabled && (
        <div className="space-y-2 border-t border-tg-hint/10 pt-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-tg-hint">Со звуком</span>
            <Toggle value={setting.sound_enabled} onChange={(v) => handleToggle('sound_enabled', v)} />
          </div>

          {setting.type === 'task_reminder' && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-tg-hint">За сколько минут</span>
              {editMin ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    value={minVal}
                    onChange={(e) => setMinVal(e.target.value)}
                    className="w-16 bg-tg-bg border border-tg-hint/30 rounded-lg px-2 py-1 text-sm text-tg-text text-right outline-none"
                  />
                  <button onClick={saveMin} className="text-tg-button text-sm">✓</button>
                </div>
              ) : (
                <button
                  onClick={() => setEditMin(true)}
                  className="text-sm text-tg-button"
                >
                  {setting.remind_before_min ?? 15} мин
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InputPreferences() {
  const [spaceCount, setSpaceCount] = useState(() => {
    return parseInt(localStorage.getItem('time_space_count') || '1', 10);
  });

  const handleChange = (val) => {
    setSpaceCount(val);
    localStorage.setItem('time_space_count', String(val));
  };

  return (
    <div className="bg-tg-secondary rounded-xl p-4 mb-3">
      <span className="text-tg-text font-medium">⌨️ Ввод времени</span>
      <div className="border-t border-tg-hint/10 pt-2 mt-3">
        <p className="text-sm text-tg-hint mb-2">
          Автозаполнение нулей при вводе пробела
        </p>
        <div className="flex gap-2">
          {[1, 2].map((n) => (
            <button
              key={n}
              onClick={() => handleChange(n)}
              className={`flex-1 py-1.5 rounded-lg text-sm border transition-colors ${
                spaceCount === n
                  ? 'bg-tg-button text-white border-tg-button'
                  : 'border-tg-hint/30 text-tg-hint'
              }`}
            >
              {n === 1 ? '1 пробел' : '2 пробела'}
            </button>
          ))}
        </div>
        <p className="text-xs text-tg-hint/60 mt-2">
          Введи цифры времени (9, 17, 1700) и нажми пробел {spaceCount === 2 ? 'дважды' : ''} — время заполнится автоматически
        </p>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchSettings();
      setSettings(data);
    } catch (e) {
      setError(e.message || 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpdate = async (ntype, updates) => {
    const updated = await updateSetting(ntype, updates);
    setSettings((prev) =>
      prev.map((s) => (s.type === ntype ? { ...s, ...updated } : s))
    );
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <p className="text-tg-hint">Загрузка...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-red-500">{error}</p>
    </div>
  );

  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold text-tg-text mb-4">Настройки</h1>
      <InputPreferences />
      {settings.map((s) => (
        <SettingRow key={s.type} setting={s} onUpdate={handleUpdate} />
      ))}
    </div>
  );
}
