import { useRef, useState } from 'react'
import { BLOCK_DEFS } from './nodes.jsx'

const DECISION_THRESHOLD = 6 // px of movement before we decide drag vs scroll

// Pointer Events (not the HTML5 Drag-and-Drop API) so this works with touch —
// Telegram Mini Apps run mostly inside mobile webviews, where native
// `draggable`/dragstart/drop events never fire.
//
// The palette is a horizontally-scrollable strip on mobile (see App.css), so
// a TOUCH that starts on a block is ambiguous — "scroll the strip" or "drag
// this block onto the canvas" — and we don't decide until the pointer has
// moved past a small threshold: mostly-horizontal movement is left alone
// (native scroll takes over, permitted by `touch-action: pan-x`);
// mostly-vertical movement starts our own drag.
//
// That ambiguity is specific to touch. Mouse/pen input never triggers the
// browser's native touch-scroll gesture in the first place, so on desktop
// (where the palette is instead a vertical sidebar and dragging onto the
// canvas — to its right — is itself a horizontal motion) waiting to
// disambiguate would misread that as a scroll and swallow the drag. Mouse/pen
// pointers skip the wait entirely and start dragging immediately, exactly
// like before the mobile fix.
export default function Palette({ onDropBlock }) {
  const [dragging, setDragging] = useState(null)
  const draggingRef = useRef(null)

  const onPointerDown = (event, block) => {
    const isTouch = event.pointerType === 'touch'
    const startX = event.clientX
    const startY = event.clientY
    let mode = isTouch ? 'pending' : 'dragging' // 'pending' | 'dragging' | 'scrolling'

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onCancel)
    }

    const startDragging = (x, y) => {
      mode = 'dragging'
      const state = { type: block.type, label: block.label, x, y }
      draggingRef.current = state
      setDragging(state)
    }

    if (mode === 'dragging') {
      startDragging(startX, startY)
    }

    const onMove = (e) => {
      if (mode === 'pending') {
        const dx = e.clientX - startX
        const dy = e.clientY - startY
        if (Math.abs(dx) < DECISION_THRESHOLD && Math.abs(dy) < DECISION_THRESHOLD) return

        if (Math.abs(dy) <= Math.abs(dx)) {
          // Horizontal-dominant touch move on the mobile strip: this is a
          // scroll gesture — let the browser handle it and stop tracking.
          mode = 'scrolling'
          cleanup()
          return
        }

        startDragging(e.clientX, e.clientY)
        return
      }

      if (mode === 'dragging') {
        e.preventDefault()
        const next = { ...draggingRef.current, x: e.clientX, y: e.clientY }
        draggingRef.current = next
        setDragging(next)
      }
    }

    const onUp = (e) => {
      if (mode === 'dragging') {
        const finished = draggingRef.current
        draggingRef.current = null
        setDragging(null)
        if (finished) onDropBlock(finished.type, e.clientX, e.clientY)
      }
      cleanup()
    }

    const onCancel = () => {
      draggingRef.current = null
      setDragging(null)
      cleanup()
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onCancel)
  }

  return (
    <aside className="palette">
      <div className="palette-title">Blocks</div>
      {BLOCK_DEFS.map((block) => (
        <div
          key={block.type}
          className="palette-item"
          onPointerDown={(e) => onPointerDown(e, block)}
        >
          {block.label}
        </div>
      ))}
      <div className="palette-hint">Drag a block onto the canvas, then connect the dots.</div>

      {dragging && (
        <div className="palette-ghost" style={{ left: dragging.x, top: dragging.y }}>
          {dragging.label}
        </div>
      )}
    </aside>
  )
}
