/** @type {import('@commitlint/types').UserConfig} */
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Tipos extra usados en este proyecto
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'refactor',
        'chore',
        'docs',
        'test',
        'style',
        'perf',
        'ci',
        'build',
        'revert',
        // proyecto
        'db',
        'docker',
        'config',
        'ws',
        'ai',
      ],
    ],
    // Permitir scope en español y sin capitalización forzada
    'subject-case': [0],
    // Sin límite de longitud de línea en el body
    'body-max-line-length': [0],
  },
};
