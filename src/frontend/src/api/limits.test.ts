import assert from 'node:assert/strict'
import test from 'node:test'
import type { NumericRange, Problem } from '../types/experiment'
import { readLimitsFixture } from '../testing/fixtures'
import { checkNumber, checkProblemLimits, describeRange, highestValue, isFixed, lowestValue, totalTruckVolume } from './limits'

const open: NumericRange = { integer: false, nullable: false, minimum: null, exclusive_minimum: null, maximum: null, exclusive_maximum: null, default: null }
const limits = readLimitsFixture()

test('describes ranges in plain words for every bound combination', () => {
  assert.equal(describeRange({ ...open, integer: true, exclusive_minimum: 0, maximum: 2000 }), '1 to 2000')
  assert.equal(describeRange({ ...open, integer: true, minimum: 0 }), '0 or more')
  assert.equal(describeRange({ ...open, integer: true, maximum: 5 }), 'Up to 5')
  assert.equal(describeRange({ ...open, exclusive_minimum: 0, exclusive_maximum: 1 }), 'Above 0 and below 1')
  assert.equal(describeRange({ ...open, exclusive_minimum: 0 }), 'Above 0')
  assert.equal(describeRange({ ...open, minimum: 0, maximum: 1 }), '0 to 1')
  assert.equal(describeRange(open), 'Any number')
})

test('stepper bounds respect exclusive limits using the step size', () => {
  const alpha = { ...open, exclusive_minimum: 0, exclusive_maximum: 1 }
  assert.equal(lowestValue(alpha, 0.005), 0.005)
  assert.equal(highestValue(alpha, 0.005), 0.995)
  assert.equal(lowestValue({ ...open, integer: true, exclusive_minimum: 0 }, 1), 1)
  assert.equal(highestValue({ ...open, integer: true, maximum: 20 }, 1), 20)
  assert.equal(isFixed({ ...open, integer: true, minimum: 1, maximum: 1 }), true)
  assert.equal(isFixed({ ...open, integer: true, minimum: 1, maximum: 2 }), false)
})

test('checks numbers against inclusive and exclusive bounds', () => {
  const range = { ...open, integer: true, exclusive_minimum: 0, maximum: 50 }
  assert.equal(checkNumber('Candidates', 50, range), null)
  assert.equal(checkNumber('Candidates', 0, range), 'Candidates must be 1 to 50')
  assert.equal(checkNumber('Candidates', 51, range), 'Candidates must be 1 to 50')
  assert.equal(checkNumber('Candidates', 2.5, range), 'Candidates must be a whole number')
  assert.equal(checkNumber('Candidates', null, range), 'Candidates is required')
  assert.equal(checkNumber('Temperature', null, { ...open, nullable: true, exclusive_minimum: 0 }), null)
  assert.equal(checkNumber('Alpha', 1, { ...open, exclusive_minimum: 0, exclusive_maximum: 1 }), 'Alpha must be above 0 and below 1')
  assert.equal(checkNumber('Alpha', Number.NaN, open), 'Alpha must be a number')
})

test('checks problem-wide limits that single fields cannot see', () => {
  const truck = { id: 'T', width: 10, length: 10, height: 10, max_capacity: 1 }
  const small: Problem = { trucks: [truck], packages: [] }
  assert.equal(checkProblemLimits(small, limits), null)
  assert.equal(totalTruckVolume(small), 1000)
  const tooManyTrucks = { ...small, trucks: Array.from({ length: limits.problem.max_trucks + 1 }, (_, index) => ({ ...truck, id: `T${index}`, width: 1, length: 1, height: 1 })) }
  assert.match(checkProblemLimits(tooManyTrucks, limits) ?? '', /at most \d+ trucks/)
  const huge = { ...small, trucks: [{ ...truck, width: 100, length: 100, height: 100 }] }
  assert.match(checkProblemLimits(huge, limits) ?? '', /1000000 cells/)
  const longId = { ...small, trucks: [{ ...truck, id: 'x'.repeat(limits.problem.max_id_length + 1) }] }
  assert.match(checkProblemLimits(longId, limits) ?? '', /longer than/)
})
