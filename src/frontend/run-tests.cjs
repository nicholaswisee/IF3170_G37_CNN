const { mkdtempSync, readdirSync, rmSync, statSync, writeFileSync } = require('node:fs')
const { join, relative } = require('node:path')
const { spawnSync } = require('node:child_process')

// Every *.test.ts(x) under src runs with node:test after a CommonJS compile.
function findTests(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    if (statSync(path).isDirectory()) return findTests(path)
    return /\.test\.tsx?$/.test(name) ? [path] : []
  })
}

const tests = findTests(join(process.cwd(), 'src')).map((path) => relative(process.cwd(), path))
const output = mkdtempSync(join(process.cwd(), '.test-build-'))
try {
  const compilation = spawnSync(process.execPath, [
    require.resolve('typescript/bin/tsc'),
    '--module', 'commonjs', '--moduleResolution', 'node', '--target', 'ES2022', '--jsx', 'react-jsx',
    '--esModuleInterop', '--skipLibCheck', '--types', 'node', '--rootDir', 'src', '--outDir', output,
    ...tests,
  ], { stdio: 'inherit' })
  if (compilation.error) throw compilation.error
  process.exitCode = compilation.status ?? 1
  if (compilation.status === 0) {
    writeFileSync(join(output, 'package.json'), JSON.stringify({ type: 'commonjs' }))
    const compiled = tests.map((path) => join(output, relative('src', path)).replace(/\.tsx?$/, '.js'))
    const run = spawnSync(process.execPath, ['--test', ...compiled], { stdio: 'inherit' })
    if (run.error) throw run.error
    process.exitCode = run.status ?? 1
  }
} finally {
  rmSync(output, { recursive: true, force: true })
}
