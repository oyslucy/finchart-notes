import { createBrowserRouter } from 'react-router'

import DesignPage from '../pages/DesignPage.tsx'
import HomePage from '../pages/HomePage.tsx'

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/design', element: <DesignPage /> },
])
