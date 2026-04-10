/**
 * Страница проектов — список проектов с прогресс-баром, подзадачами,
 * редактированием/удалением и секцией незавершённых задач.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  fetchProjects,
  createProject,
  createSubtask,
  updateSubtaskStatus,
  deleteProject,
  updateProject,
  fetchPartialTasks,
} from '../api/client';

/** Текстовый прогресс-бар */
function ProgressBar({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-2 bg-tg-hint/20 rounded-full overflow-hidden">
        <div className="h-full bg-tg-button rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-tg-hint whitespace-nowrap">{done}/{total} · {pct}%</span>
    </div>
  );
}

/** Строка одной подзадачи */
function SubtaskRow({ subtask, projectId, onToggle }) {
  const isDone    = subtask.status === 'done';
  const isSkipped = subtask.status === 'skipped';
  const icon = isDone ? '✅' : isSkipped ? '⏭' : '⬜';

  return (
    <button
      className="flex items-center gap-2 w-full text-left py-0.5"
      onClick={() => onToggle(projectId, subtask.id, isDone ? 'pending' : 'done')}
    >
      <span className="text-base leading-none">{icon}</span>
      <span className={`text-sm ${isDone || isSkipped ? 'line-through text-tg-hint' : 'text-tg-text'}`}>
        {subtask.title}
      </span>
    </button>
  );
}

