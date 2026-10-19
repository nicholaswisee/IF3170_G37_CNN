import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import test from 'node:test'

const sourceRoot = join(process.cwd(), 'src')

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx|css)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : []
  })
}

const files = sourceFiles(sourceRoot).map((path) => ({ path: relative(sourceRoot, path), text: readFileSync(path, 'utf8') }))

test('interface copy uses no middle dots, ellipses, or em dashes', () => {
  // Built from code points so this test file does not contain the characters itself.
  const forbidden = [0x00b7, 0x2026, 0x2014].map((code) => String.fromCodePoint(code))
  for (const { path, text } of files) {
    for (const character of forbidden) {
      assert.ok(!text.includes(character), `${path} contains U+${character.codePointAt(0)?.toString(16).toUpperCase().padStart(4, '0')}`)
    }
  }
})

test('source respects the repository guardrails', () => {
  const guarded = [['state', 'resolution'].join('_'), ['state', 'score', 'trig'].join('_'), ['#38', '6641'].join('')]
  for (const { path, text } of files) {
    for (const token of guarded) assert.ok(!text.toLowerCase().includes(token), `${path} contains a prohibited token`)
  }
})
