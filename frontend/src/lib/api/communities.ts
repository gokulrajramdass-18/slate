/**
 * Communities API Client
 *
 * TanStack Query hooks for community operations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export interface Community {
  id: string
  name?: string
  description?: string
  level: number
  parent_community_id?: string
  entity_ids: string
  metadata?: string
  created?: string
  updated?: string
}

export interface CommunityEntity {
  id: string
  name: string
  entity_type: string
  description?: string
}

// Query keys
export const communityKeys = {
  all: ['communities'] as const,
  lists: () => [...communityKeys.all, 'list'] as const,
  list: (filters: Record<string, any>) => [...communityKeys.lists(), filters] as const,
  details: () => [...communityKeys.all, 'detail'] as const,
  detail: (id: string) => [...communityKeys.details(), id] as const,
  entities: (id: string) => [...communityKeys.detail(id), 'entities'] as const,
  hierarchy: () => [...communityKeys.all, 'hierarchy'] as const,
}

// List communities
export function useCommunities(params?: { level?: number; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: communityKeys.list(params || {}),
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (params?.level !== undefined) searchParams.append('level', params.level.toString())
      if (params?.limit) searchParams.append('limit', params.limit.toString())
      if (params?.offset) searchParams.append('offset', params.offset.toString())

      const response = await fetch(`/api/communities?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch communities')
      return response.json() as Promise<Community[]>
    },
  })
}

// Get community hierarchy
export function useCommunityHierarchy(maxLevel?: number) {
  return useQuery({
    queryKey: [...communityKeys.hierarchy(), maxLevel],
    queryFn: async () => {
      const searchParams = new URLSearchParams()
      if (maxLevel !== undefined) searchParams.append('max_level', maxLevel.toString())

      const response = await fetch(`/api/communities/hierarchy?${searchParams}`)
      if (!response.ok) throw new Error('Failed to fetch hierarchy')
      return response.json() as Promise<Record<string, Community[]>>
    },
  })
}

// Get community details
export function useCommunity(id: string | null) {
  return useQuery({
    queryKey: communityKeys.detail(id!),
    queryFn: async () => {
      const response = await fetch(`/api/communities/${id}`)
      if (!response.ok) throw new Error('Failed to fetch community')
      return response.json() as Promise<Community>
    },
    enabled: !!id,
  })
}

// Get community entities
export function useCommunityEntities(id: string | null) {
  return useQuery({
    queryKey: communityKeys.entities(id!),
    queryFn: async () => {
      const response = await fetch(`/api/communities/${id}/entities`)
      if (!response.ok) throw new Error('Failed to fetch community entities')
      return response.json() as Promise<CommunityEntity[]>
    },
    enabled: !!id,
  })
}

// Detect communities
export function useDetectCommunities() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      source_id?: string
      notebook_id?: string
      generate_summaries?: boolean
      resolution?: number
      min_community_size?: number
    }) => {
      const response = await fetch('/api/communities/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })

      if (!response.ok) throw new Error('Failed to detect communities')
      return response.json() as Promise<{
        communities_count: number
        community_ids: string[]
      }>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: communityKeys.all })
    },
  })
}

// Update community
export function useUpdateCommunity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { id: string; name?: string; description?: string }) => {
      const { id, ...data } = params
      const response = await fetch(`/api/communities/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (!response.ok) throw new Error('Failed to update community')
      return response.json() as Promise<Community>
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: communityKeys.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: communityKeys.lists() })
    },
  })
}

// Delete community
export function useDeleteCommunity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`/api/communities/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to delete community')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: communityKeys.all })
    },
  })
}

// Regenerate community summary
export function useRegenerateSummary() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { community_id: string; model?: string }) => {
      const searchParams = new URLSearchParams()
      if (params.model) searchParams.append('model', params.model)

      const response = await fetch(
        `/api/communities/${params.community_id}/regenerate-summary?${searchParams}`,
        {
          method: 'POST',
        }
      )

      if (!response.ok) throw new Error('Failed to regenerate summary')
      return response.json()
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: communityKeys.detail(variables.community_id),
      })
    },
  })
}
