import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import pinia from './stores'
import './styles/index.scss'

const app = createApp(App)

// 全局注册 Element Plus（中文语言包）
app.use(ElementPlus, { locale: zhCn })
// 全局注册 Vue Router
app.use(router)
// 全局注册 Pinia 状态管理
app.use(pinia)

// 全局注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// ==================== 全局异常兜底 ====================
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue 全局错误]', err, `(组件: ${info})`)
  // 仅记录到控制台，不打断用户操作
}

// ==================== 网络状态检测 ====================
const showOfflineBanner = () => {
  document.body.style.setProperty('--offline-banner', '"当前网络已断开"')
}

window.addEventListener('offline', () => {
  console.warn('[网络] 连接断开')
  document.body.classList.add('is-offline')
})
window.addEventListener('online', () => {
  console.log('[网络] 已恢复连接')
  document.body.classList.remove('is-offline')
})

app.mount('#app')
