import { useState, useEffect } from 'react';
import { useTelegram } from './hooks/useTelegram';
import TabBar from './components/TabBar';
import SchedulePage from './pages/SchedulePage';
import StatsPage from './pages/StatsPage';
import ProjectsPage from './pages/ProjectsPage';
import SettingsPage from './pages/SettingsPage';

/** Маппинг вкладок на компоненты. */
const PAGES = {
  schedule: SchedulePage,
  stats: StatsPage,
  projects: ProjectsPage,
  settings: SettingsPage,
};

export default function App() {
  const { webApp } = useTelegram();
  const [activeTab, setActiveTab] = useState('schedule');

  // Deep link: открыть нужную вкладку через start_param
  useEffect(() => {
    const startParam = webApp?.initDataUnsafe?.start_param;
    if (startParam && PAGES[startParam]) {
      setActiveTab(startParam);
    }
  }, [webApp]);

  const Page = PAGES[activeTab];

  return (
    <div className="flex flex-col min-h-screen bg-tg-bg text-tg-text">
      {/* Контент страницы с отступом под таббар */}
      <main className="flex-1 pb-14">
        <Page />
      </main>

      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
