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
    { path: '/files/:id', name: 'file-detail', component: FileDetailPage },
    { path: '/scan', name: 'scan', component: ScanPage },
  ],
})

export default router
