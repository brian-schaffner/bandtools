import "server-only";
import { listRefs } from "./repo";

export const AI_MODEL = process.env.ANTHROPIC_MODEL?.trim() || "claude-sonnet-5-5";

export function aiEnabled() {
  return (process.env.ANTHROPIC_API_KEY?.trim() ?? "") !== "";
}

type Block =
  | { type: "text"; text: string }
  | { type: "image"; source: { type: "base64"; media_type: string; data: string } };

export async function callClaude(system: string, content: Block[], maxTokens = 4000): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": process.env.ANTHROPIC_API_KEY!.trim(),
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: AI_MODEL,
      max_tokens: maxTokens,
      system,
      messages: [{ role: "user", content }],
    }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Claude request failed (${res.status}): ${detail.slice(0, 300)}`);
  }
  const body = (await res.json()) as { content: { type: string; text?: string }[] };
  return body.content
    .filter((b) => b.type === "text")
    .map((b) => b.text ?? "")
    .join("\n");
}

export function extractJson<T = unknown>(text: string): T {
  const fence = /```(?:json)?\s*([\s\S]*?)```/.exec(text);
  const src = fence ? fence[1] : text;
  const start = src.indexOf("{");
  if (start < 0) throw new Error("Model did not return JSON");
  let depth = 0;
  let inStr = false;
  for (let i = start; i < src.length; i++) {
    const ch = src[i];
    if (inStr) {
      if (ch === "\\") i++;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === "{") depth++;
    else if (ch === "}" && --depth === 0) return JSON.parse(src.slice(start, i + 1)) as T;
  }
  throw new Error("Model returned incomplete JSON");
}

export async function rulebookText(): Promise<string> {
  const refs = await listRefs();
  const avoid = refs.filter((r) => r.kind === "avoid");
  const inspire = refs.filter((r) => r.kind === "inspire");
  const fmt = (r: (typeof refs)[number]) => `- ${r.title}${r.recipeId ? ` [recipe: ${r.recipeId}]` : ""}: ${r.traits.join("; ")}`;
  return [
    "WHAT MAKES A FLYER LOOK AI-GENERATED (never do these):",
    ...avoid.map(fmt),
    "",
    "TRADITIONAL REFERENCES TO DRAW FROM:",
    ...inspire.map(fmt),
  ].join("\n");
}

export const HARD_RULES = `Hard rules that are never negotiable:
- The band's photos and logos are placed exactly as uploaded. They may be cropped, scaled uniformly, rotated, masked and recoloured, but never stretched, redrawn, regenerated or retouched.
- No generated people, hands, instruments or lettering. All text is set in real fonts by the layout engine.
- No glow, bevel, chrome, drop shadow or gradient effects on type. Flat inks only.`;
