import { useState } from 'react'

// Editor for a send_message/message node's `messages` list (bot/flow_engine.py
// interprets this exact shape — see its module docstring). Kept intentionally
// simple: a media field only ever holds a plain URL from this side (Telegram
// fetches it directly — see flow_engine.py's _send_message_block comment), so
// an owner who wants to attach something they *upload* from their phone still
// needs the chat-based "Define Command" wizard for that one step; this modal
// covers everything else (text, buttons, multiple messages) identically for
// both authoring surfaces.

const EMPTY_BLOCK = { text: '', media_type: '', media_url: '', buttons: [] }
const EMPTY_BUTTON = { type: 'url', text: '', url: '', command: '' }

function ButtonRow({ button, onRemove }) {
  const detail = button.type === 'url' ? button.url : button.command
  return (
    <div className="cm-node-row">
      <span className="cm-node-title">
        {button.type === 'url' ? '🔗' : '↪️'} {button.text}
      </span>
      <span className="cm-code-badge">{detail}</span>
      <span className="cm-node-actions">
        <button type="button" className="cm-icon-button" title="Remove" onClick={onRemove}>
          🗑
        </button>
      </span>
    </div>
  )
}

function AddButtonForm({ onAdd, onCancel }) {
  const [form, setForm] = useState(EMPTY_BUTTON)
  const [error, setError] = useState('')

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = () => {
    if (!form.text.trim()) {
      setError('Button text is required.')
      return
    }
    if (form.type === 'url' && !/^https?:\/\//.test(form.url.trim())) {
      setError('Button URL must start with http:// or https://.')
      return
    }
    if (form.type === 'jump' && !form.command.trim().startsWith('/')) {
      setError('Target command must start with /.')
      return
    }
    onAdd({
      type: form.type,
      text: form.text.trim(),
      ...(form.type === 'url' ? { url: form.url.trim() } : { command: form.command.trim() }),
    })
  }

  return (
    <div className="cm-form">
      <select className="cm-input" value={form.type} onChange={set('type')}>
        <option value="url">🔗 Link button</option>
        <option value="jump">↪️ Jump-to-command button</option>
      </select>
      <input className="cm-input" placeholder="Button text" value={form.text} onChange={set('text')} />
      {form.type === 'url' ? (
        <input className="cm-input" placeholder="https://…" value={form.url} onChange={set('url')} />
      ) : (
        <input
          className="cm-input"
          placeholder="/target_command"
          value={form.command}
          onChange={set('command')}
        />
      )}
      {error && <div className="cm-error">{error}</div>}
      <div className="cm-form-actions">
        <button type="button" className="cm-button cm-button-primary" onClick={submit}>
          Add button
        </button>
        <button type="button" className="cm-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function BlockEditor({ block, index, onChange, onRemove, canRemove }) {
  const [addingButton, setAddingButton] = useState(false)
  const buttons = block.buttons || []

  return (
    <div className="cm-node">
      <div className="cm-node-row">
        <span className="cm-node-title">Message {index + 1}</span>
        {canRemove && (
          <span className="cm-node-actions">
            <button type="button" className="cm-icon-button" title="Remove this message" onClick={onRemove}>
              🗑
            </button>
          </span>
        )}
      </div>
      <div className="cm-form">
        <textarea
          className="cm-textarea"
          placeholder="Message text…"
          value={block.text || ''}
          onChange={(e) => onChange({ ...block, text: e.target.value })}
        />
        <select
          className="cm-input"
          value={block.media_type || ''}
          onChange={(e) => onChange({ ...block, media_type: e.target.value || undefined })}
        >
          <option value="">No attachment</option>
          <option value="photo">📷 Photo</option>
          <option value="video">🎥 Video</option>
          <option value="document">📄 Document</option>
        </select>
        {block.media_type && (
          <input
            className="cm-input"
            placeholder="Image/video/file URL (or paste a file_id from the chat wizard)"
            value={block.media_url || block.media_file_id || ''}
            onChange={(e) => onChange({ ...block, media_url: e.target.value, media_file_id: undefined })}
          />
        )}

        {buttons.map((b, i) => (
          <ButtonRow
            key={i}
            button={b}
            onRemove={() => onChange({ ...block, buttons: buttons.filter((_, j) => j !== i) })}
          />
        ))}

        {addingButton ? (
          <AddButtonForm
            onCancel={() => setAddingButton(false)}
            onAdd={(button) => {
              onChange({ ...block, buttons: [...buttons, button] })
              setAddingButton(false)
            }}
          />
        ) : (
          <button type="button" className="cm-button" onClick={() => setAddingButton(true)}>
            ➕ Add button
          </button>
        )}
      </div>
    </div>
  )
}

export default function MessageComposer({ initialMessages, onClose, onSave }) {
  const [blocks, setBlocks] = useState(
    initialMessages && initialMessages.length > 0 ? initialMessages : [EMPTY_BLOCK]
  )

  const updateBlock = (index, next) => setBlocks((bs) => bs.map((b, i) => (i === index ? next : b)))
  const removeBlock = (index) => setBlocks((bs) => bs.filter((_, i) => i !== index))
  const addBlock = () => setBlocks((bs) => [...bs, EMPTY_BLOCK])

  const save = () => onSave(blocks.filter((b) => (b.text || '').trim() || b.media_type))

  return (
    <div className="cm-overlay">
      <div className="cm-panel">
        <div className="cm-header">
          <div className="cm-title">Edit Message</div>
          <button type="button" className="cm-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="cm-body">
          {blocks.map((block, i) => (
            <BlockEditor
              key={i}
              block={block}
              index={i}
              canRemove={blocks.length > 1}
              onChange={(next) => updateBlock(i, next)}
              onRemove={() => removeBlock(i)}
            />
          ))}
          <button type="button" className="cm-button" onClick={addBlock}>
            ➕ Add another message
          </button>
        </div>

        <div className="cm-form-actions">
          <button type="button" className="cm-button cm-button-primary" onClick={save}>
            Save
          </button>
          <button type="button" className="cm-button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
