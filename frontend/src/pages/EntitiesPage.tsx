/**
 * Entity Browser Page
 *
 * Browse, search, and manage entities extracted from sources.
 */

import { useState } from 'react'
import { Search, Filter, Loader2, Network, Trash2 } from 'lucide-react'

import { useEntities, useEntitySearch, useDeleteEntity, useExtractEntities } from '@/lib/api/entities'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'

const ENTITY_TYPES = [
  { value: 'all', label: 'All Types' },
  { value: 'person', label: 'Person' },
  { value: 'organization', label: 'Organization' },
  { value: 'location', label: 'Location' },
  { value: 'event', label: 'Event' },
  { value: 'concept', label: 'Concept' },
  { value: 'other', label: 'Other' },
]

const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: 'bg-blue-100 text-blue-800',
  organization: 'bg-purple-100 text-purple-800',
  location: 'bg-green-100 text-green-800',
  event: 'bg-orange-100 text-orange-800',
  concept: 'bg-pink-100 text-pink-800',
  other: 'bg-gray-100 text-gray-800',
}

export default function EntitiesPage() {
  const { toast } = useToast()
  const [searchQuery, setSearchQuery] = useState('')
  const [entityType, setEntityType] = useState('all')

  const { data: entities, isLoading } = useEntities({
    entity_type: entityType === 'all' ? undefined : entityType,
    limit: 100,
  })

  const { data: searchResults } = useEntitySearch(searchQuery, searchQuery.length > 2)

  const deleteEntity = useDeleteEntity()

  const displayEntities = searchQuery.length > 2 ? searchResults : entities

  const handleDelete = async (entityId: string, entityName: string) => {
    if (!confirm(`Delete entity "${entityName}"? This will also delete all relationships.`)) {
      return
    }

    try {
      await deleteEntity.mutateAsync(entityId)
      toast({
        title: 'Entity deleted',
        description: `${entityName} has been deleted`,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete entity',
        variant: 'destructive',
      })
    }
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Entity Browser</h1>
          <p className="text-muted-foreground">
            Browse and manage entities extracted from your sources
          </p>
        </div>
        <Button asChild>
          <a href="/graph/entities">
            <Network className="mr-2 h-4 w-4" />
            View Graph
          </a>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search entities by name or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <Select value={entityType} onValueChange={setEntityType}>
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ENTITY_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            Entities {displayEntities && `(${displayEntities.length})`}
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : !displayEntities || displayEntities.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-muted-foreground">
                <p>No entities found</p>
                <p className="text-sm mt-2">
                  Extract entities from sources to see them here
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {displayEntities.map((entity) => (
              <Card key={entity.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">{entity.name}</CardTitle>
                      <Badge
                        className={`mt-2 ${ENTITY_TYPE_COLORS[entity.entity_type] || ENTITY_TYPE_COLORS.other}`}
                      >
                        {entity.entity_type}
                      </Badge>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(entity.id, entity.name)}
                      disabled={deleteEntity.isPending}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="line-clamp-3">
                    {entity.description || 'No description'}
                  </CardDescription>
                  <div className="mt-4 flex gap-2">
                    <Button variant="outline" size="sm" asChild>
                      <a href={`/entities/${entity.id}`}>View Details</a>
                    </Button>
                    <Button variant="outline" size="sm" asChild>
                      <a href={`/graph/entities?focus=${entity.id}`}>
                        <Network className="h-3 w-3 mr-1" />
                        Graph
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
