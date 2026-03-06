"""
Novel OS - Token Management System

Handles all token budget concerns for LLM interactions:
- Token estimation (no external dependency)
- Context windowing (only include what fits)
- Chapter summarization (compress old chapters into short summaries)
- Chunked generation (split long chapters into scene-by-scene calls)
- Smart prompt trimming (gracefully cut context when too large)

Token limits for common NIM models:
    - Llama 3.1 8B/70B/405B: 128K context, but NIM API may cap output at ~4096
    - Mixtral 8x7B/8x22B: 32K-64K context
    - In practice, NIM free tier often caps at 4096 output tokens
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field


# ===== Token Estimation =====
# Rule of thumb: 1 token ≈ 4 characters in English, or ~0.75 words
# This avoids needing tiktoken or sentencepiece as a dependency

CHARS_PER_TOKEN = 4.0
WORDS_PER_TOKEN = 0.75


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. Conservative (slightly overestimates)."""
    if not text:
        return 0
    # Use character-based estimation (more reliable than word-based)
    char_estimate = len(text) / CHARS_PER_TOKEN
    # Cross-check with word estimate
    word_estimate = len(text.split()) / WORDS_PER_TOKEN
    # Take the higher (more conservative) estimate
    return int(max(char_estimate, word_estimate))


def estimate_tokens_for_messages(messages: List[Dict[str, str]]) -> int:
    """Estimate total tokens for a list of chat messages."""
    total = 0
    for msg in messages:
        # ~4 tokens overhead per message (role, formatting)
        total += 4
        total += estimate_tokens(msg.get("content", ""))
    # ~2 tokens for the reply priming
    total += 2
    return total


# ===== Model Token Limits =====

@dataclass
class ModelLimits:
    """Token limits for a specific model."""
    context_window: int      # Total input + output token budget
    max_output_tokens: int   # Max tokens the API will generate
    recommended_input: int   # Recommended max input to leave room for output

    @property
    def safe_input_limit(self) -> int:
        """Max input tokens that still leaves room for a full output."""
        return self.context_window - self.max_output_tokens


# Known limits for NIM models
# NIM API may impose its own caps on top of model limits
MODEL_LIMITS = {
    "llama-3.1-8b":    ModelLimits(context_window=128000, max_output_tokens=4096, recommended_input=8000),
    "llama-3.1-70b":   ModelLimits(context_window=128000, max_output_tokens=4096, recommended_input=12000),
    "llama-3.1-405b":  ModelLimits(context_window=128000, max_output_tokens=4096, recommended_input=12000),
    "mixtral-8x7b":    ModelLimits(context_window=32000,  max_output_tokens=4096, recommended_input=8000),
    "mixtral-8x22b":   ModelLimits(context_window=65000,  max_output_tokens=4096, recommended_input=12000),
    "nemotron-70b":    ModelLimits(context_window=128000, max_output_tokens=4096, recommended_input=12000),
    "qwen2.5-72b":     ModelLimits(context_window=128000, max_output_tokens=4096, recommended_input=12000),
}

DEFAULT_LIMITS = ModelLimits(context_window=32000, max_output_tokens=4096, recommended_input=8000)


def get_model_limits(model_name: str) -> ModelLimits:
    """Get token limits for a model."""
    return MODEL_LIMITS.get(model_name, DEFAULT_LIMITS)


# ===== Context Budget Manager =====

@dataclass
class ContextBudget:
    """
    Manages the token budget for a single LLM call.
    
    Divides the available input tokens into priority slots:
    - system_prompt: Agent system prompt (highest priority, never trimmed)
    - core_task: The main task instruction (high priority)
    - chapter_text: The chapter being written/edited (medium priority, can be chunked)
    - story_context: Characters, plot threads, style info (medium, can be summarized)
    - history: Previous chapters, timeline (lowest priority, aggressively trimmed)
    """
    total_input_budget: int
    system_prompt_tokens: int = 0
    core_task_tokens: int = 0
    
    # What remains after fixed allocations
    @property
    def remaining_budget(self) -> int:
        used = self.system_prompt_tokens + self.core_task_tokens
        return max(0, self.total_input_budget - used)
    
    def allocate(self, system_prompt: str, core_task_overhead: int = 500) -> Dict[str, int]:
        """
        Calculate token budgets for each context section.
        
        Returns dict with token budgets for:
        - chapter_text: budget for the actual chapter content
        - story_context: budget for characters, plot threads, style
        - history: budget for previous chapter summaries
        """
        self.system_prompt_tokens = estimate_tokens(system_prompt)
        self.core_task_tokens = core_task_overhead  # Formatting, instructions, etc.
        
        remaining = self.remaining_budget
        
        # Allocate remaining budget in priority order:
        # 50% for chapter text (the main content)
        # 30% for story context (characters, plots, style)
        # 20% for history (previous chapter summaries)
        return {
            "chapter_text": int(remaining * 0.50),
            "story_context": int(remaining * 0.30),
            "history": int(remaining * 0.20),
        }


