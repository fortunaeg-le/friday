import { useState, useEffect, useCallback } from 'react';
import TaskRow from '../components/TaskRow';
import { fetchTasks, createTask, updateTask } from '../api/client';
import { formatDateDisplay, toISODate } from '../utils/time';

/** Сдвинуть дату на N дней */
function shiftDate(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** Извлечь строку времени HH:MM из scheduled_at */
function timeFromScheduled(scheduled_at) {
  if (!scheduled_at) return '';
  const d = new Date(scheduled_at);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

export default function SchedulePage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);

  /** Загрузка задач на выбранную дату */
  const loadTasks = useCallback(async (date) => {
    setLoading(true);
    try {
      const data = await fetchTasks(toISODate(date));
      setTasks(data.map((t) => ({
        ...t,
        timeStr: timeFromScheduled(t.scheduled_at),
      })));
    } catch (err) {
      console.error('Ошибка загрузки задач:', err);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks(currentDate);
  }, [currentDate, loadTasks]);

  /** Навигация по датам */
  const goBack = () => setCurrentDate((d) => shiftDate(d, -1));
  const goForward = () => setCurrentDate((d) => shiftDate(d, 1));
  const goToday = () => setCurrentDate(new Date());

  /** Сохранение новой задачи */
  const handleSave = async (data) => {
    const dateStr = toISODate(currentDate);
    const [h, m] = data.timeStr.split(':').map(Number);
    const scheduled = new Date(currentDate);
    scheduled.setHours(h, m, 0, 0);

    try {
      const created = await createTask({
        title: data.title,
        scheduled_at: scheduled.toISOString(),
        duration_min: data.duration_min,
      });
      // Перезагрузить список
      loadTasks(currentDate);
    } catch (err) {
      console.error('Ошибка создания задачи:', err);
    }
  };

  /** Обновление существующей задачи */
  const handleUpdate = async (taskId, data) => {
    const [h, m] = data.timeStr.split(':').map(Number);
    const scheduled = new Date(currentDate);
    scheduled.setHours(h, m, 0, 0);

    try {
      await updateTask(taskId, {
        title: data.title,
        scheduled_at: scheduled.toISOString(),
        duration_min: data.duration_min,
      });
    } catch (err) {
      console.error('Ошибка обновления задачи:', err);
    }
  };

  const isToday = toISODate(currentDate) === toISODate(new Date());

  return (
    <div className="flex flex-col h-full">
      {/* Навигация по датам */}
      <div className="flex items-center justify-between px-4 py-3 bg-tg-secondary">
        <button onClick={goBack} className="text-tg-button text-xl px-2">◀</button>
        <button
          onClick={goToday}
          className={`text-sm font-medium ${isToday ? 'text-tg-button' : 'text-tg-text'}`}
        >
          {formatDateDisplay(currentDate)}
        </button>
        <button onClick={goForward} className="text-tg-button text-xl px-2">▶</button>
      </div>

      {/* Список задач */}
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
              />
            ))}

            {/* Пустая строка для добавления новой задачи */}
            <TaskRow
              key={`new-${toISODate(currentDate)}`}
              task={null}
              onSave={handleSave}
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
    </div>
  );
}
