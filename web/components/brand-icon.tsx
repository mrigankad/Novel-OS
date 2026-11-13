import { clsx } from "clsx";
import { Bot, Clapperboard, Plug } from "lucide-react";

/**
 * Marks for model providers and connected tools (LobeHub Icons, MIT; see
 * public/brands/NOTICE.txt). Static SVGs in /public, so they're cached and
 * never bloat the JS bundle.
 */
const FILES: Record<string, string> = {
  // model providers
  ollama: "ollama", ollama_cloud: "ollama",
  claude_cli: "claudecode-color", anthropic: "claude-color",
  openai: "openai", azure: "azure-color", bedrock: "bedrock-color", aws: "aws-color",
  gemini: "gemini-color", vertex: "vertexai-color",
  openrouter: "openrouter", groq: "groq", deepseek: "deepseek-color", mistral: "mistral-color",
  xai: "xai", perplexity: "perplexity-color", together: "together-color", fireworks: "fireworks-color",
  nvidia: "nvidia-color", kimi: "kimi-color", moonshot: "kimi-color", lmstudio: "lmstudio",
  // image generation
  runway: "runway", nanobanana: "nanobanana-color",
  // tools that connect over MCP / files
  claude_code: "claudecode-color", codex: "codex-color", cursor: "cursor",
  copilot: "githubcopilot", windsurf: "windsurf", cline: "cline", obsidian: "obsidian-color",
};

export const BRAND_LABELS: Record<string, string> = {
  ollama: "Ollama", ollama_cloud: "Ollama Cloud", claude_cli: "Claude Code", anthropic: "Anthropic",
  openai: "OpenAI", azure: "Azure OpenAI", bedrock: "AWS Bedrock", gemini: "Google Gemini",
  openrouter: "OpenRouter", groq: "Groq", deepseek: "DeepSeek", mistral: "Mistral", xai: "xAI Grok",
  perplexity: "Perplexity", together: "Together AI", fireworks: "Fireworks", nvidia: "NVIDIA NIM",
  kimi: "Kimi", lmstudio: "LM Studio", runway: "Runway", higgsfield: "Higgsfield", nanobanana: "Nano Banana", openai_compatible: "Custom endpoint",
  claude_code: "Claude Code", codex: "Codex", cursor: "Cursor", copilot: "GitHub Copilot",
  windsurf: "Windsurf", cline: "Cline", obsidian: "Obsidian",
};

const SIZES = { xs: "h-4 w-4", sm: "h-5 w-5", md: "h-6 w-6", lg: "h-8 w-8" } as const;
const TILES = { xs: "h-6 w-6", sm: "h-8 w-8", md: "h-10 w-10", lg: "h-12 w-12" } as const;

export function BrandIcon({
  id, size = "sm", tile = false, className,
}: { id: string; size?: keyof typeof SIZES; tile?: boolean; className?: string }) {
  const file = FILES[id];
  const glyph = file ? (
    <img src={`/brands/${file}.svg`} alt="" aria-hidden className={clsx(SIZES[size], "shrink-0 object-contain")} />
  ) : id === "higgsfield" ? (
    // No official mark available in the icon set; a neutral glyph beats a fake logo.
    <Clapperboard className={clsx(SIZES[size], "shrink-0 text-body")} strokeWidth={1.75} aria-hidden />
  ) : id === "openai_compatible" ? (
    <Plug className={clsx(SIZES[size], "shrink-0 text-body")} strokeWidth={1.75} aria-hidden />
  ) : (
    <Bot className={clsx(SIZES[size], "shrink-0 text-body")} strokeWidth={1.75} aria-hidden />
  );
  if (!tile) return <span className={clsx("inline-flex", className)} title={BRAND_LABELS[id]}>{glyph}</span>;
  return (
    <span
      className={clsx("inline-flex shrink-0 items-center justify-center rounded-[10px] bg-paper ring-1 ring-rule", TILES[size], className)}
      title={BRAND_LABELS[id]}
    >
      {glyph}
    </span>
  );
}