# ===== Text Trimming Utilities =====

def trim_to_token_budget(text: str, max_tokens: int, strategy: str = "end") -> str:
    """
    Trim text to fit within a token budget.
    
    Strategies:
    - "end": Keep the beginning, cut the end (good for chapter drafts)
    - "start": Keep the end, cut the beginning (good for history/context)
    - "middle": Keep beginning and end, cut middle (good for long chapters)
    - "summary_hint": Add "[content trimmed]" marker where cut happens
    """
    current_tokens = estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    # Convert token budget to approximate character budget
    char_budget = int(max_tokens * CHARS_PER_TOKEN)
    
    if strategy == "end":
        trimmed = text[:char_budget]
        # Try to cut at a sentence boundary
        last_period = trimmed.rfind('. ')
        if last_period > char_budget * 0.8:  # Don't lose too much
            trimmed = trimmed[:last_period + 1]
        return trimmed + "\n\n[... content trimmed to fit token limit ...]"
    
    elif strategy == "start":
        trimmed = text[-char_budget:]
        # Try to cut at a sentence boundary
        first_period = trimmed.find('. ')
        if first_period > 0 and first_period < char_budget * 0.2:
            trimmed = trimmed[first_period + 2:]
        return "[... earlier content trimmed ...]\n\n" + trimmed
    
    elif strategy == "middle":
        half = char_budget // 2
        beginning = text[:half]
        ending = text[-half:]
        # Clean up at sentence boundaries
        last_period = beginning.rfind('. ')
        if last_period > half * 0.7:
            beginning = beginning[:last_period + 1]
        first_period = ending.find('. ')
        if first_period > 0 and first_period < half * 0.3:
            ending = ending[first_period + 2:]
        return beginning + "\n\n[... middle section trimmed ...]\n\n" + ending
    
    else:  # summary_hint
        return trim_to_token_budget(text, max_tokens, strategy="end")


def trim_characters_context(characters: list, max_tokens: int, current_chapter: int) -> str:
    """Build character context that fits within token budget, prioritizing relevance."""
    if not characters:
        return "No characters defined yet.\n"
    
    # Sort by relevance: recent appearances first, then by role priority
    role_priority = {"protagonist": 0, "antagonist": 1, "supporting": 2, "minor": 3}
    
    sorted_chars = sorted(characters, key=lambda c: (
        role_priority.get(c.role, 4),
        -(c.last_appearance_chapter or 0),  # Recent appearances first
    ))
    
    result_lines = []
    tokens_used = 0
    
    for char in sorted_chars:
        # Build a compact character entry
        entry = f"**{char.full_name}** ({char.role})"
        details = []
        if char.current_location:
            details.append(f"Location: {char.current_location}")
        if char.emotional_state:
            details.append(f"Emotion: {char.emotional_state}")
        if char.arc_stage:
            details.append(f"Arc: {char.arc_stage} ({char.arc_progress}%)")
        
        if details:
            entry += " — " + ", ".join(details)
        entry += "\n"
        
        entry_tokens = estimate_tokens(entry)
        if tokens_used + entry_tokens > max_tokens:
            result_lines.append(f"[+ {len(sorted_chars) - len(result_lines)} more characters omitted for brevity]\n")
            break
        
        result_lines.append(entry)
        tokens_used += entry_tokens
    
    return "".join(result_lines)


