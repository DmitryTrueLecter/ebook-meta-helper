import { createRouter, createWebHistory } from 'vue-router'

import FileDetailPage from '@/pages/FileDetailPage.vue'
import HomePage from '@/pages/HomePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/files/:id(\\d+)',
      name: 'file-detail',
      component: FileDetailPage,
      props: true,
    },
  ],
})

export default router
