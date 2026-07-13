import { createApp } from 'vue'
import ElementPlus from 'element-plus'
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

app.mount('#app')