def trim_plot_threads_context(threads: list, max_tokens: int) -> str:
    """Build plot thread context that fits within token budget."""
    if not threads:
        return "No active plot threads.\n"
    
    # Sort by priority (higher first)
    sorted_threads = sorted(threads, key=lambda t: -t.priority)
    
    result_lines = []
    tokens_used = 0
    
    for thread in sorted_threads:
        # Compact thread description
        desc = thread.description[:100] + "..." if len(thread.description) > 100 else thread.description
        entry = f"- [{thread.thread_type.upper()}] **{thread.name}**: {desc}\n"
        
        entry_tokens = estimate_tokens(entry)
        if tokens_used + entry_tokens > max_tokens:
            result_lines.append(f"[+ {len(sorted_threads) - len(result_lines)} more threads omitted]\n")
            break
        
        result_lines.append(entry)
        tokens_used += entry_tokens
    
    return "".join(result_lines)


# ===== Chapter Summarization =====

class ChapterSummarizer:
    """
    Manages chapter summaries to avoid sending full chapter text as context.
    
    Strategy:
    - Chapters 1-2 back: Include full summary (2-3 paragraphs)
    - Chapters 3-5 back: Include short summary (1 paragraph)
    - Chapters 6+: Include one-line summary only
    - Store summaries in outputs/state/chapter_summaries.json
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.summaries_path = self.project_path / "outputs" / "state" / "chapter_summaries.json"
        self.summaries: Dict[str, Dict[str, str]] = {}
        self._load_summaries()
    
    def _load_summaries(self):
        """Load existing chapter summaries from disk."""
        if self.summaries_path.exists():
            try:
                with open(self.summaries_path, 'r', encoding='utf-8') as f:
                    self.summaries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.summaries = {}
    
    def _save_summaries(self):
        """Save chapter summaries to disk."""
        self.summaries_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.summaries_path, 'w', encoding='utf-8') as f:
            json.dump(self.summaries, f, indent=2)
    
    def set_summary(self, chapter_number: int, full_summary: str, short_summary: str, one_liner: str):
        """Store summaries at different detail levels for a chapter."""
        self.summaries[str(chapter_number)] = {
            "full": full_summary,
            "short": short_summary,
            "one_liner": one_liner,
        }
        self._save_summaries()
    
    def generate_summary_from_text(self, chapter_text: str, chapter_number: int) -> Dict[str, str]:
        """
        Generate summaries from chapter text locally (no API call).
        
        This is a simple extractive approach - takes the first few sentences
        and key paragraphs. For better summaries, use generate_summary_with_ai().
        """
        sentences = re.split(r'(?<=[.!?])\s+', chapter_text.strip())
        sentences = [s for s in sentences if len(s) > 20]  # Filter out fragments
        
        if not sentences:
            return {
                "full": f"Chapter {chapter_number} content.",
                "short": f"Chapter {chapter_number}.",
                "one_liner": f"Chapter {chapter_number}.",
            }
        
        # Full summary: first 5 sentences + last 2 sentences
        full_parts = sentences[:5]
        if len(sentences) > 7:
            full_parts.extend(sentences[-2:])
        full_summary = " ".join(full_parts)
        
        # Short summary: first 2 sentences
        short_summary = " ".join(sentences[:2])
        
        # One-liner: first sentence, truncated
        one_liner = sentences[0][:150]
        if len(sentences[0]) > 150:
            one_liner += "..."
        
        result = {
            "full": full_summary,
            "short": short_summary,
            "one_liner": one_liner,
        }
        
        self.set_summary(chapter_number, **result)
        return result
    
    def get_context_for_chapter(self, target_chapter: int, max_tokens: int) -> str:
        """
        Build a history context string for a target chapter, within token budget.
        
        Uses progressively shorter summaries for older chapters:
        - N-1, N-2: full summary
        - N-3 to N-5: short summary  
        - N-6+: one-liner
        """
        if not self.summaries:
            return ""
        
        context_lines = ["### Previous Chapter Summaries\n"]
        tokens_used = estimate_tokens(context_lines[0])
        
        # Process chapters from most recent to oldest
        for ch_num in range(target_chapter - 1, 0, -1):
            ch_key = str(ch_num)
            if ch_key not in self.summaries:
                continue
            
            distance = target_chapter - ch_num
            summary_data = self.summaries[ch_key]
            
            # Choose detail level based on distance
            if distance <= 2:
                summary = summary_data.get("full", summary_data.get("short", ""))
                label = "full"
            elif distance <= 5:
                summary = summary_data.get("short", summary_data.get("one_liner", ""))
                label = "short"
            else:
                summary = summary_data.get("one_liner", "")
                label = "brief"
            
            if not summary:
                continue
            
            entry = f"\n**Chapter {ch_num}** ({label}): {summary}\n"
            entry_tokens = estimate_tokens(entry)
            
            if tokens_used + entry_tokens > max_tokens:
                context_lines.append(f"\n[Earlier chapters omitted to fit token budget]\n")
                break
            
            context_lines.append(entry)
            tokens_used += entry_tokens
        
        return "".join(context_lines)


# ===== Chunked Chapter Generation =====

class ChunkedWriter:
    """
    Handles writing long chapters by splitting them into scene-by-scene chunks.
    
    Problem: A 2500-word chapter ≈ 3300 tokens. With 4096 max output tokens,
    that barely fits. A 5000-word chapter won't fit at all.
    
    Solution: Split the chapter into 2-4 scenes, generate each separately,
    then stitch them together. Each scene gets ~1000-1500 words.
    """
    
    def __init__(self, agent_runner, max_output_tokens: int = 4096, custom_word_target: Optional[int] = None):
        self.agent_runner = agent_runner
        self.max_output_tokens = max_output_tokens
        # A safe target: leave ~500 tokens margin for state updates
        if custom_word_target:
            self.safe_word_target = custom_word_target
        else:
            self.safe_word_target = int((max_output_tokens - 500) * WORDS_PER_TOKEN)
    
    def needs_chunking(self, target_word_count: int) -> bool:
        """Check if the target word count requires chunked generation."""
        return target_word_count > self.safe_word_target
    
    def calculate_chunks(self, target_word_count: int) -> List[Dict[str, Any]]:
        """
        Calculate how to split a chapter into chunks.
        
        Returns list of chunk specs: [{"chunk": 1, "words": 1200, "role": "opening"}, ...]
        """
        if not self.needs_chunking(target_word_count):
            return [{"chunk": 1, "words": target_word_count, "role": "complete"}]
        
        # Calculate number of chunks needed
        num_chunks = max(2, -(-target_word_count // self.safe_word_target))  # Ceiling division
        words_per_chunk = target_word_count // num_chunks
        
        chunks = []
        roles = {
            0: "opening",
            num_chunks - 1: "closing",
        }
        
        for i in range(num_chunks):
            # Give slightly more words to opening and closing
            if i == 0 or i == num_chunks - 1:
                chunk_words = words_per_chunk + 100
            else:
                chunk_words = words_per_chunk
            
            chunks.append({
                "chunk": i + 1,
                "total_chunks": num_chunks,
                "words": chunk_words,
                "role": roles.get(i, "middle"),
            })
        
        return chunks
    
    def build_chunk_prompt(
        self,
        base_prompt: str,
        chunk_spec: Dict[str, Any],
        previous_chunks: List[str],
    ) -> str:
        """
        Build a prompt for generating one chunk of a chapter.
        
        Includes the tail end of the previous chunk for continuity.
        """
        chunk_num = chunk_spec["chunk"]
        total = chunk_spec["total_chunks"]
        words = chunk_spec["words"]
        role = chunk_spec["role"]
        
        continuity_context = ""
        if previous_chunks:
            # Include last ~300 words of previous chunk for continuity
            prev_text = previous_chunks[-1]
            prev_words = prev_text.split()
            if len(prev_words) > 300:
                continuity_text = " ".join(prev_words[-300:])
            else:
                continuity_text = prev_text
            continuity_context = f"""
