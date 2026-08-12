import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

// Vitest 配置 —— 纯逻辑单测（不挂载组件，无需 jsdom）
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
  resolve: {
    // 与 vite.config.ts 的 '@' alias 保持一致
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
