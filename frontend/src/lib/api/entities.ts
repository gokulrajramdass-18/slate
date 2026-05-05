/**
 * Entity API Client
 *
 * TanStack Query hooks for entity operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export interface Entity {
  id: string
  name: string
  entity_type: string
  description?: string
  source_id: string
  chunk_id?: string
  metadata?: string
  created?: string
  updated?: string
}

export interface EntityRelationship {
  id: string
  source_entity_id: string
  target_entity_id: string
  relationship_type: string
  context?: string
  chunk_id?: string
  strength: number
  metadata?: string
  created?: string
}

export interface EntityGraph {
  nodes: any[]
  edges: any[]
  metadata: Record<string, any>
}

// Query keys
export const entityKeys = {
  all: ['entities'] as const,
  lists: () => [...entityKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) => [...entityKeys.lists(), filters] as const,
  details: () => [...entityKeys.all, 'detail'] as const,
  detail: (id: string) => [...entityKeys.details(), id] as const,
  relationships: (id: string) => [...entityKeys.detail(id), 'relationships'] as const,
  neighbors: (id: string, depth: number) => [...entityKeys.detail(id), 'neighbors', depth] as const,
  search: (query: string) => [...entityKeys.all, 'search', query] as const,
}

// List entities
export function useEntities(params?: {
  source_id?: string
  entity_type?: string
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: entityKeys.list(params || {}),
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params?.source_id) searchParams.append('source_id', params.source_id)
      if (params?.entity_type) searchParams.append('entity_type', params.entity_type)
      if (params?.limit) searchParams.append('limit', params.limit.toString())
      if (params?.offset) searchParams.append('offset', params.offset.toString())

      const response = await fetch(`/api/entities?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch entities')
      return response.json() as Promise<Entity[]>
    },
  })
}

// Search entities
export function useEntitySearch(query: string, enabled = true) {
  return useQuery({
    queryKey: entityKeys.search(query),
    queryFn: async () => {
      const response = await fetch(`/api/entities/search?query=${encodeURIComponent(query)}`)
      if (!response.ok) throw new Error('Failed to search entities')
      return response.json() as Promise<Entity[]>
    },
    enabled: enabled && query.length > 0,
  })
}

// Get entity details
export function useEntity(id: string | null) {
  return useQuery({
    queryKey: entityKeys.detail(id!),
    queryFn: async () => {
      const response = await fetch(`/api/entities/${id}`)
      if (!response.ok) throw new Error('Failed to fetch entity')
      return response.json() as Promise<Entity>
    },
    enabled: !!id,
  })
}

// Get entity relationships
export function useEntityRelationships(
  id: string | null,
  params?: {
    direction?: 'outgoing' | 'incoming' | 'both'
    min_strength?: number
  }
) {
  return useQuery({
    queryKey: entityKeys.relationships(id!),
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params?.direction) searchParams.append('direction', params.direction)
      if (params?.min_strength !== undefined) {
        searchParams.append('min_strength', params.min_strength.toString())
      }

      const response = await fetch(`/api/entities/${id}/relationships?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch relationships')
      return response.json() as Promise<EntityRelationship[]>
    },
    enabled: !!id,
  })
}

// Get entity neighbors
export function useEntityNeighbors(id: string | null, depth = 1) {
  return useQuery({
    queryKey: entityKeys.neighbors(id!, depth),
    queryFn: async () => {
      const response = await fetch(`/api/entities/${id}/neighbors?depth=${depth}`)
      if (!response.ok) throw new Error('Failed to fetch neighbors')
      return response.json() as Promise<EntityGraph>
    },
    enabled: !!id,
  })
}

// Extract entities from source
export function useExtractEntities() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { source_id: string; force?: boolean; model?: string }) => {
      const searchParams = new URLSearchParams()
      if (params.force) searchParams.append('force', 'true')
      if (params.model) searchParams.append('model', params.model)

      const response = await fetch(`/api/entities/extract/${params.source_id}?${searchParams}`, {
        method: 'POST',
      })

      if (!response.ok) throw new Error('Failed to extract entities')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.all })
    },
  })
}

// Update entity
export function useUpdateEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      id: string
      name?: string
      entity_type?: string
      description?: string
    }) => {
      const { id, ...data } = params
      const response = await fetch(`/api/entities/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (!response.ok) throw new Error('Failed to update entity')
      return response.json() as Promise<Entity>
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: entityKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: entityKeys.lists() })
    },
  })
}

// Delete entity
export function useDeleteEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`/api/entities/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to delete entity')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.all })
    },
  })
}

// Merge entities
export function useMergeEntities() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { entity_id: string; target_entity_id: string }) => {
      const response = await fetch(`/api/entities/${params.entity_id}/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_entity_id: params.target_entity_id }),
      })

      if (!response.ok) throw new Error('Failed to merge entities')
      return response.json() as Promise<Entity>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.all })
    },
  })
}
