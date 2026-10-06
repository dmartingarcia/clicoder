import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      // Fuera del árbol: ./coverage quedó propiedad de root al ejecutar el contenedor y vitest fallaba con EACCES al limpiarlo.
      reportsDirectory: '/tmp/vitest-coverage',
      provider: 'v8',
      reporter: ['text', 'html', 'json', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/**/*.d.ts',
        'src/app/**',
        'src/components/ui/**',
        'src/lib/config.ts',
        'src/lib/socket.ts',
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
