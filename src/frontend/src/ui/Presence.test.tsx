import assert from 'node:assert/strict'
import test from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { Presence } from './Presence'

test('renders open children in a layout-neutral wrapper and nothing when closed', () => {
  assert.equal(renderToStaticMarkup(<Presence><p>Open</p></Presence>), '<div class="presence"><p>Open</p></div>')
  assert.equal(renderToStaticMarkup(<Presence>{false}</Presence>), '')
  assert.equal(renderToStaticMarkup(<Presence>{null}</Presence>), '')
})
