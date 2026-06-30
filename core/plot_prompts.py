"""Format plot threads (including subplots) for agent prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from state_manager import PlotThread


def format_plot_thread_line(thread: "PlotThread", *, max_desc: int = 200) -> str:
    """One plot thread block for inclusion in LLM prompts."""
    desc = (thread.description or "").strip()
    if len(desc) > max_desc:
        desc = desc[: max_desc - 3].rstrip() + "..."
    line = f"- **{thread.name}** ({thread.thread_type})"
    if desc:
        line += f": {desc}"
    subs = [s.strip() for s in (thread.subplots or []) if s.strip()]
    if subs:
        line += "\n  Subplots:\n" + "\n".join(f"  - {s}" for s in subs)
    return line


def format_plot_threads_block(
    threads: List["PlotThread"],
    *,
    heading: str = "### Active Plot Threads",
    max_threads: int = 12,
    max_desc: int = 200,
) -> str:
    if not threads:
        return f"{heading}\n(none)\n"
    shown = threads[:max_threads]
    lines = [heading]
    for thread in shown:
        lines.append(format_plot_thread_line(thread, max_desc=max_desc))
    if len(threads) > max_threads:
        lines.append(f"- … and {len(threads) - max_threads} more")
    return "\n".join(lines) + "\n"
