"use client"

import { useEffect, useRef, useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { getApiAuthHeaders, getApiBaseUrl } from "@/lib/api"
import { Calendar, Loader2, RefreshCw } from "lucide-react"

interface GigEventOption {
  date: string
  short_date?: string
  time: string
  title: string
  venue: string
  suggested_name: string
}

interface GigSuggestionsResponse {
  target_date: string
  band: string
  source: string
  events: GigEventOption[]
  upcoming: GigEventOption[]
  primary_suggestion?: string | null
  note?: string | null
  naming?: {
    recommended_max_chars: number
    suggestion_max_chars: number
    venue_max_chars: number
    note: string
  }
}

interface GigNameFieldProps {
  fallbackName?: string
  value: string
  onChange: (value: string) => void
}

export function GigNameField({ fallbackName, value, onChange }: GigNameFieldProps) {
  const [targetDate, setTargetDate] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<GigSuggestionsResponse | null>(null)
  const userEditedRef = useRef(false)

  const loadSuggestions = async (dateOverride?: string) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (dateOverride || targetDate) {
        params.set("date", dateOverride || targetDate)
      }
      const response = await fetch(`${getApiBaseUrl()}/gig/suggestions?${params.toString()}`, {
        headers: getApiAuthHeaders(),
      })
      if (!response.ok) {
        throw new Error(`Calendar lookup failed (${response.status})`)
      }
      const data: GigSuggestionsResponse = await response.json()
      setSuggestions(data)
      if (!targetDate) {
        setTargetDate(data.target_date)
      }
      if (!userEditedRef.current && data.primary_suggestion) {
        onChange(data.primary_suggestion)
      } else if (!userEditedRef.current && fallbackName && !value) {
        onChange(fallbackName)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gig calendar")
      if (!userEditedRef.current && fallbackName && !value) {
        onChange(fallbackName)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSuggestions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (fallbackName && !value && !userEditedRef.current && !suggestions?.primary_suggestion) {
      onChange(fallbackName)
    }
  }, [fallbackName, value, onChange, suggestions?.primary_suggestion])

  const options = suggestions?.events?.length
    ? suggestions.events
    : suggestions?.upcoming || []

  return (
    <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <Label htmlFor="gig-output-name" className="text-sm font-medium">
          Output file name
        </Label>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      <Input
        id="gig-output-name"
        value={value}
        onChange={(e) => {
          userEditedRef.current = true
          onChange(e.target.value)
        }}
        placeholder={fallbackName || "Jun 26 Stevie Rays Blues Bar"}
      />

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="gig-date" className="text-xs text-muted-foreground">
            Gig date
          </Label>
          <Input
            id="gig-date"
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            className="w-[180px]"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => loadSuggestions(targetDate)}
          disabled={loading}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh gigs
        </Button>
      </div>

      {suggestions && (
        <p className="text-xs text-muted-foreground">
          {suggestions.band} calendar
          {suggestions.note ? ` — ${suggestions.note}` : ""}
          {suggestions.naming ? ` · aim for ≤${suggestions.naming.recommended_max_chars} chars in Song Book Pro` : ""}
        </p>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}

      {options.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Suggested from calendar</p>
          <div className="flex flex-wrap gap-2">
            {options.map((event) => (
              <Button
                key={`${event.date}-${event.suggested_name}`}
                type="button"
                variant="secondary"
                size="sm"
                className="h-auto whitespace-normal text-left"
                onClick={() => {
                  userEditedRef.current = true
                  onChange(event.suggested_name)
                }}
              >
                <span className="block text-xs opacity-70">{event.short_date || event.date}{event.time ? ` · ${event.time}` : ""}</span>
                <span>{event.venue}</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
