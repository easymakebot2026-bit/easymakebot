import { createContext } from 'react'

// Lets node components push data edits / deletion up to App's node state
// without storing callback functions inside node.data (which must stay
// plain, JSON-serializable data since it's what gets POSTed to /api/flow).
export const NodeActionsContext = createContext({
  updateNodeData: () => {},
  deleteNode: () => {},
  openContentManager: () => {},
})
