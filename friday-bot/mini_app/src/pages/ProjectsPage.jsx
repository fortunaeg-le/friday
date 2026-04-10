/**
 * Страница проектов — список проектов с прогресс-баром и подзадачами.
 * Этап 8.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  fetchProjects,
  createProject,
  createSubtask,
  updateSubtaskStatus,
} from '../api/client';

/** Текстовый прогресс-бар */
function ProgressBar({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-2 bg-tg-hint/20 rounded-full overflow-hidden">
        <div
          className="h-full bg-tg-button rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-tg-hint whitespace-nowrap">
        {done}/{total} · {pct}%
      </span>
    </div>
  );
}

/** Карточка одного проекта */
function ProjectCard({ project, onSubtaskToggle }) {
  const [expanded, setExpanded] = useState(false);
  const done = project.subtasks.filter((s) => s.status === 'done').length;
  const total = project.subtasks.length;

  const deadlineStr = project.deadline
    ? new Date(project.deadline + 'T00:00:00').toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: 'long',
      })
    : null;

  return (
    <div className="bg-tg-secondary rounded-xl p-4 mb-3">
      {/* Заголовок */}
      <button
        className="w-full text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex justify-between items-start gap-2">
          <span className="font-medium text-tg-text">{project.title}</span>
          <span className="text-tg-hint text-sm mt-0.5">{expanded ? '▲' : '▼'}</span>
        </div>
        {deadlineStr && (
          <p className="text-xs text-tg-hint mt-0.5">📅 до {deadlineStr}</p>
        )}
        <ProgressBar done={done} total={total} />
      </button>

      {/* Подзадачи */}
      {expanded && (
        <div className="mt-3 space-y-2">
          {project.subtasks.length === 0 && (
            <p className="text-sm text-tg-hint">Подзадач нет</p>
          )}
          {project.subtasks.map((sub) => (
            <SubtaskRow
              key={sub.id}
              subtask={sub}
              projectId={project.id}
              onToggle={onSubtaskToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Строка одной подзадачи */
function SubtaskRow({ subtask, projectId, onToggle }) {
  const isDone = subtask.status === 'done';
  const isSkipped = subtask.status === 'skipped';

  const icon = isDone ? '✅' : isSkipped ? '⏭' : '⬜';

  const handleClick = () => {
    if (isDone) {
      onToggle(projectId, subtask.id, 'pending');
    } else {
      onToggle(projectId, subtask.id, 'done');
    }
  };

  return (
    <button
      className="flex items-center gap-2 w-full text-left"
      onClick={handleClick}
    >
      <span className="text-base leading-none">{icon}</span>
      <span
        className={`text-sm ${isDone || isSkipped ? 'line-through text-tg-hint' : 'text-tg-text'}`}
      >
        {subtask.title}
      </span>
    </button>
  );
}

/** Форма создания проекта */
function NewProjectForm({ onCreated, onCancel }) {
  const [title, setTitle] = useState('');
  const [deadline, setDeadline] = useState('');
  const [subtitleInput, setSubtitleInput] = useState('');
  const [subtasks, setSubtasks] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const addSubtask = () => {
    const t = subtitleInput.trim();
    if (!t) return;
    setSubtasks((prev) => [...prev, t]);
    setSubtitleInput('');
  };

  const handleSave = async () => {
    if (!title.trim()) {
      setError('Введи название проекта');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const project = await createProject({
        title: title.trim(),
        deadline: deadline || null,
      });
      for (let i = 0; i < subtasks.length; i++) {
        await createSubtask(project.id, { title: subtasks[i], order_index: i });
      }
      onCreated();
    } catch (e) {
      setError(e.message || 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-tg-secondary rounded-xl p-4 mb-4">
      <p className="font-medium mb-3 text-tg-text">Новый проект</p>

      <input
        className="w-full bg-tg-bg border border-tg-hint/30 rounded-lg px-3 py-2 text-sm text-tg-text mb-2 outline-none focus:border-tg-button"
        placeholder="Название проекта"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <input
        type="date"
        className="w-full bg-tg-bg border border-tg-hint/30 rounded-lg px-3 py-2 text-sm text-tg-text mb-3 outline-none focus:border-tg-button"
        placeholder="Дедлайн (необязательно)"
        value={deadline}
        onChange={(e) => setDeadline(e.target.value)}
      />

      {/* Подзадачи */}
      {subtasks.length > 0 && (
        <ul className="mb-2 space-y-1">
          {subtasks.map((s, i) => (
            <li key={i} className="text-sm text-tg-text flex items-center gap-1">
              <span className="text-tg-hint">•</span> {s}
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-2 mb-3">
        <input
          className="flex-1 bg-tg-bg border border-tg-hint/30 rounded-lg px-3 py-2 text-sm text-tg-text outline-none focus:border-tg-button"
          placeholder="Подзадача..."
          value={subtitleInput}
          onChange={(e) => setSubtitleInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addSubtask()}
        />
        <button
          onClick={addSubtask}
          className="px-3 py-2 rounded-lg bg-tg-button/20 text-tg-button text-sm"
        >
          ➕
        </button>
      </div>

      {error && <p className="text-red-500 text-xs mb-2">{error}</p>}

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 py-2 rounded-lg bg-tg-button text-white text-sm font-medium disabled:opacity-50"
        >
          {saving ? 'Сохраняем...' : 'Создать'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg border border-tg-hint/30 text-tg-hint text-sm"
        >
          Отмена
        </button>
      </div>
    </div>
  );
}

/** Главная страница проектов */
export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch (e) {
      setError(e.message || 'Не удалось загрузить проекты');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleSubtaskToggle = async (projectId, subtaskId, newStatus) => {
    try {
      await updateSubtaskStatus(projectId, subtaskId, newStatus);
      setProjects((prev) =>
        prev.map((p) =>
          p.id !== projectId
            ? p
            : {
                ...p,
                subtasks: p.subtasks.map((s) =>
                  s.id === subtaskId ? { ...s, status: newStatus } : s
                ),
              }
        )
      );
    } catch (e) {
      // ignore
    }
  };

  const handleCreated = () => {
    setShowForm(false);
    loadProjects();
  };

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-lg font-semibold text-tg-text">Проекты</h1>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="text-tg-button text-sm font-medium"
          >
            ＋ Новый
          </button>
        )}
      </div>

      {showForm && (
        <NewProjectForm onCreated={handleCreated} onCancel={() => setShowForm(false)} />
      )}

      {loading && (
        <p className="text-center text-tg-hint py-8">Загрузка...</p>
      )}

      {!loading && error && (
        <p className="text-center text-red-500 py-8">{error}</p>
      )}

      {!loading && !error && projects.length === 0 && !showForm && (
        <div className="text-center py-12">
          <p className="text-4xl mb-3">📁</p>
          <p className="text-tg-hint">Проектов пока нет</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-4 px-5 py-2 rounded-full bg-tg-button text-white text-sm"
          >
            Создать первый проект
          </button>
        </div>
      )}

      {!loading &&
        projects.map((p) => (
          <ProjectCard key={p.id} project={p} onSubtaskToggle={handleSubtaskToggle} />
        ))}
    </div>
  );
}
