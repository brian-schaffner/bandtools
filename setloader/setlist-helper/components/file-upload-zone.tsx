"use client"

import type React from "react"

import { useCallback, useState, useRef } from "react"
import { Upload, File } from "lucide-react"
import { cn } from "@/lib/utils"

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void
  accept?: string
  label?: string
  disabled?: boolean
}

export function FileUploadZone({ onFileSelect, accept, label, disabled }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      if (!disabled) {
        setIsDragging(true)
      }
    },
    [disabled],
  )

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)

      if (disabled) return

      const files = Array.from(e.dataTransfer.files)
      if (files.length > 0) {
        const file = files[0]
        setSelectedFile(file)
        onFileSelect(file)
      }
    },
    [disabled, onFileSelect],
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files && files.length > 0) {
        const file = files[0]
        setSelectedFile(file)
        onFileSelect(file)
      }
    },
    [onFileSelect],
  )

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "relative rounded-lg border-2 border-dashed transition-colors",
        isDragging && !disabled && "border-primary bg-primary/5",
        !isDragging && !disabled && "border-border hover:border-primary/50 hover:bg-muted/50",
        disabled && "cursor-not-allowed opacity-50",
        !disabled && "cursor-pointer",
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileInput}
        disabled={disabled}
        className="absolute inset-0 z-10 cursor-pointer opacity-0"
      />
      <div className="flex flex-col items-center justify-center gap-3 px-6 py-12">
        {selectedFile ? (
          <>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <File className="h-6 w-6 text-primary" />
            </div>
            <div className="text-center">
              <p className="font-medium text-foreground">{selectedFile.name}</p>
              <p className="text-sm text-muted-foreground">{(selectedFile.size / 1024).toFixed(2)} KB</p>
            </div>
          </>
        ) : (
          <>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Upload className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="text-center">
              <p className="font-medium text-foreground">{label || "Drop your file here or click to browse"}</p>
              <p className="text-sm text-muted-foreground">
                {accept ? `Supported formats: ${accept}` : "All file types supported"}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