## Previous Section (for continuity - DO NOT repeat this text)

```
...{continuity_text}
```

Continue seamlessly from where the previous section ended.
"""
        
        role_instructions = {
            "opening": "This is the OPENING section. Start with a strong hook. Establish the scene and characters.",
            "middle": "This is a MIDDLE section. Continue the action/conflict. Maintain momentum.",
            "closing": "This is the CLOSING section. Build to the chapter's climax and end with a compelling hook for the next chapter.",
            "complete": "Write the complete chapter.",
        }
        
        chunk_header = f"""
## ⚠️ CHUNKED GENERATION: Section {chunk_num} of {total}

**Target for this section**: ~{words} words
**Section role**: {role_instructions.get(role, role)}

{continuity_context}
"""
        
        # Insert chunk header right before the writing instruction
        return base_prompt + "\n" + chunk_header
    
    def generate_chapter_chunked(
        self,
        base_prompt: str,
        target_word_count: int,
        agent_name: str = "scribe",
        temperature: float = 0.8,
        stream: bool = True,
    ) -> str:
        """
        Generate a full chapter using chunked generation.
        
        Returns the complete chapter text (all chunks stitched together).
        """
        chunks_spec = self.calculate_chunks(target_word_count)
        
        if len(chunks_spec) == 1 and chunks_spec[0]["role"] == "complete":
            # No chunking needed, generate normally
            return self.agent_runner.run_agent(
                agent_name=agent_name,
                task_prompt=base_prompt,
                temperature=temperature,
                max_tokens=self.max_output_tokens,
                stream=stream,
            )
        
        print(f"\n📝 Chapter will be generated in {len(chunks_spec)} sections")
        print(f"   (Target: {target_word_count} words, ~{target_word_count // len(chunks_spec)} words per section)")
        
        generated_chunks = []
        
        for chunk_spec in chunks_spec:
            chunk_num = chunk_spec["chunk"]
            total = chunk_spec["total_chunks"]
            
            print(f"\n--- Section {chunk_num}/{total} ({chunk_spec['role']}) ---")
            
            chunk_prompt = self.build_chunk_prompt(base_prompt, chunk_spec, generated_chunks)
            
            chunk_text = self.agent_runner.run_agent(
                agent_name=agent_name,
                task_prompt=chunk_prompt,
                temperature=temperature,
                max_tokens=self.max_output_tokens,
                stream=stream,
            )
            
            generated_chunks.append(chunk_text)
            word_count = len(chunk_text.split())
            print(f"\n   ✅ Section {chunk_num}: {word_count} words")
        
        # Stitch chunks together
        full_chapter = "\n\n".join(generated_chunks)
        total_words = len(full_chapter.split())
        print(f"\n📊 Total chapter: {total_words} words (target: {target_word_count})")
        
        return full_chapter


# ===== Smart Prompt Builder =====

class SmartPromptBuilder:
    """
    Builds prompts that respect token budgets.
    
    Automatically trims and prioritizes content to fit within model limits.
    """
    
    def __init__(self, model_name: str = "llama-3.1-70b"):
        self.limits = get_model_limits(model_name)
        self.model_name = model_name
    
    def build_writing_prompt(
        self,
        system_prompt: str,
        chapter_info: str,
        characters_context: str,
        plot_threads_context: str,
        style_context: str,
        history_context: str,
        writing_instructions: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a writing prompt that fits within the model's token budget.
        
        Returns:
            (final_prompt, stats_dict) where stats_dict has token usage info
        """
        budget = ContextBudget(total_input_budget=self.limits.recommended_input)
        allocations = budget.allocate(system_prompt, core_task_overhead=estimate_tokens(chapter_info + writing_instructions))
        
        stats = {
            "model": self.model_name,
            "total_budget": self.limits.recommended_input,
            "system_prompt_tokens": budget.system_prompt_tokens,
            "core_task_tokens": budget.core_task_tokens,
            "allocations": allocations,
        }
        
        # Trim each section to its budget
        trimmed_chars = trim_to_token_budget(characters_context, allocations["story_context"] // 2, "end")
        trimmed_plots = trim_to_token_budget(plot_threads_context, allocations["story_context"] // 2, "end")
        trimmed_history = trim_to_token_budget(history_context, allocations["history"], "start")
        trimmed_style = trim_to_token_budget(style_context, 200, "end")  # Style is always short
        
        # Assemble final prompt
        final_prompt = f"""{chapter_info}

## Story Context

### Characters
{trimmed_chars}

### Active Plot Threads
{trimmed_plots}

### Style Profile
{trimmed_style}

{trimmed_history}

{writing_instructions}"""
        
        final_tokens = estimate_tokens(system_prompt) + estimate_tokens(final_prompt)
        stats["final_input_tokens"] = final_tokens
        stats["output_budget_remaining"] = self.limits.context_window - final_tokens
        stats["fits_in_budget"] = final_tokens <= self.limits.recommended_input
        
        if not stats["fits_in_budget"]:
            print(f"⚠️  Prompt ({final_tokens} tokens) exceeds recommended budget ({self.limits.recommended_input})")
            print(f"   Still within absolute limit: {final_tokens < self.limits.safe_input_limit}")
        
        return final_prompt, stats
    
    def build_edit_prompt(
        self,
        system_prompt: str,
        chapter_text: str,
        edit_instructions: str,
        style_context: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build an editing prompt. The chapter text gets priority.
        
        If chapter is too long, it's trimmed with middle strategy
        (keep beginning and end, which are most important for editing).
        """
        total_budget = self.limits.recommended_input
        system_tokens = estimate_tokens(system_prompt)
        instruction_tokens = estimate_tokens(edit_instructions + style_context)
        
        chapter_budget = total_budget - system_tokens - instruction_tokens - 200  # 200 margin
        
        trimmed_chapter = trim_to_token_budget(chapter_text, chapter_budget, "middle")
        
        stats = {
            "model": self.model_name,
            "original_chapter_tokens": estimate_tokens(chapter_text),
            "trimmed_chapter_tokens": estimate_tokens(trimmed_chapter),
            "was_trimmed": estimate_tokens(chapter_text) > chapter_budget,
        }
        
        final_prompt = f"""{edit_instructions}

## Chapter Text

{trimmed_chapter}

{style_context}
"""
        
        stats["final_input_tokens"] = system_tokens + estimate_tokens(final_prompt)
        return final_prompt, stats
    
    def build_validation_prompt(
        self,
        system_prompt: str,
        chapter_text: str,
        story_state_context: str,
        validation_instructions: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a validation prompt. Balances chapter text vs story state.
        """
        total_budget = self.limits.recommended_input
        system_tokens = estimate_tokens(system_prompt)
        instruction_tokens = estimate_tokens(validation_instructions)
        
        remaining = total_budget - system_tokens - instruction_tokens - 200
        
        # 60% to chapter, 40% to story state
        chapter_budget = int(remaining * 0.6)
        state_budget = int(remaining * 0.4)
        
        trimmed_chapter = trim_to_token_budget(chapter_text, chapter_budget, "middle")
        trimmed_state = trim_to_token_budget(story_state_context, state_budget, "end")
        
        stats = {
            "model": self.model_name,
            "original_chapter_tokens": estimate_tokens(chapter_text),
            "chapter_budget": chapter_budget,
            "state_budget": state_budget,
        }
        
        final_prompt = f"""{validation_instructions}

## Chapter Text to Validate

{trimmed_chapter}

## Story State Context

{trimmed_state}
"""
        
        stats["final_input_tokens"] = system_tokens + estimate_tokens(final_prompt)
        return final_prompt, stats


# ===== AI-Powered Summarization =====

def build_summarize_prompt(chapter_text: str, chapter_number: int) -> str:
    """
    Build a prompt to ask the AI to summarize a chapter.
    Used to generate chapter summaries for the history context.
    """
    # Trim chapter text if needed (for the summarization call itself)
    trimmed = trim_to_token_budget(chapter_text, 6000, "middle")
    
    return f"""Summarize Chapter {chapter_number} at three detail levels.

## Chapter Text

{trimmed}

## Required Output Format (respond ONLY in this JSON format):

```json
{{
    "full": "A 3-4 sentence summary covering the main events, character developments, and key plot points.",
    "short": "A 1-2 sentence summary of the most important event.",
    "one_liner": "A single phrase describing this chapter (under 15 words)."
}}
```
"""


# ===== Convenience Function =====

def print_token_report(label: str, stats: Dict[str, Any]):
    """Print a human-readable token usage report."""
    print(f"\n📊 Token Report: {label}")
    print(f"   Model: {stats.get('model', 'unknown')}")
    print(f"   Input tokens: {stats.get('final_input_tokens', '?')}")
    if 'output_budget_remaining' in stats:
        print(f"   Output budget: {stats['output_budget_remaining']} tokens")
    if 'was_trimmed' in stats:
        if stats['was_trimmed']:
            print(f"   ⚠️  Content was trimmed to fit budget")
            print(f"   Original: {stats.get('original_chapter_tokens', '?')} → Trimmed: {stats.get('trimmed_chapter_tokens', '?')}")
        else:
            print(f"   ✅ Content fit within budget (no trimming needed)")
    if stats.get('fits_in_budget') is False:
        print(f"   ⚠️  Prompt exceeds recommended budget!")
