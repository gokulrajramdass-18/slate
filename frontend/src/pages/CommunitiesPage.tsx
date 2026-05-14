/**
 * Communities Explorer Page
 *
 * Explore entity communities detected via Louvain clustering.
 */

import { useState } from 'react'
import { Network, Users, Loader2, RefreshCw, Trash2 } from 'lucide-react'

import {
  useCommunities,
  useCommunityHierarchy,
  useDetectCommunities,
  useDeleteCommunity,
  useRegenerateSummary,
} from '@/lib/api/communities'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function CommunitiesPage() {
  const { toast } = useToast()
  const [detectDialogOpen, setDetectDialogOpen] = useState(false)
  const [notebookId, setNotebookId] = useState('')

  const { data: communities, isLoading } = useCommunities()
  const detectMutation = useDetectCommunities()
  const deleteMutation = useDeleteCommunity()
  const regenerateMutation = useRegenerateSummary()

  const handleDetect = async () => {
    if (!notebookId) {
      toast({
        title: 'Error',
        description: 'Please enter a notebook ID',
        variant: 'destructive',
      })
      return
    }

    try {
      const result = await detectMutation.mutateAsync({
        notebook_id: notebookId,
        generate_summaries: true,
      })

      toast({
        title: 'Communities detected',
        description: `Found ${result.communities_count} communities`,
      })

      setDetectDialogOpen(false)
      setNotebookId('')
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to detect communities',
        variant: 'destructive',
      })
    }
  }

  const handleDelete = async (communityId: string, communityName: string) => {
    if (!confirm(`Delete community "${communityName}"?`)) {
      return
    }

    try {
      await deleteMutation.mutateAsync(communityId)
      toast({
        title: 'Community deleted',
        description: `${communityName} has been deleted`,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete community',
        variant: 'destructive',
      })
    }
  }

  const handleRegenerateSummary = async (communityId: string) => {
    try {
      await regenerateMutation.mutateAsync({ community_id: communityId })
      toast({
        title: 'Summary regenerated',
        description: 'Community summary has been updated',
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to regenerate summary',
        variant: 'destructive',
      })
    }
  }

  const getEntityCount = (entityIdsJson: string) => {
    try {
      const ids = JSON.parse(entityIdsJson)
      return Array.isArray(ids) ? ids.length : 0
    } catch {
      return 0
    }
  }

  const getMetadata = (metadataJson?: string) => {
    if (!metadataJson) return null
    try {
      return JSON.parse(metadataJson)
    } catch {
      return null
    }
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Community Explorer</h1>
          <p className="text-muted-foreground">
            Explore thematic clusters of related entities
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={detectDialogOpen} onOpenChange={setDetectDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Network className="mr-2 h-4 w-4" />
                Detect Communities
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Detect Communities</DialogTitle>
                <DialogDescription>
                  Run Louvain algorithm to detect entity communities in a notebook
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="notebook-id">Notebook ID</Label>
                  <Input
                    id="notebook-id"
                    placeholder="Enter notebook ID"
                    value={notebookId}
                    onChange={(e) => setNotebookId(e.target.value)}
                  />
                </div>
                <Button
                  onClick={handleDetect}
                  disabled={detectMutation.isPending}
                  className="w-full"
                >
                  {detectMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Detecting...
                    </>
                  ) : (
                    'Detect Communities'
                  )}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {communities && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Communities</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{communities.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Entities</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {communities.reduce((sum, c) => sum + getEntityCount(c.entity_ids), 0)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Hierarchy Levels</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {Math.max(...communities.map((c) => c.level), 0) + 1}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div>
        <h2 className="text-xl font-semibold mb-4">
          Communities {communities && `(${communities.length})`}
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : !communities || communities.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-muted-foreground">
                <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No communities found</p>
                <p className="text-sm mt-2">
                  Detect communities from a notebook to see them here
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {communities.map((community) => {
              const entityCount = getEntityCount(community.entity_ids)
              const metadata = getMetadata(community.metadata)

              return (
                <Card key={community.id} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg">
                          {community.name || `Community ${community.id.slice(0, 8)}`}
                        </CardTitle>
                        <div className="flex gap-2 mt-2">
                          <Badge variant="outline">{entityCount} entities</Badge>
                          <Badge variant="outline">Level {community.level}</Badge>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(community.id, community.name || 'Unnamed')}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <CardDescription className="line-clamp-3">
                      {community.description || 'No description'}
                    </CardDescription>

                    {metadata && (
                      <div className="text-sm text-muted-foreground space-y-1">
                        {metadata.modularity && (
                          <div>Modularity: {metadata.modularity.toFixed(3)}</div>
                        )}
                        {metadata.density && (
                          <div>Density: {metadata.density.toFixed(3)}</div>
                        )}
                      </div>
                    )}

                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" asChild className="flex-1">
                        <a href={`/communities/${community.id}`}>View Details</a>
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRegenerateSummary(community.id)}
                        disabled={regenerateMutation.isPending}
                      >
                        <RefreshCw className="h-3 w-3" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
