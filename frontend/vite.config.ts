import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    tsconfigPaths(), // Handles @/* path alias from tsconfig
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // Code splitting for optimal loading
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': [
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-select',
            '@radix-ui/react-tabs',
          ],
          'flow-vendor': ['@xyflow/react', 'dagre'],
          'query-vendor': ['@tanstack/react-query'],
          'editor-vendor': ['@monaco-editor/react', '@tiptap/react'],
        },
      },
    },
  },

  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:5055',
        changeOrigin: true,
      },
    },
  },

  preview: {
    port: 3000,
    host: '0.0.0.0',
  },
});
