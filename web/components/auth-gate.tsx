"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { BrandLogo } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api";

type Status = { password_required: boolean; signed_in: boolean };

/**
 * Keeps the studio private. Reader links (/read/...) are always public; the
 * studio itself needs either this computer or a sign-in (NOVEL_OS_PASSWORD).
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const isReader = pathname.startsWith("/read/");
  const status = useQuery({
    queryKey: ["auth", "status"],
    queryFn: () => api.get<Status>("/auth/status"),
    enabled: !isReader,
    staleTime: 60_000,
    retry: false,
  });

  if (isReader || status.isLoading || status.isError) return <>{children}</>;
  const s = status.data!;
  if (s.signed_in) return <>{children}</>;
  if (s.password_required) return <SignIn />;
  return (
    <Screen title="This studio is private">
      <p className="text-[15px] leading-relaxed text-body">
        Novel OS only answers the computer it runs on. To write from this device, set{" "}
        <span className="font-semibold text-ink">NOVEL_OS_PASSWORD</span> on the server and restart it, then sign in here.
      </p>
    </Screen>
  );
}

function SignIn() {
  const qc = useQueryClient();
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => api.post("/auth/login", { password }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const error = login.error instanceof ApiError ? login.error.message : login.error ? String(login.error) : "";
  return (
    <Screen title="Sign in to your studio">
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (password) login.mutate(); }}>
        <Field label="Password">
          <Input type="password" autoFocus autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <p role="alert" className="text-[13px] text-fail">{error}</p>}
        <Button type="submit" disabled={!password || login.isPending}>
          <Lock className="h-4 w-4" strokeWidth={1.75} /> {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </Screen>
  );
}

function Screen({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-paper px-6">
      <div className="w-full max-w-sm">
        <BrandLogo />
        <h1 className="mt-10 font-display text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">{title}</h1>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}
