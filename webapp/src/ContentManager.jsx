import { useEffect, useMemo, useState } from 'react'
import {
  listContent,
  createContent,
  updateContent,
  deleteContent,
  reparentContent,
} from './telegram.js'

const EMPTY_FORM = {
  title: '',
  body: '',
  image_url: '',
  link_url: '',
  code: '',
  is_premium: false,
  unlock_price: '',
}

// Builds a { parentId|null: [items] } map so the tree can be rendered by
// recursively walking from the top (parent_id === null) down — same
// "inferred from whether children exist" model as bot/content_nav.py.
function groupByParent(items) {
  const map = new Map()
  for (const item of items) {
    const key = item.parent_id ?? null
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  return map
}

function ItemForm({ initial, onCancel, onSubmit, submitLabel, showCode }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const setChecked = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.checked }))

  const submit = async () => {
    if (!form.title.trim()) {
      setError('Title is required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSubmit(form)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="cm-form">
      <input
        className="cm-input"
        placeholder="Title"
        value={form.title}
        onChange={set('title')}
      />
      <textarea
        className="cm-textarea"
        placeholder="Body text"
        value={form.body}
        onChange={set('body')}
      />
      <input
        className="cm-input"
        placeholder="Image URL (optional)"
        value={form.image_url}
        onChange={set('image_url')}
      />
      <input
        className="cm-input"
        placeholder="Link URL (optional)"
        value={form.link_url}
        onChange={set('link_url')}
      />
      {showCode && (
        <input
          className="cm-input"
          placeholder="Shortcut code (optional, e.g. 101 or buy)"
          value={form.code}
          onChange={set('code')}
        />
      )}
      <label className="cm-check">
        <input type="checkbox" checked={!!form.is_premium} onChange={setChecked('is_premium')} />
        🔒 Premium — needs an active subscription to view
      </label>
      {form.is_premium && (
        <input
          className="cm-input"
          type="number"
          min="0"
          placeholder="Single-purchase price in Toman (blank = use bot default)"
          value={form.unlock_price ?? ''}
          onChange={set('unlock_price')}
        />
      )}
      {error && <div className="cm-error">{error}</div>}
      <div className="cm-form-actions">
        <button className="cm-button cm-button-primary" onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : submitLabel}
        </button>
        <button className="cm-button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function GroupPicker({ item, items, onCancel, onSubmit }) {
  const [target, setTarget] = useState(item.parent_id == null ? 'top' : String(item.parent_id))
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const options = items.filter((i) => i.id !== item.id)

  const submit = async () => {
    setSaving(true)
    setError('')
    try {
      await onSubmit(target === 'top' ? null : Number(target))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="cm-form">
      <select className="cm-input" value={target} onChange={(e) => setTarget(e.target.value)}>
        <option value="top">📁 Top Level (no category)</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.title}
          </option>
        ))}
      </select>
      {error && <div className="cm-error">{error}</div>}
      <div className="cm-form-actions">
        <button className="cm-button cm-button-primary" onClick={submit} disabled={saving}>
          {saving ? 'Moving…' : 'Move here'}
        </button>
        <button className="cm-button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function TreeNode({ item, depth, byParent, activePanel, setActivePanel, items, refresh }) {
  const children = byParent.get(item.id) || []
  const isEditing = activePanel?.type === 'edit' && activePanel.id === item.id
  const isGrouping = activePanel?.type === 'group' && activePanel.id === item.id

  const del = async () => {
    if (!window.confirm(`Delete "${item.title}"? This cannot be undone.`)) return
    try {
      await deleteContent(item.id)
      await refresh()
    } catch (err) {
      window.alert(err.message)
    }
  }

  return (
    <div className="cm-node" style={{ marginLeft: depth * 18 }}>
      <div className="cm-node-row">
        <span className="cm-node-title">
          {children.length > 0 ? '📁' : '📌'} {item.is_premium ? '🔒 ' : ''}{item.title}
        </span>
        {item.code && <span className="cm-code-badge">{item.code}</span>}
        {item.is_premium && item.unlock_price ? (
          <span className="cm-code-badge">{Number(item.unlock_price).toLocaleString()} T</span>
        ) : null}
        <span className="cm-node-actions">
          <button
            className="cm-icon-button"
            title="Edit"
            onClick={() => setActivePanel({ type: 'edit', id: item.id })}
          >
            ✏️
          </button>
          <button
            className="cm-icon-button"
            title="Move to a different category"
            onClick={() => setActivePanel({ type: 'group', id: item.id })}
          >
            🔀
          </button>
          <button className="cm-icon-button" title="Delete" onClick={del}>
            🗑
          </button>
        </span>
      </div>

      {isEditing && (
        <ItemForm
          initial={{
            title: item.title,
            body: item.body || '',
            image_url: item.image_url || '',
            link_url: item.link_url || '',
            code: item.code || '',
            is_premium: !!item.is_premium,
            unlock_price: item.unlock_price ?? '',
          }}
          submitLabel="Save"
          showCode={false}
          onCancel={() => setActivePanel(null)}
          onSubmit={async (form) => {
            await updateContent(item.id, {
              title: form.title,
              body: form.body,
              image_url: form.image_url || null,
              link_url: form.link_url || null,
              is_premium: !!form.is_premium,
              unlock_price: form.is_premium && form.unlock_price !== '' ? Number(form.unlock_price) : null,
            })
            setActivePanel(null)
            await refresh()
          }}
        />
      )}

      {isGrouping && (
        <GroupPicker
          item={item}
          items={items}
          onCancel={() => setActivePanel(null)}
          onSubmit={async (parentId) => {
            await reparentContent(item.id, parentId)
            setActivePanel(null)
            await refresh()
          }}
        />
      )}

      {children.map((child) => (
        <TreeNode
          key={child.id}
          item={child}
          depth={depth + 1}
          byParent={byParent}
          activePanel={activePanel}
          setActivePanel={setActivePanel}
          items={items}
          refresh={refresh}
        />
      ))}
    </div>
  )
}

