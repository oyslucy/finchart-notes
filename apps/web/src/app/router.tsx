import { createBrowserRouter } from 'react-router'

import AppLayout from '../pages/AppLayout.tsx'
import ArticlePage from '../pages/ArticlePage.tsx'
import BoardPage from '../pages/BoardPage.tsx'
import CardDetailPage from '../pages/CardDetailPage.tsx'
import DesignPage from '../pages/DesignPage.tsx'
import HomePage from '../pages/HomePage.tsx'
import LoginPage from '../pages/LoginPage.tsx'
import NewsPage from '../pages/NewsPage.tsx'
import SettingsPage from '../pages/SettingsPage.tsx'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/design', element: <DesignPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'boards/:boardId', element: <BoardPage /> },
      { path: 'boards/:boardId/cards/:cardId', element: <CardDetailPage /> },
      { path: 'news', element: <NewsPage /> },
      { path: 'news/:articleId', element: <ArticlePage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
])
