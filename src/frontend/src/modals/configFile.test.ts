import assert from 'node:assert/strict'
import test from 'node:test'
import { isConfigSummary, isSavedConfig } from '../api/validation'
import { readLimitsFixture } from '../testing/fixtures'
import type { Problem } from '../types/experiment'
import { configFileName, configFileText, nameFromFileName, parseConfigFile } from './configFile'

const limitsFixture = readLimitsFixture()

const problem: Problem = {
  trucks: [{ id: 'T1', width: 4, length: 5, height: 3, max_capacity: 40 }],
  packages: [{ id: 'P1', width: 1, length: 2, height: 1, value: 7.5, weight: 2, is_fragile: true, eta: 1 }],
}

test('an exported file imports back to the same upload', () => {
  const text = configFileText('Small fleet', problem, 'Two boxes')
  assert.deepEqual(parseConfigFile(text, 'small-fleet.json', limitsFixture), {
    upload: { schema_version: 1, name: 'Small fleet', description: 'Two boxes', problem },
    error: null,
  })
})

test('a bare problem takes its name from the file name', () => {
  const parsed = parseConfigFile(JSON.stringify(problem), 'my_fleet-v2.json', limitsFixture)
  assert.equal(parsed.error, null)
  assert.equal(parsed.upload?.name, 'my fleet v2')
  assert.equal(parsed.upload?.description, '')
  assert.deepEqual(parsed.upload?.problem, problem)
})

test('a saved config from the API imports without its server fields', () => {
  const saved = { id: 'abc', builtin: false, created_at: '2026-01-01T00:00:00Z', name: '  Saved  ', description: 'x', problem }
  const parsed = parseConfigFile(JSON.stringify(saved), 'saved.json', limitsFixture)
  assert.deepEqual(parsed.upload, { schema_version: 1, name: 'Saved', description: 'x', problem })
})

test('a blank name falls back to the file name', () => {
  const parsed = parseConfigFile(JSON.stringify({ name: '   ', problem }), 'warehouse.json', limitsFixture)
  assert.equal(parsed.upload?.name, 'warehouse')
})

test('rejects text that is not JSON or not a configuration', () => {
  for (const [text, message] of [
    ['{trucks: []', 'not valid JSON'],
    ['[]', 'JSON object'],
    ['{"trucks": []}', 'trucks list and a packages list'],
    ['{"problem": {"trucks": {}, "packages": []}}', 'trucks list and a packages list'],
    [JSON.stringify({ schema_version: 2, name: 'x', problem }), 'Only format 1'],
  ]) {
    const parsed = parseConfigFile(text, 'bad.json', limitsFixture)
    assert.equal(parsed.upload, null)
    assert.match(parsed.error ?? '', new RegExp(message))
  }
})

test('applies the backend problem limits before uploading', () => {
  const trucks = Array.from({ length: limitsFixture.problem.max_trucks + 1 }, (_, index) => ({ ...problem.trucks[0], id: `T${index}` }))
  const parsed = parseConfigFile(JSON.stringify({ ...problem, trucks }), 'big.json', limitsFixture)
  assert.match(parsed.error ?? '', /at most/)
  assert.equal(parseConfigFile(JSON.stringify({ ...problem, trucks }), 'big.json', null).error, null, 'limits are skipped until they load')
})

test('file names are plain slugs', () => {
  assert.equal(configFileName('Tight capacity (v2)'), 'tight-capacity-v2.json')
  assert.equal(configFileName('***'), 'configuration.json')
  assert.equal(nameFromFileName('.json'), 'Imported configuration')
})

test('config responses are checked before use', () => {
  const saved = { id: 'a', name: 'n', description: '', builtin: true, created_at: null, problem }
  assert.ok(isSavedConfig(saved))
  assert.ok(!isSavedConfig({ ...saved, problem: { trucks: [], packages: [] } }))
  assert.ok(isConfigSummary({ ...saved, problem: undefined, truck_count: 1, package_count: 1 }))
  assert.ok(!isConfigSummary({ ...saved, truck_count: '1', package_count: 1 }))
})
