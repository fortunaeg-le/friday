import { useState, useEffect, useCallback } from 'react';
import TaskRow from '../components/TaskRow';
import MiniCalendar from '../components/MiniCalendar';
import { fetchTasks, createTask, updateTask, deleteTask } from '../api/client';
import { formatDateDisplay, toISODate } from '../utils/time';

/** Сдвинуть дату на N дней */
function shiftDate(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/**
 * Извлечь строку времени HH:MM из scheduled_at.
 * Сервер хранит UTC без 'Z' — добавляем его, чтобы JS корректно
 * конвертировал UTC → локальное время пользователя.
 */
function timeFromScheduled(scheduled_at) {
  if (!scheduled_at) return '';
  const utcStr = scheduled_at.endsWith('Z') ? scheduled_at : scheduled_at + 'Z';
  const d = new Date(utcStr);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

export default function SchedulePage() {
  const [currentDate, setCurrentDate]   = useState(new Date());
  const [tasks, setTasks]               = useState([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [spaceCount] = useState(() =>
    parseInt(localStorage.getItem('time_space_count') || '1', 10)
  );

  /** Загрузка задач на выбранную дату */
  const loadTasks = useCallback(async (date) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTasks(toISODate(date));
      // Задачи со временем сортируются бэкендом; задачи без времени — в конец
      const timed    = data.filter((t) => t.scheduled_at).map((t) => ({
        ...t, timeStr: timeFromScheduled(t.scheduled_at),
      }));
      const timeless = data.filter((t) => !t.scheduled_at).map((t) => ({
        ...t, timeStr: '',
      }));
      setTasks([...timed, ...timeless]);
    } catch (err) {
      console.error('Ошибка загрузки задач:', err);
      setError(`Загрузка: ${err.message}`);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTasks(currentDate); }, [currentDate, loadTasks]);

  const goBack    = () => setCurrentDate((d) => shiftDate(d, -1));
  const goForward = () => setCurrentDate((d) => shiftDate(d, 1));
  const goToday   = () => setCurrentDate(new Date());

  /** Сохранение новой задачи */
  const handleSave = async (data) => {
    let scheduled_at = null;
    if (data.timeStr) {
      const [h, m] = data.timeStr.split(':').map(Number);
      const scheduled = new Date(currentDate);
      scheduled.setHours(h, m, 0, 0);
      scheduled_at = scheduled.toISOString();
    }

    try {
      setError(null);
      await createTask({
        title:        data.title,
        scheduled_at,
        duration_min: data.duration_min,
        task_date:    toISODate(currentDate),
      });
      loadTasks(currentDate);
    } catch (err) {
      console.error('Ошибка создания задачи:', err);
      setError(`Сохранение: ${err.message}`);
    }
  };

  /** Обновление существующей задачи */
  const handleUpdate = async (taskId, data) => {
    let scheduled_at = null;
    if (data.timeStr) {
      const [h, m] = data.timeStr.split(':').map(Number);
      const scheduled = new Date(currentDate);
      scheduled.setHours(h, m, 0, 0);
      scheduled_at = scheduled.toISOString();
    }

    try {
      await updateTask(taskId, {
        title:        data.title,
        scheduled_at,
        duration_min: data.duration_min,
      });
      loadTasks(currentDate);
    } catch (err) {
      console.error('Ошибка обновления задачи:', err);
    }
  };

  /** Смена статуса задачи */
  const handleStatus = async (taskId, status) => {
    // Оптимистичное обновление
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status } : t))
    );
    try {
      await updateTask(taskId, { status });
    } catch (err) {
      console.error('Ошибка смены статуса:', err);
      loadTasks(currentDate); // откат
    }
  };

  /** Удаление задачи */
  const handleDelete = async (taskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
    try {
      await deleteTask(taskId);
    } catch (err) {
      console.error('Ошибка удаления задачи:', err);
      loadTasks(currentDate);
    }
  };

  const isToday = toISODate(currentDate) === toISODate(new Date());

  return (
    <div className="flex flex-col h-full">
      {/* Навигация по датам */}
      <div className="flex items-center justify-between px-4 py-3 bg-tg-secondary">
        <button onClick={goBack}    className="text-tg-button text-xl px-2">◀</button>
        <button
          onClick={() => setCalendarOpen(true)}
          className={`text-sm font-medium ${isToday ? 'text-tg-button' : 'text-tg-text'}`}
        >
          {formatDateDisplay(currentDate)}
        </button>
        <button onClick={goForward} className="text-tg-button text-xl px-2">▶</button>
      </div>

      {error && (
        <div className="mx-3 mt-2 p-2 bg-red-100 text-red-700 text-xs rounded">{error}</div>
      )}

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-tg-hint text-sm">Загрузка...</p>
          </div>
        ) : (
          <>
            {tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
                onStatus={handleStatus}
                spaceCount={spaceCount}
              />
            ))}

            {/* Пустая строка для добавления новой задачи */}
            <TaskRow
              key={`new-${toISODate(currentDate)}`}
              task={null}
              onSave={handleSave}
              spaceCount={spaceCount}
            />

            {tasks.length === 0 && !loading && (
              <div className="text-center py-6">
                <p className="text-tg-hint text-sm">Нет задач на этот день</p>
                <p className="text-tg-hint text-xs mt-1">Введи время и задачу выше</p>
              </div>
            )}
          </>
        )}
      </div>

      {calendarOpen && (
        <MiniCalendar
          selectedDate={currentDate}
          onSelectDate={(date) => setCurrentDate(date)}
          onClose={() => setCalendarOpen(false)}
        />
      )}
    </div>
  );
}
