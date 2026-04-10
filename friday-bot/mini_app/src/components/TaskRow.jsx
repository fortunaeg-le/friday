import { useState, useRef, useEffect } from 'react';
import { formatTimeInput } from '../utils/time';

/**
 * Строка задачи в ежедневнике.
 * Props:
 *   task        — объект задачи или null (новая строка)
 *   onSave      — callback(data) для новой задачи
 *   onUpdate    — callback(id, data) для существующей задачи
 *   onDelete    — callback(id) для удаления задачи
 *   onStatus    — callback(id, status) для смены статуса
 *   spaceCount  — кол-во пробелов для триггера автозаполнения (1 или 2)
 */
export default function TaskRow({ task, onSave, onUpdate, onDelete, onStatus, spaceCount = 1 }) {
  const [time, setTime]           = useState(task?.timeStr || '');
  const [title, setTitle]         = useState(task?.title || '');
  const [duration, setDuration]   = useState(task?.duration_min ?? '');
  const [timeFormatted, setTimeFormatted] = useState(!!task?.timeStr);
  const containerRef = useRef(null);
  const titleRef     = useRef(null);
  const saved        = useRef(false);

  // Синхронизация при загрузке задач с сервера
  useEffect(() => {
    if (task?.timeStr !== undefined) { setTime(task.timeStr || ''); setTimeFormatted(!!task.timeStr); }
    if (task?.title !== undefined)   setTitle(task.title);
    if (task?.duration_min != null)  setDuration(task.duration_min);
  }, [task?.id]);

  /** Автоформатирование времени при потере фокуса */
  const handleTimeBlur = () => {
    if (!time) return;
    const formatted = formatTimeInput(time.trim());
    if (formatted) {
      setTime(formatted);
      setTimeFormatted(true);
      titleRef.current?.focus();
    } else {
      // невалидное — сбросить
      setTime('');
      setTimeFormatted(false);
    }
  };

  /** Пробельный триггер автозаполнения */
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

  /** Сохранение — вызывается когда фокус покидает весь row */
  const handleSave = () => {
    if (saved.current) return;
    if (!title.trim()) return; // минимум — название

    // Время может быть пустым (задача без времени)
    let finalTime = null;
    if (time) {
      const formatted = formatTimeInput(time.trim());
      if (!formatted) return; // время введено, но невалидно — не сохраняем
      finalTime = formatted;
    }

    saved.current = true;

    const data = {
      timeStr:     finalTime,
      title:       title.trim(),
      duration_min: duration ? parseInt(duration, 10) : null,
    };

    if (task?.id) {
      onUpdate?.(task.id, data);
    } else {
      onSave?.(data);
      // Сбросить поля для следующей задачи
      setTime(''); setTitle(''); setDuration('');
      setTimeFormatted(false);
    }

    setTimeout(() => { saved.current = false; }, 500);
  };

  /**
   * Blur на контейнере — срабатывает когда фокус уходит ЗА ПРЕДЕЛЫ строки.
   * Если фокус просто переходит между полями внутри строки — игнорируем.
   */
  const handleContainerBlur = (e) => {
    if (containerRef.current?.contains(e.relatedTarget)) return;
    handleSave();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
  };

  /** Цикл статусов: pending → done → partial → skipped → pending */
  const STATUS_CYCLE = ['pending', 'done', 'partial', 'skipped'];
  const handleStatusClick = () => {
    if (!task?.id) return;
    const cur = task.status || 'pending';
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(cur) + 1) % STATUS_CYCLE.length];
    onStatus?.(task.id, next);
  };

  const statusIcon = task?.status === 'done'    ? '✅'
    : task?.status === 'partial'  ? '🔶'
    : task?.status === 'skipped'  ? '⏭'
    : task?.id                    ? '⬜'  // pending — кликабельный
    : '';

  const isTimeless = task?.id && !task?.timeStr;

  return (
    <div
      ref={containerRef}
      onBlur={handleContainerBlur}
      className="flex items-start gap-2 py-2 px-3 border-b border-tg-hint/10"
    >
      {/* Статус (только для существующих задач) */}
      {task?.id && (
        <button
          onMouseDown={(e) => e.preventDefault()} // не уводить фокус
          onClick={handleStatusClick}
          className="shrink-0 text-base pt-1 leading-none"
          title="Сменить статус"
        >
          {statusIcon}
        </button>
      )}

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
          onKeyDown={handleKeyDown}
          rows={1}
          className={`w-full bg-transparent resize-none text-sm
            ${isTimeless ? 'italic text-tg-hint' : 'text-tg-text'}
            ${task?.status === 'done' || task?.status === 'skipped' ? 'line-through opacity-60' : ''}
            placeholder:text-tg-hint/50 focus:outline-none leading-relaxed py-1 overflow-hidden`}
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
        onKeyDown={handleKeyDown}
        className="w-10 shrink-0 text-center text-xs text-tg-hint bg-transparent
          border-b border-tg-hint/20 focus:outline-none focus:border-tg-button py-1"
      />

      {/* Удалить (только существующие задачи) */}
      {task?.id && (
        <button
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => onDelete?.(task.id)}
          className="shrink-0 text-tg-hint/40 hover:text-red-400 text-lg leading-none pt-0.5 px-0.5"
          title="Удалить"
        >
          ×
        </button>
      )}
    </div>
  );
}
