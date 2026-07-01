"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Plus, Trash2, Save, AlertCircle, Search, CheckCircle2, XCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { apiService } from "@/lib/api"

interface Mapping {
  userTitle: string
  actualTitle: string
}

interface TitleSuggestion {
  title: string
  score: number
}

interface TitleResult {
  title: string
  status: 'exact_match' | 'mapped' | 'dropped' | 'needs_mapping'
  mapped_to: string | null
  suggestions: TitleSuggestion[]
}

interface SongTitleMappingProps {
  prefillTitle?: string
  onMappingComplete?: () => void
}

export function SongTitleMapping({ prefillTitle, onMappingComplete }: SongTitleMappingProps = {}) {
  console.log('SongTitleMapping component rendered with prefillTitle:', prefillTitle);
  const [mappings, setMappings] = useState<Record<string, string>>({})
  const [catalog, setCatalog] = useState<string[]>([])
  const [newUserTitle, setNewUserTitle] = useState(prefillTitle || "")
  const [newActualTitle, setNewActualTitle] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [quickPickSuggestions, setQuickPickSuggestions] = useState<string[]>([])

  // Update newUserTitle when prefillTitle changes
  useEffect(() => {
    if (prefillTitle) {
      console.log('Updating newUserTitle with prefillTitle:', prefillTitle);
      setNewUserTitle(prefillTitle);
      // Generate quick pick suggestions for the prefill title
      generateQuickPickSuggestions(prefillTitle);
    }
  }, [prefillTitle]);

  // Generate quick pick suggestions when user title changes
  useEffect(() => {
    if (newUserTitle && catalog.length > 0) {
      generateQuickPickSuggestions(newUserTitle);
    }
  }, [newUserTitle, catalog]);

  const generateQuickPickSuggestions = (title: string) => {
    if (catalog.length === 0) {
      console.log('No catalog available for quick picks');
      setQuickPickSuggestions([]);
      return;
    }
    
    console.log(`Generating quick picks for "${title}" from ${catalog.length} songs`);
    
    // Simple AI-like matching: find songs that contain key words from the title
    const titleWords = title.toLowerCase().split(/\s+/).filter(word => word.length > 2);
    const suggestions: { song: string; score: number }[] = [];
    
    for (const song of catalog) {
      let score = 0;
      const songLower = song.toLowerCase();
      
      // Exact match gets highest score
      if (songLower.includes(title.toLowerCase())) {
        score += 100;
      }
      
      // Word matches
      for (const word of titleWords) {
        if (songLower.includes(word)) {
          score += 10;
        }
      }
      
      // Partial word matches
      for (const word of titleWords) {
        if (word.length > 3) {
          const partial = word.substring(0, 3);
          if (songLower.includes(partial)) {
            score += 3;
          }
        }
      }
      
      if (score > 0) {
        suggestions.push({ song, score });
      }
    }
    
    // Sort by score and return top 4
    const topSuggestions = suggestions
      .sort((a, b) => b.score - a.score)
      .slice(0, 4)
      .map(s => s.song);
    
    setQuickPickSuggestions(topSuggestions);
    console.log('Quick pick suggestions for', title, ':', topSuggestions);
  };

  // Debug current state
  useEffect(() => {
    console.log('Current state:', {
      mappings: Object.keys(mappings).length,
      catalog: catalog.length,
      newUserTitle,
      newActualTitle,
      searchQuery,
      searchResults: searchResults.length
    });
  }, [mappings, catalog, newUserTitle, newActualTitle, searchQuery, searchResults]);
  const [error, setError] = useState<string | null>(null)

  // Load existing mappings and catalog on component mount
  useEffect(() => {
    loadMappings()
    loadCatalog()
  }, [])

  const loadMappings = async () => {
    try {
      const response = await apiService.getTitleMappings()
      if (response.ok && response.data) {
        setMappings(response.data.mappings)
      }
    } catch (err) {
      console.error('Failed to load mappings:', err)
    }
  }

  const loadCatalog = async () => {
    try {
      console.log('Loading user catalog...')
      const response = await apiService.getUserCatalog()
      console.log('Catalog response:', response)
      if (response.ok && response.data) {
        setCatalog(response.data.catalog)
        console.log('Catalog loaded:', response.data.catalog.length, 'songs')
      } else {
        console.error('Failed to load catalog:', response.error)
      }
    } catch (err) {
      console.error('Failed to load catalog:', err)
    }
  }

  const handleAddMapping = () => {
    if (newUserTitle && newActualTitle) {
      const normalizedKey = newUserTitle.toLowerCase().trim()
      setMappings(prev => ({
        ...prev,
        [normalizedKey]: newActualTitle
      }))
      setNewUserTitle("")
      setNewActualTitle("")
      
      // Call the completion callback if provided
      if (onMappingComplete) {
        onMappingComplete()
      }
    }
  }

  const handleDeleteMapping = (userTitle: string) => {
    const normalizedKey = userTitle.toLowerCase().trim()
    setMappings(prev => {
      const newMappings = { ...prev }
      delete newMappings[normalizedKey]
      return newMappings
    })
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    
    try {
      const response = await apiService.saveTitleMappings(mappings)
      if (response.ok) {
        console.log("Mappings saved successfully")
        
        // Reprocess the setlist with updated mappings
        console.log('Reprocessing setlist with updated mappings...')
        // Call the completion callback to trigger reprocessing
        if (onMappingComplete) {
          onMappingComplete('reprocess')
        }
      } else {
        setError(response.error || 'Failed to save mappings')
      }
    } catch (err) {
      setError('Network error: Failed to save mappings')
    } finally {
      setSaving(false)
    }
  }

  const handleSearch = (query: string) => {
    console.log('Searching for:', query, 'in catalog of', catalog.length, 'songs')
    setSearchQuery(query)
    if (query.length < 2) {
      setSearchResults([])
      return
    }
    
    const filtered = catalog.filter(title => 
      title.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 10)
    
    console.log('Search results:', filtered)
    setSearchResults(filtered)
  }

  const handleSelectSuggestion = (suggestion: string) => {
    setNewActualTitle(suggestion)
    setSearchResults([])
    setSearchQuery("")
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Song Title Mapping</CardTitle>
        <CardDescription>
          Map abbreviated or alternate song titles to their actual names in your Song Book Pro database
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Use this section when your set lists contain shortened or alternate song titles that don't match your Song
            Book Pro database exactly. These mappings are user-specific and will be saved to your account.
          </AlertDescription>
        </Alert>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Existing Mappings */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-foreground">
            Current Mappings ({Object.keys(mappings).length})
          </h3>
          <div className="space-y-3">
            {Object.entries(mappings).map(([userTitle, actualTitle]) => (
              <div key={userTitle} className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
                <div className="flex-1 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Set List Title</p>
                    <p className="font-medium text-foreground">{userTitle}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Actual Song Title</p>
                    <p className="font-medium text-foreground">{actualTitle}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDeleteMapping(userTitle)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {Object.keys(mappings).length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No mappings yet. Add your first mapping below.
              </div>
            )}
          </div>
        </div>

        {/* Add New Mapping */}
        <div className="space-y-4 rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-lg font-semibold text-foreground">Add New Mapping</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="user-title">Set List Title</Label>
              <Input
                id="user-title"
                placeholder="e.g., Stairway"
                value={newUserTitle}
                onChange={(e) => setNewUserTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="actual-title">Actual Song Title</Label>
              
              {/* Quick Pick Suggestions */}
              {quickPickSuggestions.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground font-medium">Quick Pick Suggestions:</p>
                  <div className="flex flex-wrap gap-1">
                    {quickPickSuggestions.map((suggestion, index) => (
                      <Button
                        key={index}
                        size="sm"
                        variant="outline"
                        className="text-xs h-7 px-2 bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
                        onClick={() => {
                          console.log('Quick pick selected:', suggestion);
                          setNewActualTitle(suggestion);
                          setSearchResults([]);
                          setSearchQuery("");
                        }}
                      >
                        {suggestion}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="relative">
                <Input
                  id="actual-title"
                  placeholder="e.g., Stairway to Heaven"
                  value={newActualTitle}
                  onChange={(e) => {
                    console.log('Actual title input changed:', e.target.value)
                    setNewActualTitle(e.target.value)
                    handleSearch(e.target.value)
                  }}
                />
                {console.log('Rendering search results:', searchResults.length, 'results')}
                {searchResults.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                    {searchResults.map((suggestion, index) => (
                      <button
                        key={index}
                        className="w-full px-3 py-2 text-left hover:bg-muted flex items-center gap-2"
                        onClick={() => handleSelectSuggestion(suggestion)}
                      >
                        <Search className="h-4 w-4 text-muted-foreground" />
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          <Button 
            onClick={handleAddMapping} 
            className="gap-2"
            disabled={!newUserTitle || !newActualTitle}
          >
            <Plus className="h-4 w-4" />
            Add Mapping
          </Button>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <Button 
            onClick={handleSave} 
            size="lg" 
            className="gap-2"
            disabled={saving}
          >
            <Save className="h-5 w-5" />
            {saving ? 'Saving...' : 'Save All Mappings'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
