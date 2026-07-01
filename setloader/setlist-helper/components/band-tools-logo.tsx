import { cn } from "@/lib/utils"

interface BandToolsLogoProps {
  className?: string
  size?: "sm" | "md" | "lg"
  showWordmark?: boolean
}

const sizes = {
  sm: { icon: 36, title: "text-lg", tagline: "text-xs" },
  md: { icon: 48, title: "text-2xl", tagline: "text-sm" },
  lg: { icon: 64, title: "text-3xl", tagline: "text-base" },
}

export function BandToolsLogo({
  className,
  size = "md",
  showWordmark = true,
}: BandToolsLogoProps) {
  const s = sizes[size]

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg
        width={s.icon}
        height={s.icon}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
        className="shrink-0"
      >
        <rect width="64" height="64" rx="16" fill="url(#bt-gradient)" />
        <path
          d="M18 42V22l14 10 14-10v20"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="32" cy="32" r="4" fill="white" fillOpacity="0.9" />
        <path
          d="M44 18h6v6M44 18l8 8"
          stroke="#FCD34D"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <defs>
          <linearGradient id="bt-gradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6366F1" />
            <stop offset="1" stopColor="#D97706" />
          </linearGradient>
        </defs>
      </svg>
      {showWordmark && (
        <div>
          <div className={cn("font-bold tracking-tight text-foreground", s.title)}>
            Band Tools
          </div>
          <div className={cn("text-muted-foreground", s.tagline)}>
            For gigging musicians
          </div>
        </div>
      )}
    </div>
  )
}
