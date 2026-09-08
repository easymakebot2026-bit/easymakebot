import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './App.css'
import { nodeTypes, BLOCK_DEFS } from './nodes.jsx'
import { NodeActionsContext } from './FlowContext.js'
import Palette from './Palette.jsx'
import ContentManager from './ContentManager.jsx'
import { initTelegramApp, getBotId, loadFlow, saveFlow } from './telegram.js'

let nextId = 1
function newNodeId() {
  return `node-${Date.now()}-${nextId++}`
}

function Canvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [status, setStatus] = useState('Loading…')
  const [managingContent, setManagingContent] = useState(false)
  const wrapperRef = useRef(null)
  const { screenToFlowPosition } = useReactFlow()

  useEffect(() => {
    const botId = getBotId()
    if (!botId) {
      setStatus('Missing bot_id — open this page from the bot\'s "Visual Builder" button.')
      return
    }

    loadFlow()
      .then((flow) => {
        setNodes(flow.nodes || [])
        setEdges((flow.edges || []).map((e) => ({ ...e, id: e.id || `${e.source}-${e.target}` })))
        setStatus('')
      })
      .catch((err) => setStatus(`Failed to load: ${err.message}`))
  }, [setNodes, setEdges])

  const updateNodeData = useCallback(
    (id, patch) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))
      )
    },
    [setNodes]
  )

  const deleteNode = useCallback(
    (id) => {
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
    },
    [setNodes, setEdges]
  )

  const openContentManager = useCallback(() => setManagingContent(true), [])

  const nodeActions = useMemo(
    () => ({ updateNodeData, deleteNode, openContentManager }),
    [updateNodeData, deleteNode, openContentManager]
  )

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges])

  // Edges have no touch-friendly context menu, so tapping one deletes it
  // directly — cheap to reconnect if that wasn't the intent.
  const onEdgeClick = useCallback(
    (_event, edge) => setEdges((eds) => eds.filter((e) => e.id !== edge.id)),
    [setEdges]
  )

  const handleDropBlock = useCallback(
    (blockType, clientX, clientY) => {
      const blockDef = BLOCK_DEFS.find((b) => b.type === blockType)
      if (!blockDef || !wrapperRef.current) return

      const bounds = wrapperRef.current.getBoundingClientRect()
      const insideCanvas =
        clientX >= bounds.left &&
        clientX <= bounds.right &&
        clientY >= bounds.top &&
        clientY <= bounds.bottom
      if (!insideCanvas) return

      const position = screenToFlowPosition({ x: clientX, y: clientY })
      setNodes((nds) => [
        ...nds,
        {
          id: newNodeId(),
          type: blockDef.type,
          position,
          data: { ...blockDef.defaultData },
        },
      ])
    },
    [screenToFlowPosition, setNodes]
  )

  const handleSave = useCallback(async () => {
    setStatus('Saving…')
    try {
      await saveFlow({
        nodes: nodes.map(({ id, type, data, position }) => ({ id, type, data, position })),
        edges: edges.map(({ source, target }) => ({ source, target })),
      })
      setStatus('Saved ✅')
      setTimeout(() => setStatus(''), 2000)
    } catch (err) {
      setStatus(`Failed to save: ${err.message}`)
    }
  }, [nodes, edges])

  return (
    <NodeActionsContext.Provider value={nodeActions}>
      <div className="builder">
        <Palette onDropBlock={handleDropBlock} />
        <div className="canvas-area" ref={wrapperRef}>
          <div className="topbar">
            <span className="status">{status}</span>
            <button className="save-button" onClick={handleSave}>
              Save
            </button>
          </div>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </div>
      {managingContent && <ContentManager onClose={() => setManagingContent(false)} />}
    </NodeActionsContext.Provider>
  )
}

export default function App() {
  useEffect(() => {
    initTelegramApp()
  }, [])

  return (
    <ReactFlowProvider>
      <Canvas />
    </ReactFlowProvider>
  )
}
