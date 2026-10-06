/** @type {import('@commitlint/types').UserConfig} */
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
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
        'db',
        'docker',
        'config',
        'ws',
        'ai',
      ],
    ],
    'subject-case': [0],
    'body-max-line-length': [0],
  },
};