export default function ContentManager({ onClose }) {
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('Loading…')
  const [activePanel, setActivePanel] = useState(null) // null | {type:'edit'|'group', id} | {type:'add'}

  const refresh = async () => {
    try {
      const data = await listContent()
      setItems(data)
      setStatus('')
    } catch (err) {
      setStatus(`Failed to load: ${err.message}`)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const byParent = useMemo(() => groupByParent(items), [items])
  const roots = byParent.get(null) || []

  return (
    <div className="cm-overlay">
      <div className="cm-panel">
        <div className="cm-header">
          <div className="cm-title">Manage Content</div>
          <button className="cm-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="cm-toolbar">
          <button
            className="cm-button cm-button-primary"
            onClick={() => setActivePanel({ type: 'add' })}
          >
            ➕ Add Item
          </button>
        </div>

        {activePanel?.type === 'add' && (
          <ItemForm
            initial={EMPTY_FORM}
            submitLabel="Add"
            showCode
            onCancel={() => setActivePanel(null)}
            onSubmit={async (form) => {
              await createContent({
                title: form.title,
                body: form.body,
                image_url: form.image_url || null,
                link_url: form.link_url || null,
                code: form.code || null,
                is_premium: !!form.is_premium,
                unlock_price:
                  form.is_premium && form.unlock_price !== '' ? Number(form.unlock_price) : null,
              })
              setActivePanel(null)
              await refresh()
            }}
          />
        )}

        <div className="cm-body">
          {status && <div className="cm-status">{status}</div>}
          {!status && roots.length === 0 && (
            <div className="cm-status">No content items yet — add one above.</div>
          )}
          {roots.map((item) => (
            <TreeNode
              key={item.id}
              item={item}
              depth={0}
              byParent={byParent}
              activePanel={activePanel}
              setActivePanel={setActivePanel}
              items={items}
              refresh={refresh}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
