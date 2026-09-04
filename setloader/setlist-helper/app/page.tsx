"use client"

import Link from "next/link"
import { FileText, Megaphone, ArrowRight } from "lucide-react"
import { BandToolsLogo } from "@/components/band-tools-logo"
import { GoogleAuth } from "@/components/google-auth"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const tools = [
  {
    id: "setlist-loader",
    title: "Setlist Loader",
    description:
      "Turn PDF set lists into Song Book Pro backups — match songs, map titles, and download ready-to-import sets.",
    href: "/setlist-loader",
    icon: FileText,
    accent: "from-indigo-500 to-violet-600",
    available: true,
  },
  {
    id: "flyer-agent",
    title: "Flyer Agent",
    description:
      "Sign in with Google, pick an upcoming gig, and generate or revise concert posters with an expert design agent.",
    href: "/flyers/agent",
    icon: Megaphone,
    accent: "from-violet-600 to-purple-700",
    available: true,
  },
  {
    id: "gig-flyers",
    title: "Gig Flyers",
    description:
      "Generate promoter-style flyer options from your gig calendar, review on the web, and approve via iMessage.",
    href: "/flyers/",
    icon: Megaphone,
    accent: "from-amber-500 to-orange-600",
    available: true,
    // Served by the flyers bridge via nginx — must be a full page load, not Next.js client nav.
    fullNavigation: true,
  },
]

export default function BandToolsHome() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50/80 via-background to-amber-50/40">
      <header className="border-b border-border/60 bg-card/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-6">
          <BandToolsLogo size="lg" />
        </div>
      </header>

      <main className="container mx-auto px-4 py-10">
        <div className="mx-auto max-w-3xl space-y-8">
          <section className="space-y-3 text-center sm:text-left">
            <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Your band&apos;s toolkit
            </h1>
            <p className="text-lg text-muted-foreground">
              Set lists, flyers, and more — built for musicians who play out.
            </p>
          </section>

          <section className="max-w-md">
            <GoogleAuth />
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            {tools.map((tool) => {
              const Icon = tool.icon
              return (
                <Card
                  key={tool.id}
                  className="group relative overflow-hidden border-border/80 transition-shadow hover:shadow-md"
                >
                  <div
                    className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${tool.accent}`}
                  />
                  <CardHeader className="pb-3">
                    <div
                      className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${tool.accent} text-white shadow-sm`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-xl">{tool.title}</CardTitle>
                    <CardDescription className="text-sm leading-relaxed">
                      {tool.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button asChild className="w-full gap-2 group-hover:gap-3 transition-all">
                      {"fullNavigation" in tool && tool.fullNavigation ? (
                        <a href={tool.href}>
                          Open {tool.title}
                          <ArrowRight className="h-4 w-4" />
                        </a>
                      ) : (
                        <Link href={tool.href}>
                          Open {tool.title}
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              )
            })}
          </section>
        </div>
      </main>

      <footer className="container mx-auto px-4 py-8 text-center text-sm text-muted-foreground">
        Band Tools
      </footer>
    </div>
  )
}
