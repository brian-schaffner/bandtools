/** Fixed corner stamp — matches Gig Flyers HTML UI build label. */
export function BuildStamp() {
  const label = process.env.NEXT_PUBLIC_BANDTOOLS_BUILD_LABEL?.trim()
  const builtAt = process.env.NEXT_PUBLIC_BANDTOOLS_BUILT_AT?.trim()
  const deployEnv = process.env.NEXT_PUBLIC_BANDTOOLS_DEPLOY_ENV?.trim()

  if (!label) {
    return null
  }

  const envBit = deployEnv && deployEnv !== "local" ? ` · ${deployEnv}` : ""
  const when = builtAt ? builtAt.replace("T", " ").replace("Z", " UTC") : ""
  const text = when ? `Build ${label}${envBit} · ${when}` : `Build ${label}${envBit}`
  const title = `git ${label} · built ${builtAt || "unknown"}${deployEnv ? ` · ${deployEnv}` : ""}`

  return (
    <footer
      className="pointer-events-auto fixed bottom-[max(0.35rem,env(safe-area-inset-bottom))] right-[max(0.5rem,env(safe-area-inset-right))] z-[9999] max-w-[min(96vw,22rem)] truncate rounded-md bg-slate-900/90 px-2 py-1 font-mono text-[0.62rem] leading-tight text-slate-200 shadow-md"
      title={title}
    >
      {text}
    </footer>
  )
}
