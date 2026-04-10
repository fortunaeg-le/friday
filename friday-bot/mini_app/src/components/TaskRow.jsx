import { useState, useRef, useEffect } from 'react';
import { formatTimeInput } from '../utils/time';

/**
 * Строка задачи в ежедневнике.
 * Поля: время (автоформатирование), название, длительность (опц.).
 * spaceCount — сколько пробелов нужно ввести для автозаполнения нулей (1 или 2).
 */
export default function TaskRow({ task, onSave, onUpdate, spaceCount = 1 }) {
  const [time, setTime] = useState(task?.timeStr || '');
  const [title, setTitle] = useState(task?.title || '');
  const [duration, setDuration] = useState(task?.duration_min ?? '');
  const [timeFormatted, setTimeFormatted] = useState(!!task?.timeStr);
  const titleRef = useRef(null);
  const saved = useRef(false);

  // Синхронизация при загрузке задач с сервера
  useEffect(() => {
    if (task?.timeStr) { setTime(task.timeStr); setTimeFormatted(true); }
    if (task?.title) setTitle(task.title);
    if (task?.duration_min != null) setDuration(task.duration_min);
  }, [task?.id]);

  /** Автоформатирование времени при потере фокуса */
  const handleTimeBlur = () => {
    if (!time) return;
    const formatted = formatTimeInput(time.trim());
    if (formatted) {
      setTime(formatted);
      setTimeFormatted(true);
      // Фокус переходит на поле задачи
      titleRef.current?.focus();
    }
  };

  /** Обработка ввода времени: пробельный триггер автозаполнения */
  const handleTimeChange = (e) => {
    const val = e.target.value;
    const trigger = ' '.repeat(spaceCount);
    if (val.endsWith(trigger)) {
      const textPart = val.trimEnd();
      if (textPart.length > 0) {
        const formatted = formatTimeInput(textPart);
        if (formatted) {
          setTime(formatted);
          setTimeFormatted(true);
          titleRef.current?.focus();
          return;
        }
      }
    }
    setTime(val);
    setTimeFormatted(false);
  };

  /** Сохранение при потере фокуса или Enter */
  const handleSave = () => {
    if (saved.current) return;
    if (!time || !title.trim()) return;

    const formatted = formatTimeInput(time);
    if (!formatted) return;

    saved.current = true;

    const data = {
      timeStr: formatted,
      title: title.trim(),
      duration_min: duration ? parseInt(duration, 10) : null,
    };

    if (task?.id) {
      onUpdate?.(task.id, data);
    } else {
      onSave?.(data);
    }

    // Сбросить флаг чтобы позволить повторное сохранение при изменении
    setTimeout(() => { saved.current = false; }, 500);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
  };

  const statusIcon = task?.status === 'done' ? '✅'
    : task?.status === 'partial' ? '🔶'
    : task?.status === 'skipped' ? '⏭'
    : '';

  return (
    <div className="flex items-start gap-2 py-2 px-3 border-b border-tg-hint/10">
      {/* Время */}
      <input
        type="text"
        inputMode="decimal"
        placeholder="09:00"
        value={time}
        onChange={handleTimeChange}
        onBlur={handleTimeBlur}
        onKeyDown={(e) => { if (e.key === 'Enter') handleTimeBlur(); }}
        className={`w-14 shrink-0 text-center bg-transparent border-b
          ${timeFormatted ? 'border-tg-button text-tg-text font-medium' : 'border-tg-hint/30 text-tg-hint'}
          focus:outline-none focus:border-tg-button py-1 text-sm`}
      />

      {/* Название задачи */}
      <div className="flex-1 min-w-0">
        <textarea
          ref={titleRef}
          placeholder="Задача..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          rows={1}
          className="w-full bg-transparent resize-none text-sm text-tg-text
            placeholder:text-tg-hint/50 focus:outline-none leading-relaxed py-1
            overflow-hidden"
          style={{ minHeight: '28px' }}
          onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = e.target.scrollHeight + 'px'; }}
        />
      </div>

      {/* Длительность */}
      <input
        type="text"
        inputMode="numeric"
        placeholder="мин"
        value={duration}
        onChange={(e) => setDuration(e.target.value.replace(/\D/g, ''))}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className="w-10 shrink-0 text-center text-xs text-tg-hint bg-transparent
          border-b border-tg-hint/20 focus:outline-none focus:border-tg-button py-1"
      />

      {/* Статус */}
      {statusIcon && <span className="text-sm shrink-0 pt-1">{statusIcon}</span>}
    </div>
  );
}
