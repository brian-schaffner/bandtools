"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Trash2, Download, RotateCcw, FileText, Database, Archive } from 'lucide-react'
import { toast } from 'sonner'
import { apiService } from '@/lib/api'

interface ArchiveItem {
  id: string
  filename: string
  original_filename?: string
  path: string
  created: string
  size?: number
  file_size_mb?: number
  file_exists?: boolean
  reprocessed_from?: string
}

interface ArchiveData {
  backups: ArchiveItem[]
  setlists: ArchiveItem[]
  downloads: ArchiveItem[]
  title_mapper: Record<string, string>
  summary: {
    total_backups: number
    total_setlists: number
    total_downloads: number
    total_mappings: number
    latest_backup: ArchiveItem | null
    latest_setlist: ArchiveItem | null
    latest_download: ArchiveItem | null
  }
}

export default function ArchiveManager() {
  console.log('🔍 ArchiveManager: Component rendered')
  const [archiveData, setArchiveData] = useState<ArchiveData | null>(null)
  const [loading, setLoading] = useState(true)
  const [reprocessing, setReprocessing] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const fetchArchiveData = async () => {
    try {
      const response = await apiService.getArchive()
      
      if (!response.ok) {
        throw new Error(response.error || 'Failed to fetch archive')
      }
      
      setArchiveData(response.data)
    } catch (error) {
      console.error('Error fetching archive data:', error)
      toast.error('Failed to load archive data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchArchiveData()
  }, [])

  const handleReprocess = async (itemType: string, itemId: string, itemName: string) => {
    setReprocessing(itemId)
    try {
      const response = await apiService.reprocessArchiveItem(itemType, itemId)
      
      if (!response.ok) {
        throw new Error(response.error || 'Reprocessing failed')
      }
      
      toast.success(`Successfully reprocessed ${itemName}`)
      
      // Refresh archive data
      await fetchArchiveData()
    } catch (error) {
      console.error('Error reprocessing item:', error)
      toast.error(`Failed to reprocess ${itemName}: ${error.message}`)
    } finally {
      setReprocessing(null)
    }
  }

  const handleDelete = async (itemType: string, itemId: string, itemName: string) => {
    if (!confirm(`Are you sure you want to delete ${itemName}? This action cannot be undone.`)) {
      return
    }
    
    setDeleting(itemId)
    try {
      const response = await apiService.deleteArchiveItem(itemType, itemId)
      
      if (!response.ok) {
        throw new Error(response.error || 'Deletion failed')
      }
      
      toast.success(`Successfully deleted ${itemName}`)
      
      // Refresh archive data
      await fetchArchiveData()
    } catch (error) {
      console.error('Error deleting item:', error)
      toast.error(`Failed to delete ${itemName}: ${error.message}`)
    } finally {
      setDeleting(null)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    return `${(size / (1024 * 1024)).toFixed(1)} MB`
  }

  const renderCombinedItems = (items: any[]) => {
    if (!items || items.length === 0) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <Archive className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p>No setlists found</p>
        </div>
      )
    }

    return (
      <div className="space-y-6">
        {items.map((item) => (
          <Card key={item.id} className="relative">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <FileText className="h-5 w-5" />
                  <div>
                    <CardTitle className="text-sm font-medium">
                      {item.original_filename || item.setlist?.metadata?.original_filename || item.setlist?.filename}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      PDF Setlist • {formatDate(item.uploaded_at || "")}
                    </CardDescription>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {item.file_exists ? (
                    <Badge variant="default" className="text-xs">
                      PDF Ready
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="text-xs">
                      PDF Missing
                    </Badge>
                  )}
                  {item.has_downloads && (
                    <Badge variant="secondary" className="text-xs">
                      SBP Ready
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground mb-4">
                <div>
                  <span className="font-medium">PDF Size:</span> {formatFileSize((item.file_size_mb || 0) * 1024 * 1024)}
                </div>
                <div>
                  <span className="font-medium">Downloads:</span> {item.downloads?.length || 0} SBP file(s)
                </div>
              </div>
              
              {/* Downloads section */}
              {item.downloads && item.downloads.length > 0 && (
                <div className="border-t pt-4 mb-4">
                  <h4 className="text-sm font-medium mb-2">Generated SBP Files:</h4>
                  <div className="space-y-2">
                    {item.downloads.map((download: any, index: number) => (
                      <div key={download.id} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                        <div className="flex items-center space-x-2">
                          <Download className="h-4 w-4" />
                          <span className="text-sm">{download.filename}</span>
                          <span className="text-xs text-muted-foreground">
                            ({formatFileSize((download.file_size ?? download.size ?? 0))})
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Button 
                            size="sm" 
                            onClick={() => {
                              const downloadUrl = apiService.downloadFile(download.id);
                              window.open(downloadUrl, '_blank');
                            }}
                          >
                            <Download className="h-4 w-4 mr-1" /> Download
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDelete("download", download.id, download.filename)}
                            disabled={deleting === download.id}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="flex items-center justify-end space-x-2">
                <Button
                  size="sm"
                  onClick={() => handleReprocess("setlist", item.id, item.original_filename || item.setlist?.filename)}
                  disabled={reprocessing === item.id || !item.file_exists}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  {item.has_downloads ? "Reprocess & Update" : "Generate SBP"}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete("setlist", item.id, item.original_filename || item.setlist?.filename)}
                  disabled={deleting === item.id}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const renderItemList = (items: ArchiveItem[], type: string, icon: React.ReactNode) => {
    if (!items || items.length === 0) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <Archive className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p>No {type} found</p>
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {items.map((item) => (
          <Card key={item.id} className="relative">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  {icon}
                  <div>
                    <CardTitle className="text-sm font-medium">
                      {item.metadata?.original_filename || item.filename}
                    </CardTitle>
                    {item.original_filename && item.original_filename !== item.filename && (
                      <CardDescription className="text-xs">
                        Original: {item.original_filename}
                      </CardDescription>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {item.file_exists === false && (
                    <Badge variant="destructive" className="text-xs">
                      Missing
                    </Badge>
                  )}
                  {item.reprocessed_from && (
                    <Badge variant="secondary" className="text-xs">
                      Reprocessed
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                <div>
                  <span className="font-medium">Created:</span> {formatDate(item.uploaded_at || item.created)}
                </div>
                <div>
                  <span className="font-medium">Size:</span> {formatFileSize((item.file_size_mb ? item.file_size_mb * 1024 * 1024 : (item.file_size ?? item.size ?? 0)))}
                </div>
              </div>
              
              <div className="flex items-center justify-end space-x-2 mt-4">
                {type === 'setlist' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleReprocess(type, item.id, item.filename)}
                    disabled={reprocessing === item.id || !item.file_exists}
                  >
                    <RotateCcw className="h-4 w-4 mr-2" />
                    {reprocessing === item.id ? 'Reprocessing...' : 'Reprocess'}
                  </Button>
                )}
                {type === 'download' && (
                  <Button
                    size="sm"
                    onClick={() => {
                      const url = apiService.downloadFile(item.id)
                      window.open(url, '_blank')
                    }}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                )}
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDelete(type, item.id, item.filename)}
                  disabled={deleting === item.id}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  {deleting === item.id ? 'Deleting...' : 'Delete'}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!archiveData) {
    return (
      <div className="text-center py-8">
        <div className="text-lg font-semibold mb-2">Archive Manager</div>
        <div className="text-muted-foreground mb-4">Loading archive data...</div>
        <Button onClick={fetchArchiveData}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Archive Manager</h2>
          <p className="text-muted-foreground">
            Manage your uploaded files and processing history
          </p>
        </div>
        <Button onClick={fetchArchiveData} variant="outline">
          <RotateCcw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Backups</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{archiveData.summary.total_backups}</div>
            <p className="text-xs text-muted-foreground">
              {archiveData.summary.latest_backup ? 'Latest: ' + (archiveData.summary.latest_backup.metadata?.original_filename || archiveData.summary.latest_backup.filename) : 'No backups'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Setlists</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{archiveData.summary.total_setlists}</div>
            <p className="text-xs text-muted-foreground">
              {archiveData.summary.latest_setlist ? 'Latest: ' + (archiveData.summary.latest_setlist.metadata?.original_filename || archiveData.summary.latest_setlist.filename) : 'No setlists'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Downloads</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{archiveData.summary.total_downloads}</div>
            <p className="text-xs text-muted-foreground">
              {archiveData.summary.latest_download ? 'Latest: ' + (archiveData.summary.latest_download.metadata?.original_filename || archiveData.summary.latest_download.filename) : 'No downloads'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{archiveData.summary.total_mappings}</div>
            <p className="text-xs text-muted-foreground">
              Title mappings
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Archive Tabs */}
        <Tabs defaultValue="combined" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="combined" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Setlists & Downloads ({archiveData.summary.total_combined_items || archiveData.summary.total_setlists})</span>
          </TabsTrigger>
          <TabsTrigger value="backups" className="flex items-center space-x-2">
            <Database className="h-4 w-4" />
            <span>Backups ({archiveData.summary.total_backups})</span>
          </TabsTrigger>
          <TabsTrigger value="downloads" className="flex items-center space-x-2">
            <Download className="h-4 w-4" />
            <span>Downloads ({archiveData.summary.total_downloads})</span>
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="combined" className="mt-6">
          {renderCombinedItems(archiveData.combined_items || archiveData.setlists)}
        </TabsContent>
        
        <TabsContent value="backups" className="mt-6">
          {renderItemList(archiveData.backups, 'backup', <Database className="h-5 w-5" />)}
        </TabsContent>
        
        <TabsContent value="downloads" className="mt-6">
          {renderItemList(archiveData.downloads, 'download', <Download className="h-5 w-5" />)}
        </TabsContent>
      </Tabs>
    </div>
  )
}
