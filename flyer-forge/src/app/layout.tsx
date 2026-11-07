import { Suspense } from "react";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { AppNav } from "@/components/app-nav";
import { googleFontsHref } from "@/lib/fonts";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Gig Flyer Studio",
  description: "Design gig flyers from your band's real photos and logos, rooted in print traditions.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={googleFontsHref()} />
      </head>
      <body className="flex min-h-full flex-col">
        <Suspense fallback={<div className="h-14 border-b border-border/60" />}>
          <AppNav />
        </Suspense>
        <main className="flex flex-1 flex-col">{children}</main>
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
