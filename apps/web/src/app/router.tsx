import { createBrowserRouter } from 'react-router'

import AppLayout from '../pages/AppLayout.tsx'
import BoardPage from '../pages/BoardPage.tsx'
import BoardsIndexPage from '../pages/BoardsIndexPage.tsx'
import DesignPage from '../pages/DesignPage.tsx'
import LoginPage from '../pages/LoginPage.tsx'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/design', element: <DesignPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <BoardsIndexPage /> },
      { path: 'boards/:boardId', element: <BoardPage /> },
    ],
  },
])
