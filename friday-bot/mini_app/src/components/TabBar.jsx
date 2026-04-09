/** Нижний таббар навигации Mini App. */

const TABS = [
  { id: 'schedule', label: 'Расписание', icon: '📅' },
  { id: 'stats',    label: 'Статистика', icon: '📊' },
  { id: 'projects', label: 'Проекты',    icon: '📁' },
  { id: 'settings', label: 'Настройки',  icon: '⚙️' },
];

export default function TabBar({ activeTab, onTabChange }) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-tg-secondary border-t border-tg-hint/20">
      <div className="flex justify-around items-center h-14 max-w-lg mx-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex flex-col items-center justify-center flex-1 h-full transition-colors
              ${activeTab === tab.id ? 'text-tg-button' : 'text-tg-hint'}`}
          >
            <span className="text-lg leading-none">{tab.icon}</span>
            <span className="text-[10px] mt-0.5">{tab.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