/** Карточка одного проекта с редактированием и удалением */
function ProjectCard({ project, onSubtaskToggle, onDeleted, onUpdated }) {
  const [expanded, setExpanded] = useState(false);
  const [editing,  setEditing]  = useState(false);
  const [editTitle, setEditTitle]    = useState(project.title);
  const [editDeadline, setEditDeadline] = useState(project.deadline || '');
  const [saving, setSaving]     = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);

  const done  = project.subtasks.filter((s) => s.status === 'done').length;
  const total = project.subtasks.length;

  const deadlineStr = project.deadline
    ? new Date(project.deadline + 'T00:00:00').toLocaleDateString('ru-RU', { day: '2-digit', month: 'long' })
    : null;

  const handleSaveEdit = async () => {
    if (!editTitle.trim()) return;
    setSaving(true);
    try {
      await updateProject(project.id, {
        title:    editTitle.trim(),
        deadline: editDeadline || null,
      });
      onUpdated();
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDel) { setConfirmDel(true); return; }
    setSaving(true);
    try {
      await deleteProject(project.id);
      onDeleted();
    } finally {
      setSaving(false);
      setConfirmDel(false);
    }
  };

  const handleComplete = async () => {
    setSaving(true);
    try {
      await updateProject(project.id, { status: 'completed' });
      onDeleted(); // убрать из списка активных
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="bg-tg-secondary rounded-xl p-4 mb-3">
        <input
          className="w-full bg-tg-bg border border-tg-hint/30 rounded-lg px-3 py-2 text-sm text-tg-text mb-2 outline-none focus:border-tg-button"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          placeholder="Название проекта"
        />
        <input
          type="date"
          className="w-full bg-tg-bg border border-tg-hint/30 rounded-lg px-3 py-2 text-sm text-tg-text mb-3 outline-none focus:border-tg-button"
          value={editDeadline}
          onChange={(e) => setEditDeadline(e.target.value)}
        />
        <div className="flex gap-2">
          <button
            onClick={handleSaveEdit}
            disabled={saving}
            className="flex-1 py-2 rounded-lg bg-tg-button text-white text-sm font-medium disabled:opacity-50"
          >
            Сохранить
          </button>
          <button
            onClick={() => setEditing(false)}
            className="px-4 py-2 rounded-lg border border-tg-hint/30 text-tg-hint text-sm"
          >
            Отмена
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-tg-secondary rounded-xl p-4 mb-3 ${saving ? 'opacity-60' : ''}`}>
      {/* Заголовок */}
      <div className="flex items-start gap-2">
        <button className="flex-1 text-left" onClick={() => setExpanded((v) => !v)}>
          <div className="flex justify-between items-start gap-2">
            <span className="font-medium text-tg-text">{project.title}</span>
            <span className="text-tg-hint text-sm mt-0.5">{expanded ? '▲' : '▼'}</span>
          </div>
          {deadlineStr && <p className="text-xs text-tg-hint mt-0.5">📅 до {deadlineStr}</p>}
          <ProgressBar done={done} total={total} />
        </button>

        {/* Кнопки управления */}
        <div className="flex flex-col gap-1 shrink-0 ml-1">
          <button
            onClick={() => setEditing(true)}
            className="text-tg-hint/60 hover:text-tg-button text-sm px-1"
            title="Редактировать"
          >✏️</button>
          <button
            onClick={handleDelete}
            className={`text-sm px-1 ${confirmDel ? 'text-red-500 font-bold' : 'text-tg-hint/60 hover:text-red-400'}`}
            title={confirmDel ? 'Нажми ещё раз' : 'Удалить'}
          >{confirmDel ? '⚠️' : '🗑'}</button>
        </div>
      </div>

      {/* Подзадачи */}
      {expanded && (
        <div className="mt-3 space-y-1.5 border-t border-tg-hint/10 pt-2">
          {project.subtasks.length === 0 && (
            <p className="text-sm text-tg-hint">Подзадач нет</p>
          )}
          {project.subtasks.map((sub) => (
            <SubtaskRow key={sub.id} subtask={sub} projectId={project.id} onToggle={onSubtaskToggle} />
          ))}

          {done === total && total > 0 && (
            <button
              onClick={handleComplete}
              className="mt-2 w-full py-1.5 rounded-lg bg-green-500/20 text-green-600 text-sm font-medium"
            >
              ✅ Завершить проект
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Форма создания проекта */
function NewProjectForm({ onCreated, onCancel }) {
  const [title,         setTitle]         = useState('');
  const [deadline,      setDeadline]      = useState('');
  const [subtitleInput, setSubtitleInput] = useState('');
  const [subtasks,      setSubtasks]      = useState([]);
  const [saving,        setSaving]        = useState(false);
  const [error,         setError]         = useState('');

  const addSubtask = () => {
    const t = subtitleInput.trim();
    if (!t) return;
    setSubtasks((prev) => [...prev, t]);
    setSubtitleInput('');
  };

  const handleSave = async () => {
    if (!title.trim()) { setError('Введи название проекта'); return; }
    setSaving(true);
    setError('');
    try {
      const project = await createProject({ title: title.trim(), deadline: deadline || null });
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
        value={deadline}
        onChange={(e) => setDeadline(e.target.value)}
      />

      {subtasks.length > 0 && (
        <ul className="mb-2 space-y-1">
          {subtasks.map((s, i) => (
            <li key={i} className="text-sm text-tg-text flex items-center gap-1">
              <span className="text-tg-hint">•</span> {s}
              <button
                onClick={() => setSubtasks((p) => p.filter((_, j) => j !== i))}
                className="ml-auto text-tg-hint/50 hover:text-red-400 text-xs"
              >×</button>
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
        <button onClick={addSubtask} className="px-3 py-2 rounded-lg bg-tg-button/20 text-tg-button text-sm">
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
        <button onClick={onCancel} className="px-4 py-2 rounded-lg border border-tg-hint/30 text-tg-hint text-sm">
          Отмена
        </button>
      </div>
    </div>
  );
}

/** Секция незавершённых задач (статус partial) */
function PartialTasksSection() {
  const [tasks,   setTasks]   = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPartialTasks()
      .then(setTasks)
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading || tasks.length === 0) return null;

  return (
    <div className="bg-tg-secondary rounded-xl p-4 mb-4">
      <p className="text-sm font-medium text-tg-text mb-2">🔶 Незавершённые задачи</p>
      <p className="text-xs text-tg-hint mb-3">Задачи, отмеченные как частично выполненные — требуют внимания</p>
      <div className="space-y-2">
        {tasks.map((t) => (
          <div key={t.id} className="flex items-center gap-2 text-sm">
            <span className="text-base">🔶</span>
            <div className="flex-1 min-w-0">
              <p className="text-tg-text truncate">{t.title}</p>
              {t.scheduled_at && (
                <p className="text-xs text-tg-hint">
                  {new Date(t.scheduled_at.endsWith('Z') ? t.scheduled_at : t.scheduled_at + 'Z')
                    .toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Главная страница проектов */
export default function ProjectsPage() {
  const [projects,  setProjects]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showForm,  setShowForm]  = useState(false);
  const [error,     setError]     = useState('');

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

  useEffect(() => { loadProjects(); }, [loadProjects]);

  const handleSubtaskToggle = async (projectId, subtaskId, newStatus) => {
    try {
      await updateSubtaskStatus(projectId, subtaskId, newStatus);
      setProjects((prev) =>
        prev.map((p) =>
          p.id !== projectId ? p : {
            ...p,
            subtasks: p.subtasks.map((s) =>
              s.id === subtaskId ? { ...s, status: newStatus } : s
            ),
          }
        )
      );
    } catch (_) {}
  };

  return (
    <div className="p-4 pb-6 overflow-y-auto">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-lg font-semibold text-tg-text">Проекты</h1>
        {!showForm && (
          <button onClick={() => setShowForm(true)} className="text-tg-button text-sm font-medium">
            ＋ Новый
          </button>
        )}
      </div>

      {showForm && (
        <NewProjectForm onCreated={() => { setShowForm(false); loadProjects(); }} onCancel={() => setShowForm(false)} />
      )}

      {/* Незавершённые задачи из дневника */}
      <PartialTasksSection />

      {loading && <p className="text-center text-tg-hint py-8">Загрузка...</p>}
      {!loading && error && <p className="text-center text-red-500 py-8">{error}</p>}

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

      {!loading && projects.map((p) => (
        <ProjectCard
          key={p.id}
          project={p}
          onSubtaskToggle={handleSubtaskToggle}
          onDeleted={loadProjects}
          onUpdated={loadProjects}
        />
      ))}
    </div>
  );
}
