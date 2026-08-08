import { useCallback, useState, type ReactNode } from "react";
import Modal from "./Modal";
import { ConfirmCtx, type ConfirmOptions } from "./confirmContext";

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<
    (ConfirmOptions & { resolve: (v: boolean) => void }) | null
  >(null);

  const confirm = useCallback(
    (opts: ConfirmOptions) =>
      new Promise<boolean>((resolve) => setState({ ...opts, resolve })),
    [],
  );

  const close = (value: boolean) => {
    state?.resolve(value);
    setState(null);
  };

  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Modal open={!!state} onClose={() => close(false)} title={state?.title ?? "Are you sure?"}>
        <p className="text-[14px] leading-relaxed text-ink-muted">{state?.message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={() => close(false)} className="btn-ghost px-3 py-2">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => close(true)}
            className={`btn-primary px-4 py-2 ${state?.danger ? "underline decoration-2 underline-offset-4" : ""}`}
          >
            {state?.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </Modal>
    </ConfirmCtx.Provider>
  );
}
