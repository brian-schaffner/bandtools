import Link from "next/link"
import { BandToolsLogo } from "@/components/band-tools-logo"
import { cn } from "@/lib/utils"

interface BandToolsShellProps {
  children: React.ReactNode
  className?: string
  showBack?: boolean
}

export function BandToolsShell({ children, className, showBack = false }: BandToolsShellProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50/80 via-background to-amber-50/40">
      <header className="border-b border-border/60 bg-card/80 backdrop-blur-sm">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <Link href="/" className="transition-opacity hover:opacity-90">
            <BandToolsLogo size="sm" />
          </Link>
          {showBack && (
            <Link
              href="/"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              ← All tools
            </Link>
          )}
        </div>
      </header>
      <main className={cn("container mx-auto px-4 py-8", className)}>{children}</main>
    </div>
  )
}
