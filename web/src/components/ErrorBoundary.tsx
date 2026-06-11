import { Component, type ReactNode } from "react";

export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full items-center justify-center p-10">
          <div className="max-w-md rounded-xl border border-paper-line bg-paper-card p-8 text-center shadow-[var(--shadow-paper)]">
            <p className="font-display text-[22px] font-semibold text-ink-text">Something broke</p>
            <p className="mt-2 text-[14px] leading-relaxed text-ink-muted">
              An unexpected error occurred while rendering this view. Your saved work is safe.
            </p>
            <p className="mt-3 rounded-md bg-ink/5 px-3 py-2 font-mono text-[12px] text-ink-muted">
              {this.state.error.message}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="mt-5 rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
