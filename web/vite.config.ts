import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    // The app reads ../contract/fixture.json, which sits outside this folder.
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'node',
  },
})
