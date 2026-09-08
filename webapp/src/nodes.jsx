import { useContext } from 'react'
import { Handle, Position } from '@xyflow/react'
import { NodeActionsContext } from './FlowContext.js'

// The block types v1 of the flow engine understands (bot/flow_engine.py).
// Each palette entry's `defaultData` becomes a new node's `data` when dropped.
export const BLOCK_DEFS = [
  { type: 'guide_video', label: '📖 Guide & Video', defaultData: {} },
  { type: 'trigger', label: '▶️ Trigger', defaultData: { command: '/start' } },
  { type: 'send_message', label: '💬 Send Message', defaultData: { text: '' } },
  { type: 'force_join_gate', label: '🔒 Force Join Gate', defaultData: {} },
  { type: 'content_list', label: '📚 Content List', defaultData: {} },
  { type: 'shop', label: '🛍 Shop', defaultData: {} },
  { type: 'broadcast', label: '📢 Broadcast', defaultData: {} },
]

function NodeCard({ id, accent, title, children, showTarget = true, showSource = true }) {
  const { deleteNode } = useContext(NodeActionsContext)
  return (
    <div className="flow-node" style={{ borderLeftColor: accent }}>
      {showTarget && <Handle type="target" position={Position.Left} />}
      <button
        type="button"
        className="nodrag flow-node-delete"
        title="Delete block"
        onClick={() => deleteNode(id)}
      >
        ✕
      </button>
      <div className="flow-node-title">{title}</div>
      {children}
      {showSource && <Handle type="source" position={Position.Right} />}
    </div>
  )
}

export function TriggerNode({ id, data }) {
  const { updateNodeData } = useContext(NodeActionsContext)
  return (
    <NodeCard id={id} accent="#34c759" title="▶️ Trigger" showTarget={false}>
      <input
        className="nodrag flow-node-input"
        placeholder="/start"
        value={data.command || ''}
        onChange={(e) => updateNodeData(id, { command: e.target.value })}
      />
      <div className="flow-node-hint">Any command, e.g. /start, /menu, /help</div>
    </NodeCard>
  )
}

export function SendMessageNode({ id, data }) {
  const { updateNodeData } = useContext(NodeActionsContext)
  return (
    <NodeCard id={id} accent="#0a84ff" title="💬 Send Message">
      <textarea
        className="nodrag flow-node-textarea"
        placeholder="Message text…"
        value={data.text || ''}
        onChange={(e) => updateNodeData(id, { text: e.target.value })}
      />
    </NodeCard>
  )
}

export function ForceJoinGateNode({ id }) {
  return (
    <NodeCard id={id} accent="#ff9500" title="🔒 Force Join Gate">
      <div className="flow-node-body">
        Blocks here until the user has joined every channel configured with
        the "Force Join" tool in the bot chat.
      </div>
    </NodeCard>
  )
}

export function GuideVideoNode({ id }) {
  return (
    <NodeCard id={id} accent="#5856d6" title="📖 Guide & Video">
      <div className="flow-node-body">
        Asks once for the user's phone (optional), guesses their country from
        it, then sends a localized "how to use this bot" guide + video
        tutorial link.
      </div>
    </NodeCard>
  )
}

export function ContentListNode({ id }) {
  const { openContentManager } = useContext(NodeActionsContext)
  return (
    <NodeCard id={id} accent="#34aadc" title="📚 Content List">
      <div className="flow-node-body">
        Shows the content items (news/products/lessons/etc.) defined below —
        or via the "Content List" tool in the bot chat, or bulk-imported from
        an Excel file; all three edit the exact same items. Skipped silently
        if there's no content yet.
      </div>
      <button type="button" className="nodrag flow-node-manage" onClick={openContentManager}>
        🛠 Manage Content
      </button>
    </NodeCard>
  )
}

export function ShopNode({ id }) {
  return (
    <NodeCard id={id} accent="#ff2d55" title="🛍 Shop">
      <div className="flow-node-body">
        Shows the products defined via the "Shop" tool in the bot chat, with
        payment (Zarinpal / card-to-card), shipping, and invoices all handled
        automatically. Skipped silently if there are no products yet.
      </div>
    </NodeCard>
  )
}

export function BroadcastNode({ id }) {
  return (
    <NodeCard id={id} accent="#af52de" title="📢 Broadcast">
      <div className="flow-node-body">
        Marker only — the actual broadcast is sent from the "Broadcast" tool
        in the bot chat.
      </div>
    </NodeCard>
  )
}

export const nodeTypes = {
  trigger: TriggerNode,
  send_message: SendMessageNode,
  force_join_gate: ForceJoinGateNode,
  guide_video: GuideVideoNode,
  content_list: ContentListNode,
  shop: ShopNode,
  broadcast: BroadcastNode,
}
