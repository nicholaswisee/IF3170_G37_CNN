import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { deleteConfig, getConfig, listConfigs, uploadConfig } from '../api/client'
import { formatWhole } from '../copy/format'
import type { ConfigSummary, SavedConfig } from '../types/config'
import type { Limits } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/toastContext'
import { configFileName, configFileText, parseConfigFile } from './configFile'

const UPLOADING = 'upload'
const savedAt = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' })

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function summaryOf(config: SavedConfig): ConfigSummary {
  const { problem, ...rest } = config
  return { ...rest, truck_count: problem.trucks.length, package_count: problem.packages.length }
}

function download(fileName: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

interface ConfigManagerProps {
  limits: Limits | null
  activeConfig: { id: string; name: string } | null
  /** Validates and shows the configuration. Closes this sheet on success. */
  onApply: (config: SavedConfig, verb: string) => Promise<void>
  onDeleted: (id: string) => void
  onClose: () => void
}

/** Popup for importing truck and package configurations as JSON, reloading saved ones, and deleting them. */
export function ConfigManager({ limits, activeConfig, onApply, onDeleted, onClose }: ConfigManagerProps) {
  const toast = useToast()
  const fileInput = useRef<HTMLInputElement>(null)
  const [configs, setConfigs] = useState<ConfigSummary[]>([])
  const [loading, setLoading] = useState(true)
  // ID of the row being loaded or deleted, or UPLOADING while a file is saved.
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  const fetchConfigs = useCallback((isActive: () => boolean) => listConfigs()
    .then((list) => {
      if (isActive()) setConfigs(list)
    }, (error: unknown) => {
      if (isActive()) toast.show(`Could not load configurations. ${messageOf(error)}`, 'error')
    })
    .finally(() => {
      if (isActive()) setLoading(false)
    }), [toast])

  // The active flag keeps a doubled development effect from announcing twice.
  useEffect(() => {
    let active = true
    void fetchConfigs(() => active)
    return () => {
      active = false
    }
  }, [fetchConfigs])

  const refreshConfigs = () => {
    setLoading(true)
    void fetchConfigs(() => true)
  }

  const importFile = async (file: File) => {
    if (busy) return
    if (limits && file.size > limits.max_request_bytes) {
      toast.show(`${file.name} is larger than the ${formatWhole(limits.max_request_bytes / 1024)} KB upload limit`, 'error')
      return
    }
    const parsed = parseConfigFile(await file.text(), file.name, limits)
    if (!parsed.upload) {
      toast.show(parsed.error, 'error')
      return
    }
    setBusy(UPLOADING)
    try {
      const saved = await uploadConfig(parsed.upload)
      setConfigs((list) => [...list.filter((item) => item.builtin), summaryOf(saved), ...list.filter((item) => !item.builtin)])
      await onApply(saved, 'Saved and loaded')
    } catch (error) {
      toast.show(`Could not save ${parsed.upload.name}. ${messageOf(error)}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  const load = async (summary: ConfigSummary) => {
    setBusy(summary.id)
    try {
      await onApply(await getConfig(summary.id), 'Loaded')
    } catch (error) {
      toast.show(`Could not load ${summary.name}. ${messageOf(error)}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  const exportConfig = async (summary: ConfigSummary) => {
    setBusy(summary.id)
    try {
      const config = await getConfig(summary.id)
      download(configFileName(config.name), configFileText(config.name, config.problem, config.description))
    } catch (error) {
      toast.show(`Could not download ${summary.name}. ${messageOf(error)}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  const remove = async (summary: ConfigSummary) => {
    setBusy(summary.id)
    try {
      await deleteConfig(summary.id)
      setConfigs((list) => list.filter((item) => item.id !== summary.id))
      onDeleted(summary.id)
      toast.show(`Deleted ${summary.name}`, 'success')
    } catch (error) {
      toast.show(`Could not delete ${summary.name}. ${messageOf(error)}`, 'error')
    } finally {
      setBusy(null)
      setConfirmId(null)
    }
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void importFile(file)
  }

  const refresh = (
    <button className="btn btn-plain btn-sm" type="button" disabled={loading} onClick={refreshConfigs}>
      {loading ? <span className="spinner" aria-hidden="true" /> : <Icon name="refresh" size={14} />}{loading ? 'Loading' : 'Refresh'}
    </button>
  )

  return (
    <Modal title="Configurations" onClose={onClose} headerExtra={refresh}>
      <div
        className={dragging ? 'dropzone dragging' : 'dropzone'}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <Icon name="upload" size={22} />
        <div className="dropzone-text">
          <b>Upload a JSON configuration</b>
          <small>Drop a file here or choose one. It is saved to the app and loaded right away.</small>
        </div>
        <button className="btn btn-primary btn-sm" type="button" disabled={busy !== null} onClick={() => fileInput.current?.click()}>
          {busy === UPLOADING ? <span className="spinner light" aria-hidden="true" /> : <Icon name="folder" size={14} />}
          {busy === UPLOADING ? 'Saving' : 'Choose file'}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".json,application/json"
          hidden
          onChange={(event) => {
            const file = event.currentTarget.files?.[0]
            event.currentTarget.value = ''
            if (file) void importFile(file)
          }}
        />
      </div>

      {configs.length === 0 ? (
        <div className="group empty-state"><p>{loading ? 'Loading configurations' : 'No configurations yet. Upload a JSON file to add one.'}</p></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Trucks</th><th>Packages</th><th>Saved</th><th><span className="visually-hidden">Actions</span></th></tr>
            </thead>
            <tbody>
              {configs.map((config) => {
                const showing = config.id === activeConfig?.id
                const rowBusy = busy === config.id
                return (
                  <tr key={config.id} aria-current={showing || undefined}>
                    <td className="config-name">
                      <b>{config.name}</b>
                      {config.builtin && <span className="tag inline">Built-in</span>}
                      {config.description && <small title={config.description}>{config.description}</small>}
                    </td>
                    <td>{config.truck_count}</td>
                    <td>{config.package_count}</td>
                    <td>{config.created_at ? savedAt.format(new Date(config.created_at)) : 'Ships with the app'}</td>
                    <td>
                      <span className="row-actions">
                        {confirmId === config.id ? (
                          <>
                            <button className="btn btn-danger btn-sm" type="button" disabled={rowBusy} onClick={() => void remove(config)}>
                              {rowBusy && <span className="spinner light" aria-hidden="true" />}Delete
                            </button>
                            <button className="btn btn-plain btn-sm" type="button" disabled={rowBusy} onClick={() => setConfirmId(null)}>Cancel</button>
                          </>
                        ) : (
                          <>
                            <button className="btn btn-tinted btn-sm" type="button" disabled={showing || busy !== null} onClick={() => void load(config)}>
                              {rowBusy && <span className="spinner" aria-hidden="true" />}{showing ? 'Showing' : 'Load'}
                            </button>
                            <button className="icon-btn small" type="button" aria-label={`Download ${config.name}`} title="Download as JSON" disabled={busy !== null} onClick={() => void exportConfig(config)}>
                              <Icon name="download" size={16} />
                            </button>
                            <button
                              className="icon-btn small"
                              type="button"
                              aria-label={`Delete ${config.name}`}
                              title={config.builtin ? 'Built-in configurations cannot be deleted' : 'Delete'}
                              disabled={config.builtin || busy !== null}
                              onClick={() => setConfirmId(config.id)}
                            >
                              <Icon name="trash" size={16} />
                            </button>
                          </>
                        )}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="caption">
        A file holds schema_version 1, a name, an optional description, and a problem with trucks and packages, the same shape the download button writes.
        A file with only trucks and packages also works and takes its name from the file.
        Uploaded configurations are kept in the backend data folder. On the free hosted backend they reset when the service restarts, while built-in ones always stay.
      </p>
    </Modal>
  )
}
