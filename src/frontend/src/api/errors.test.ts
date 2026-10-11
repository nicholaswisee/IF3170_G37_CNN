import assert from 'node:assert/strict'
import test from 'node:test'
import { formatApiError } from './errors'

test('formats FastAPI validation detail arrays into readable field errors', () => {
  assert.equal(formatApiError(422, [
    { loc: ['body', 'parameters', 'generations'], msg: 'Input should be greater than or equal to 1' },
    { loc: ['body', 'seed'], msg: 'Input should be a valid integer' },
  ]), 'parameters.generations: Input should be greater than or equal to 1; seed: Input should be a valid integer')
})

test('formats string 422 detail and preserves unexpected status errors', () => {
  assert.equal(formatApiError(422, 'Invalid configuration'), 'Invalid configuration')
  assert.equal(formatApiError(500, null), 'Request failed with status 500')
})
