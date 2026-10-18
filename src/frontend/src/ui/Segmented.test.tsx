import assert from 'node:assert/strict'
import test from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { Segmented } from './Segmented'

test('marks exactly the chosen option and mirrors the labels inside the glass lens', () => {
  const markup = renderToStaticMarkup(
    <Segmented label="Algorithm" options={[{ value: 'a', label: 'Hill Climbing' }, { value: 'b', label: 'Annealing' }]} value="b" onChange={() => {}} />,
  )
  assert.match(markup, /role="group" aria-label="Algorithm"/)
  assert.equal(markup.match(/aria-pressed="true"/g)?.length, 1)
  assert.match(markup, /aria-pressed="true"[^>]*>Annealing</)
  assert.match(markup, /class="seg-thumb" aria-hidden="true"/)
  assert.match(markup, /<span class="on">Annealing<\/span>/)
})
