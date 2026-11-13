"use client";

import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { BrandIcon } from "@/components/brand-icon";
import { useToast } from "@/components/ui/toast";
import { settingsApi, type Connection, type ProviderInfo } from "@/lib/api/settings";
import { Sheet } from "./sheet";

export function AddConnectionSheet({
  provider, existing, onClose,
}: { provider: ProviderInfo | null; existing?: Connection; onClose: () => void }) {
  return (
    <Sheet open={!!provider} onClose={onClose} eyebrow={existing ? "Edit connection" : "Add connection"}
      title={provider?.label ?? ""}>
      {provider && <Form key={provider.id} provider={provider} existing={existing} onClose={onClose} />}
    </Sheet>
  );
}

function Form({ provider, existing, onClose }: { provider: ProviderInfo; existing?: Connection; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [baseUrl, setBaseUrl] = useState(existing?.base_url || provider.default_base_url);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(existing?.default_model || provider.default_model);
  const save = useMutation({
    mutationFn: () => settingsApi.create({
      provider: provider.id, base_url: provider.fields.includes("base_url") ? baseUrl : "",
      api_key: apiKey, default_model: model,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      toast(`${provider.label} connected`, "success");
      onClose();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const keyMissing = provider.needs_key && !apiKey && !existing?.has_key;

  return (
    <form className="flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div className="flex items-center gap-3">
        <BrandIcon id={provider.id} size="md" tile />
        <p className="text-[14px] text-body">{provider.description}</p>
      </div>
      {provider.fields.includes("base_url") && (
        <Field label={provider.labels?.base_url ?? "Base URL"}>
          <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder={provider.default_base_url || "https://…/v1"} />
        </Field>
      )}
      {provider.fields.includes("api_key") && (
        <Field label="API key" hint={existing?.has_key ? `saved, ends ${existing.key_last4 || "····"}` : "stays on this machine"}>
          <Input type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            placeholder={existing?.has_key ? "Leave empty to keep the saved key" : "Paste your key"} />
        </Field>
      )}
      <Field label={provider.labels?.default_model ?? "Default model"}>
        <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder={provider.default_model || "model id"} />
      </Field>
      <a href={provider.help_url} target="_blank" rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-gall hover:underline">
        Where do I get this? <ExternalLink size={13} strokeWidth={1.75} />
      </a>
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={keyMissing || save.isPending}>
          {save.isPending ? "Saving…" : existing ? "Save" : "Connect"}
        </Button>
      </div>
    </form>
  );
}
