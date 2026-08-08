import { createContext, useContext } from "react";

export type ToastTone = "success" | "error" | "info";

/** Split from Toaster.tsx so that file exports only components (Fast Refresh). */
export const ToastCtx = createContext<(message: string, tone?: ToastTone) => void>(
  () => {},
);

export function useToast() {
  return useContext(ToastCtx);
}
