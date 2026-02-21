import { rmSync } from 'node:fs'
import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import electron from 'vite-plugin-electron/simple'

import pkg from './package.json'

const desktopRoot = __dirname
const frontendRoot = path.resolve(desktopRoot, '../frontend')

if (process.cwd() !== frontendRoot) {
  process.chdir(frontendRoot)
}

export default defineConfig(({ command }) => {
  const isServe = command === 'serve'
  const isBuild = command === 'build'

  rmSync(path.resolve(desktopRoot, 'dist-electron'), { recursive: true, force: true })

  return {
    root: frontendRoot,
    plugins: [
      react(),
      electron({
        main: {
          entry: path.resolve(desktopRoot, 'electron/main/index.ts'),
          vite: {
            build: {
              sourcemap: isServe,
              minify: isBuild,
              outDir: path.resolve(desktopRoot, 'dist-electron/main'),
              rollupOptions: {
                external: Object.keys(pkg.dependencies ?? {}),
              },
            },
          },
        },
        preload: {
          input: path.resolve(desktopRoot, 'electron/preload/index.ts'),
          vite: {
            build: {
              sourcemap: isServe ? 'inline' : undefined,
              minify: isBuild,
              outDir: path.resolve(desktopRoot, 'dist-electron/preload'),
              rollupOptions: {
                external: Object.keys(pkg.dependencies ?? {}),
              },
            },
          },
        },
        renderer: {},
      }),
    ],
    resolve: {
      alias: {
        '@': path.resolve(frontendRoot, 'src'),
      },
    },
    css: {
      postcss: path.resolve(frontendRoot, 'postcss.config.js'),
    },
    build: {
      outDir: path.resolve(desktopRoot, 'dist'),
      emptyOutDir: true,
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: false,
      open: false,
    },
  }
})
