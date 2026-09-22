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
      // Fuera del árbol del proyecto: el directorio por defecto (./coverage) quedó en manos
      // de root tras ejecutar el contenedor como superusuario, y vitest lo limpia al
      // arrancar, de modo que la medición fallaba con EACCES antes de empezar.
      reportsDirectory: '/tmp/vitest-coverage',
      provider: 'v8',
      reporter: ['text', 'html', 'json', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/**/*.d.ts',
        'src/app/**',
        'src/components/ui/**',   // shadcn-generated UI primitives
        'src/lib/config.ts',      // env config, always mocked in tests
        'src/lib/socket.ts',      // Phoenix socket singleton, always mocked
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
