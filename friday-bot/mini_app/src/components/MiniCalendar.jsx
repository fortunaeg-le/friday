import { useState, useEffect, useCallback } from 'react';
import { fetchCalendar } from '../api/client';
import { toISODate } from '../utils/time';

/** Названия месяцев в родительном падеже */
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

/** Заголовки дней недели: пн-вс */
const WEEKDAY_HEADERS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];

/** Цвет ячейки по количеству задач */
function dayBgClass(tasksCount) {
  if (tasksCount === 0) return '';
  if (tasksCount <= 2) return 'bg-gray-100 dark:bg-gray-700';
  if (tasksCount <= 5) return 'bg-gray-300 dark:bg-gray-600';
  return 'bg-red-300 dark:bg-red-700';
}

/** Первый день месяца (0=вс, 1=пн, ...) → сдвиг в сетке (пн=0) */
function monthStartOffset(year, month) {
  const day = new Date(year, month, 1).getDay(); // 0=вс
  return (day + 6) % 7; // пн=0
}

/** Количество дней в месяце */
function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

/**
 * MiniCalendar — bottom sheet с сеткой месяца.
 *
 * Props:
 *   selectedDate — Date, текущая выбранная дата
 *   onSelectDate — функция(Date), вызывается при клике на день
 *   onClose      — закрыть календарь
 */
export default function MiniCalendar({ selectedDate, onSelectDate, onClose }) {
  const today = new Date();
  const todayStr = toISODate(today);

  // Отображаемый месяц (год + индекс 0–11)
  const [viewYear, setViewYear] = useState(selectedDate.getFullYear());
  const [viewMonth, setViewMonth] = useState(selectedDate.getMonth());

  // Данные с бэкенда: { "YYYY-MM-DD": {tasks_count, is_quiet_day} }
  const [calendarData, setCalendarData] = useState({});

  /** Загрузить данные для видимого месяца */
  const loadMonth = useCallback(async (year, month) => {
    const from = toISODate(new Date(year, month, 1));
    const to = toISODate(new Date(year, month + 1, 0));
    try {
      const data = await fetchCalendar(from, to);
      setCalendarData((prev) => {
        const next = { ...prev };
        data.forEach((d) => {
          next[d.date] = { tasks_count: d.tasks_count, is_quiet_day: d.is_quiet_day };
        });
        return next;
      });
    } catch (err) {
      console.error('Ошибка загрузки календаря:', err);
    }
  }, []);

  useEffect(() => {
    loadMonth(viewYear, viewMonth);
  }, [viewYear, viewMonth, loadMonth]);

  /** Максимальный месяц = сегодня + 3 месяца */
  const maxYear = today.getFullYear() + Math.floor((today.getMonth() + 3) / 12);
  const maxMonth = (today.getMonth() + 3) % 12;

  const canGoForward =
    viewYear < maxYear || (viewYear === maxYear && viewMonth < maxMonth);

  function prevMonth() {
    if (viewMonth === 0) {
      setViewYear((y) => y - 1);
      setViewMonth(11);
    } else {
      setViewMonth((m) => m - 1);
    }
  }

  function nextMonth() {
    if (!canGoForward) return;
    if (viewMonth === 11) {
      setViewYear((y) => y + 1);
      setViewMonth(0);
    } else {
      setViewMonth((m) => m + 1);
    }
  }

  function handleDayClick(dayNum) {
    const clicked = new Date(viewYear, viewMonth, dayNum);
    onSelectDate(clicked);
    onClose();
  }

  // Построение сетки
  const offset = monthStartOffset(viewYear, viewMonth);
  const days = daysInMonth(viewYear, viewMonth);
  const cells = Array(offset).fill(null).concat(
    Array.from({ length: days }, (_, i) => i + 1)
  );
  // Дополнить до полных строк
  while (cells.length % 7 !== 0) cells.push(null);

  const selectedStr = toISODate(selectedDate);

  return (
    <>
      {/* Оверлей */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Bottom sheet */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-tg-bg rounded-t-2xl shadow-xl pb-safe">
        {/* Шапка с навигацией по месяцам */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-tg-secondary">
          <button
            onClick={prevMonth}
            className="text-tg-button text-xl px-2 py-1"
          >
            ◀
          </button>
          <span className="font-semibold text-tg-text">
            {MONTHS[viewMonth]} {viewYear}
          </span>
          <button
            onClick={nextMonth}
            disabled={!canGoForward}
            className={`text-xl px-2 py-1 ${canGoForward ? 'text-tg-button' : 'text-tg-hint opacity-40'}`}
          >
            ▶
          </button>
        </div>

        {/* Заголовок дней недели */}
        <div className="grid grid-cols-7 px-2 pt-2">
          {WEEKDAY_HEADERS.map((wd) => (
            <div key={wd} className="text-center text-xs text-tg-hint py-1">
              {wd}
            </div>
          ))}
        </div>

        {/* Сетка дней */}
        <div className="grid grid-cols-7 px-2 pb-4">
          {cells.map((day, idx) => {
            if (!day) {
              return <div key={`e-${idx}`} />;
            }

            const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const info = calendarData[dateStr] || { tasks_count: 0, is_quiet_day: false };
            const isToday = dateStr === todayStr;
            const isSelected = dateStr === selectedStr;

            return (
              <button
                key={dateStr}
                onClick={() => handleDayClick(day)}
                className={[
                  'relative flex flex-col items-center justify-center rounded-lg m-0.5 py-1.5 text-sm transition-colors',
                  isSelected
                    ? 'ring-2 ring-tg-button'
                    : '',
                  isToday
                    ? 'bg-tg-button text-white font-bold'
                    : dayBgClass(info.tasks_count),
                  !isToday ? 'text-tg-text' : '',
                ].join(' ')}
              >
                <span>{day}</span>
                {info.is_quiet_day && (
                  <span className="text-xs leading-none" title="Тихий день">🌿</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
