/**
 * Автоформатирование времени: 9→09:00, 930→09:30, 14→14:00, 1430→14:30.
 * Возвращает отформатированную строку или null если ввод невалиден.
 */
export function formatTimeInput(raw) {
  const text = raw.trim().replace(/[.,\-]/g, ':');

  // Формат HH:MM
  if (text.includes(':')) {
    const parts = text.split(':');
    if (parts.length === 2) {
      const h = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      if (!isNaN(h) && !isNaN(m) && h >= 0 && h <= 23 && m >= 0 && m <= 59) {
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      }
    }
    return null;
  }

  // Только цифры
  if (!/^\d+$/.test(text)) return null;

  const num = parseInt(text, 10);

  // 0-23 → часы
  if (num >= 0 && num <= 23 && text.length <= 2) {
    return `${String(num).padStart(2, '0')}:00`;
  }
  // 100-959 → H:MM (930 → 09:30)
  if (num >= 100 && num <= 959) {
    const h = Math.floor(num / 100);
    const m = num % 100;
    if (m <= 59) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }
  // 1000-2359 → HH:MM (1430 → 14:30)
  if (num >= 1000 && num <= 2359) {
    const h = Math.floor(num / 100);
    const m = num % 100;
    if (h <= 23 && m <= 59) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  return null;
}

/** Форматирование даты для отображения: «ср, 9 апреля 2025» */
const MONTHS = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];
const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];

export function formatDateDisplay(date) {
  const d = new Date(date);
  const wd = WEEKDAYS[d.getDay()];
  const day = d.getDate();
  const month = MONTHS[d.getMonth()];
  const year = d.getFullYear();
  return `${wd}, ${day} ${month} ${year}`;
}

/** Дата в формате YYYY-MM-DD для API */
export function toISODate(date) {
  const d = new Date(date);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
