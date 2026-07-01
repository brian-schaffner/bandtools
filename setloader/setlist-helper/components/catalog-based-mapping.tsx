'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { 
  Search, 
  Plus, 
  Trash2, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  Music,
  FileText,
  Filter,
  ChevronDown,
  ChevronRight
} from 'lucide-react'

interface CatalogSong {
  id: number
  name: string
  content?: string
}

interface UserMapping {
  userTitle: string
  catalogTitle: string
  isDrop: boolean
}

interface CatalogBasedMappingProps {
  userCatalog: CatalogSong[]
  userMappings: Record<string, string>
  onMappingUpdate: (mappings: Record<string, string>) => void
  onMappingComplete?: () => void
}

export default function CatalogBasedMapping({
  userCatalog,
  userMappings,
  onMappingUpdate,
  onMappingComplete
}: CatalogBasedMappingProps) {
  console.log('CatalogBasedMapping rendered with:', {
    catalogLength: userCatalog.length,
    mappingsLength: Object.keys(userMappings).length
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [filterType, setFilterType] = useState<'all' | 'mapped' | 'unmapped' | 'dropped'>('all')
  const [editingMapping, setEditingMapping] = useState<string | null>(null)
  const [newUserTitle, setNewUserTitle] = useState('')
  const [catalogBasedMappings, setCatalogBasedMappings] = useState<Record<string, UserMapping[]>>({})
  const [mappedSongsCollapsed, setMappedSongsCollapsed] = useState(false)

  // Debug: Monitor userMappings changes
  useEffect(() => {
    console.log('userMappings changed:', Object.keys(userMappings).length, 'mappings')
  }, [userMappings])

  // Convert user mappings to catalog-based structure
  useEffect(() => {
    console.log('Converting mappings - userCatalog length:', userCatalog.length)
    console.log('Converting mappings - userMappings keys:', Object.keys(userMappings).length)
    console.log('Sample userMappings:', Object.entries(userMappings).slice(0, 3))
    
    const catalogBased: Record<string, UserMapping[]> = {}
    
    // Initialize all catalog songs as unmapped
    userCatalog.forEach(song => {
      catalogBased[song.name] = []
    })
    
    // Add existing mappings
    Object.entries(userMappings).forEach(([userTitle, catalogTitle]) => {
      if (catalogTitle === '__DROP__') {
        // Handle dropped items - they don't map to any catalog song
        if (!catalogBased['__DROPPED__']) {
          catalogBased['__DROPPED__'] = []
        }
        catalogBased['__DROPPED__'].push({
          userTitle,
          catalogTitle: '__DROP__',
          isDrop: true
        })
      } else if (catalogBased[catalogTitle]) {
        catalogBased[catalogTitle].push({
          userTitle,
          catalogTitle,
          isDrop: false
        })
      } else {
        // Debug: log unmapped catalog titles
        console.log(`No catalog match found for: "${catalogTitle}"`)
      }
    })
    
    console.log('Catalog-based mappings:', catalogBased)
    setCatalogBasedMappings(catalogBased)
  }, [userCatalog, userMappings])

  const filteredCatalog = userCatalog.filter(song => {
    const matchesSearch = song.name.toLowerCase().includes(searchTerm.toLowerCase())
    if (!matchesSearch) return false
    
    const mappings = catalogBasedMappings[song.name] || []
    const hasMappings = mappings.length > 0
    
    switch (filterType) {
      case 'mapped': return hasMappings
      case 'unmapped': return !hasMappings
      case 'dropped': return false
      default: return true
    }
  }).sort((a, b) => {
    // Sort alphabetically by name
    return a.name.localeCompare(b.name)
  })

  // Group songs by mapping status
  const mappedSongs = filteredCatalog.filter(song => {
    const mappings = catalogBasedMappings[song.name] || []
    return mappings.length > 0
  })
  
  const unmappedSongs = filteredCatalog.filter(song => {
    const mappings = catalogBasedMappings[song.name] || []
    return mappings.length === 0
  })

  const droppedItems = catalogBasedMappings['__DROPPED__'] || []

  const handleAddMapping = (catalogTitle: string) => {
    if (!newUserTitle.trim()) return
    
    const updatedMappings = { ...userMappings }
    updatedMappings[newUserTitle.trim()] = catalogTitle
    onMappingUpdate(updatedMappings)
    setNewUserTitle('')
    setEditingMapping(null)
  }

  const handleRemoveMapping = (userTitle: string) => {
    const updatedMappings = { ...userMappings }
    delete updatedMappings[userTitle]
    onMappingUpdate(updatedMappings)
  }

  const handleDropItem = (userTitle: string) => {
    const updatedMappings = { ...userMappings }
    updatedMappings[userTitle] = '__DROP__'
    onMappingUpdate(updatedMappings)
  }

  const handleUndropItem = (userTitle: string) => {
    const updatedMappings = { ...userMappings }
    delete updatedMappings[userTitle]
    onMappingUpdate(updatedMappings)
  }

  const getMappingStats = () => {
    const totalMappings = Object.keys(userMappings).length
    const droppedCount = Object.values(userMappings).filter(v => v === '__DROP__').length
    const activeMappings = totalMappings - droppedCount
    
    // Count how many catalog songs actually have mappings
    const mappedCatalogSongs = new Set()
    Object.values(userMappings).forEach(mappedTitle => {
      if (mappedTitle !== '__DROP__' && mappedTitle !== '') {
        // Check if this mapped title exists in the catalog
        const catalogSong = userCatalog.find(song => song.name === mappedTitle)
        if (catalogSong) {
          mappedCatalogSongs.add(catalogSong.name)
        }
      }
    })
    
    const songsWithMappings = mappedCatalogSongs.size
    const unmappedSongs = userCatalog.length - songsWithMappings
    
    return { 
      totalMappings, 
      droppedCount, 
      activeMappings, 
      songsWithMappings,
      unmappedSongs 
    }
  }

  const stats = getMappingStats()

  const renderSongCard = (song: CatalogSong) => {
    const mappings = catalogBasedMappings[song.name] || []
    const isEditing = editingMapping === song.name
    
    return (
      <Card key={song.id} className="relative">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Music className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">{song.name}</CardTitle>
              <Badge variant="outline" className="text-xs">
                ID: {song.id}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              {mappings.length > 0 ? (
                <Badge variant="default" className="text-xs">
                  {mappings.length} mapping{mappings.length !== 1 ? 's' : ''}
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-xs">
                  Unmapped
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingMapping(isEditing ? null : song.name)}
              >
                {isEditing ? 'Cancel' : 'Add Mapping'}
              </Button>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="pt-0">
          {/* Existing mappings */}
          {mappings.length > 0 && (
            <div className="space-y-2">
              {mappings.map((mapping, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-muted rounded-md">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm font-medium">{mapping.userTitle}</span>
                    {mapping.isDrop && (
                      <Badge variant="destructive" className="text-xs">DROPPED</Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemoveMapping(mapping.userTitle)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
          
          {/* Add new mapping */}
          {isEditing && (
            <div className="mt-3 p-3 border rounded-md bg-muted/50">
              <Label htmlFor={`new-title-${song.id}`} className="text-sm font-medium">
                Add user title that maps to "{song.name}"
              </Label>
              <div className="flex gap-2 mt-2">
                <Input
                  id={`new-title-${song.id}`}
                  placeholder="Enter user title..."
                  value={newUserTitle}
                  onChange={(e) => setNewUserTitle(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAddMapping(song.name)}
                />
                <Button
                  size="sm"
                  onClick={() => handleAddMapping(song.name)}
                  disabled={!newUserTitle.trim()}
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Song Title Mapping</h3>
          <p className="text-sm text-muted-foreground">
            Organize your song mappings by catalog title
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline">{stats.songsWithMappings} catalog songs mapped</Badge>
          <Badge variant="secondary">{stats.unmappedSongs} catalog songs unmapped</Badge>
          {stats.droppedCount > 0 && (
            <Badge variant="destructive">{stats.droppedCount} dropped</Badge>
          )}
        </div>
      </div>

      {/* Search and filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search catalog songs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        <Tabs value={filterType} onValueChange={(value) => setFilterType(value as any)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="mapped">Mapped</TabsTrigger>
            <TabsTrigger value="unmapped">Unmapped</TabsTrigger>
            <TabsTrigger value="dropped">Dropped</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Mapped Songs Section */}
      {mappedSongs.length > 0 && (
        <Collapsible open={!mappedSongsCollapsed} onOpenChange={setMappedSongsCollapsed}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-4 h-auto">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-semibold">Mapped Songs ({mappedSongs.length})</span>
              </div>
              {mappedSongsCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            {mappedSongs.map(renderSongCard)}
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Unmapped Songs Section */}
      {unmappedSongs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            <span className="font-semibold">Unmapped Songs ({unmappedSongs.length})</span>
          </div>
          {unmappedSongs.map(renderSongCard)}
        </div>
      )}

      {/* Dropped items section */}
      {droppedItems.length > 0 && filterType === 'dropped' && (
        <div className="space-y-4">
          <Separator />
          <div>
            <h4 className="text-lg font-semibold text-destructive flex items-center gap-2">
              <XCircle className="h-5 w-5" />
              Dropped Items ({droppedItems.length})
            </h4>
            <p className="text-sm text-muted-foreground">
              These items will be ignored during setlist processing
            </p>
          </div>
          
          <div className="space-y-2">
            {droppedItems.map((item, index) => (
              <div key={index} className="flex items-center justify-between p-3 border border-destructive/20 rounded-md bg-destructive/5">
                <div className="flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-destructive" />
                  <span className="font-medium">{item.userTitle}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleUndropItem(item.userTitle)}
                >
                  Restore
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      <Card className="bg-muted/50">
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-green-600">{stats.songsWithMappings}</div>
              <div className="text-sm text-muted-foreground">Catalog Songs Mapped</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-600">{stats.unmappedSongs}</div>
              <div className="text-sm text-muted-foreground">Catalog Songs Unmapped</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-600">{stats.droppedCount}</div>
              <div className="text-sm text-muted-foreground">Dropped Items</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-600">{userCatalog.length}</div>
              <div className="text-sm text-muted-foreground">Total Catalog</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
