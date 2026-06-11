import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import Modal from "./Modal";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
}

const ConfirmCtx = createContext<(opts: ConfirmOptions) => Promise<boolean>>(
  async () => true,
);

export function useConfirm() {
  return useContext(ConfirmCtx);
}

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
          <button
            onClick={() => close(false)}
            className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5"
          >
            Cancel
          </button>
          <button
            onClick={() => close(true)}
            className={`rounded-lg px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors ${
              state?.danger ? "bg-red-600 hover:bg-red-700" : "bg-ink hover:bg-ink-800"
            }`}
          >
            {state?.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </Modal>
    </ConfirmCtx.Provider>
  );
}
