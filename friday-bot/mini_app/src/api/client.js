/**
 * HTTP-клиент для общения с бэкендом.
 * Передаёт initData для авторизации.
 */

const BASE_URL = '/api';

function getInitData() {
  return window.Telegram?.WebApp?.initData || '';
}

function getTelegramId() {
  return window.Telegram?.WebApp?.initDataUnsafe?.user?.id || null;
}

export async function apiRequest(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': getInitData(),
    'ngrok-skip-browser-warning': '1',
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/** Получить задачи на дату */
export function fetchTasks(date) {
  const telegramId = getTelegramId();
  return apiRequest(`/tasks?date=${date}&telegram_id=${telegramId}`);
}

/** Создать задачу */
export function createTask(task) {
  const telegramId = getTelegramId();
  return apiRequest(`/tasks?telegram_id=${telegramId}`, {
    method: 'POST',
    body: JSON.stringify(task),
  });
}

/** Обновить задачу */
export function updateTask(taskId, updates) {
  return apiRequest(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

/** Получить данные календаря для диапазона дат */
export function fetchCalendar(fromDate, toDate) {
  const telegramId = getTelegramId();
  return apiRequest(`/calendar?from=${fromDate}&to=${toDate}&telegram_id=${telegramId}`);
}

/** Получить список проектов */
export function fetchProjects(status = 'active') {
  const telegramId = getTelegramId();
  return apiRequest(`/projects?telegram_id=${telegramId}&status=${status}`);
}

/** Создать проект */
export function createProject(project) {
  const telegramId = getTelegramId();
  return apiRequest(`/projects?telegram_id=${telegramId}`, {
    method: 'POST',
    body: JSON.stringify(project),
  });
}

/** Получить подзадачи проекта */
export function fetchSubtasks(projectId) {
  const telegramId = getTelegramId();
  return apiRequest(`/projects/${projectId}/subtasks?telegram_id=${telegramId}`);
}

/** Добавить подзадачу к проекту */
export function createSubtask(projectId, subtask) {
  const telegramId = getTelegramId();
  return apiRequest(`/projects/${projectId}/subtasks?telegram_id=${telegramId}`, {
    method: 'POST',
    body: JSON.stringify(subtask),
  });
}

/** Обновить статус подзадачи */
export function updateSubtaskStatus(projectId, subtaskId, status) {
  const telegramId = getTelegramId();
  return apiRequest(`/projects/${projectId}/subtasks/${subtaskId}?telegram_id=${telegramId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}
