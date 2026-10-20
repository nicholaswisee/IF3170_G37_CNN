import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readLimitsFixture } from '../testing/fixtures'
import type { Problem } from '../types/experiment'
import { ToastApiContext } from '../ui/toastContext'
import { SetupPanel } from './SetupPanel'

test('Save run is off by default', () => {
  const problem: Problem = { packages: [], trucks: [] }
  const markup = renderToStaticMarkup(createElement(ToastApiContext.Provider, {
    value: { show: () => 0, update: () => {}, dismiss: () => {} },
  }, createElement(SetupPanel, {
    open: true, problem, isExampleProblem: false, configName: null, viewingRun: false,
    limits: readLimitsFixture(), limitsError: null, running: false,
    onRetryLimits: () => {}, onEditProblem: () => {}, onOpenConfigs: () => {},
    onPreviewProblem: () => {}, onRun: () => {},
  })))
  const saveRun = markup.match(/<input id="opt-persist"[^>]*>/)?.[0]
  assert.ok(saveRun)
  assert.doesNotMatch(saveRun, /\schecked(?:=|\s|>)/)
})
