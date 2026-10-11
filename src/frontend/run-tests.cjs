const { mkdtempSync, writeFileSync, rmSync } = require('node:fs')
const { join } = require('node:path')
const { spawnSync } = require('node:child_process')

const output = mkdtempSync(join(process.cwd(), '.test-build-'))
try {
  const compilation = spawnSync(process.execPath, [
    require.resolve('typescript/bin/tsc'),
    '--module', 'commonjs', '--moduleResolution', 'node', '--target', 'ES2022',
    '--esModuleInterop', '--skipLibCheck', '--types', 'node', '--outDir', output,
    'src/api/validation.test.ts', 'src/api/errors.test.ts', 'src/stores/replayStore.test.ts',
  ], { stdio: 'inherit' })
  if (compilation.error) throw compilation.error
  process.exitCode = compilation.status ?? 1
  if (compilation.status === 0) {
    writeFileSync(join(output, 'package.json'), JSON.stringify({ type: 'commonjs' }))
    const tests = spawnSync(process.execPath, [
      '--test', join(output, 'api/validation.test.js'),
      join(output, 'api/errors.test.js'),
      join(output, 'stores/replayStore.test.js'),
    ], { stdio: 'inherit' })
    if (tests.error) throw tests.error
    process.exitCode = tests.status ?? 1
  }
} finally {
  rmSync(output, { recursive: true, force: true })
}
