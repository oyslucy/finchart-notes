import { createBrowserRouter } from 'react-router'

import AppLayout from '../pages/AppLayout.tsx'
import BoardPage from '../pages/BoardPage.tsx'
import CardDetailPage from '../pages/CardDetailPage.tsx'
import DesignPage from '../pages/DesignPage.tsx'
import HomePage from '../pages/HomePage.tsx'
import LoginPage from '../pages/LoginPage.tsx'

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
    ],
  },
])
