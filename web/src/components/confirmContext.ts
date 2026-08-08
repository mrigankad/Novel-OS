import { createContext, useContext } from "react";

export interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
}

/** Split from Confirm.tsx so that file exports only components (Fast Refresh). */
export const ConfirmCtx = createContext<(opts: ConfirmOptions) => Promise<boolean>>(
  async () => true,
);

export function useConfirm() {
  return useContext(ConfirmCtx);
}
