import { z } from "zod";
import { aiEnabled, callClaude, extractJson, HARD_RULES, rulebookText } from "@/lib/ai";
import { jsonError } from "@/lib/repo";
import { BriefSchema } from "@/lib/spec";
import type { Critique, CritiqueIssue } from "@/lib/types";
import { consumeQuota, requireViewer } from "@/lib/guard";

const Body = z.object({
  image: z.string().max(3_000_000),
  brief: BriefSchema,
  checks: z.array(z.string()).max(40).default([]),
});

export async function POST(req: Request) {
  const viewer = await requireViewer(req);
  if (viewer instanceof Response) return viewer;
  if (!aiEnabled()) return jsonError("no-key", 503);
  const overQuota = await consumeQuota(viewer, "ai");
  if (overQuota) return overQuota;
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError("Invalid critique request");
  const { image, brief, checks } = parsed.data;
  const m = /^data:(image\/(?:jpeg|png));base64,(.+)$/.exec(image);
  if (!m) return jsonError("Expected a JPEG or PNG data URL");
  const rules = await rulebookText();

  const system = `You are a blunt, experienced gig-poster designer reviewing a flyer before it goes to print.
Judge it against this rulebook:

${rules}

${HARD_RULES}

Focus on: does anything read as AI-generated; hierarchy (who, when, where in that order); legibility from ten feet; whether it feels rooted in a real print tradition; and composition.
Every fix must be something a layout edit can do (move, resize, recolour, change font, crop, treatment, swap photo). Never suggest generating imagery.`;

  const user = `Gig details that must be present and correct: ${JSON.stringify({ date: brief.date, venue: brief.venue, city: brief.city, time: brief.showTime, doors: brief.doors, price: brief.price, support: brief.support })}
Automated checks already found:
${checks.join("\n") || "(none)"}

Return JSON only:
{"score": 0-100, "summary": "two sentences", "issues": [{"severity": "pass|info|warn|fail", "area": "short label", "note": "what you see", "fix": "a concrete layout instruction, or omit"}]}
Include 3-7 issues and at least one "pass" for what works.`;

  try {
    const text = await callClaude(
      system,
      [
        { type: "image", source: { type: "base64", media_type: m[1], data: m[2] } },
        { type: "text", text: user },
      ],
      2000,
    );
    const out = extractJson<{ score: number; summary: string; issues: CritiqueIssue[] }>(text);
    const critique: Critique = {
      source: "ai",
      score: Math.max(0, Math.min(100, Math.round(Number(out.score) || 0))),
      summary: String(out.summary ?? "").slice(0, 500),
      issues: (out.issues ?? []).slice(0, 10).map((i) => ({
        severity: (["pass", "info", "warn", "fail"].includes(i.severity) ? i.severity : "info") as CritiqueIssue["severity"],
        area: String(i.area ?? "").slice(0, 60),
        note: String(i.note ?? "").slice(0, 400),
        ...(i.fix ? { fix: String(i.fix).slice(0, 300) } : {}),
      })),
      createdAt: new Date().toISOString(),
    };
    return Response.json(critique);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "AI request failed", 502);
  }
}
