import { createRouter, createWebHistory } from 'vue-router'

import DirectoriesPage from '@/pages/DirectoriesPage.vue'
import FileDetailPage from '@/pages/FileDetailPage.vue'
import FilesPage from '@/pages/FilesPage.vue'
import ScanPage from '@/pages/ScanPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/directories' },
    { path: '/directories', name: 'directories', component: DirectoriesPage },
    { path: '/directories/:id/files', name: 'files', component: FilesPage },
    {
      path: '/files/:id(\\d+)',
      name: 'file-detail',
      component: FileDetailPage,
      props: true,
    },
    { path: '/scan', name: 'scan', component: ScanPage },
  ],
})

export default router
