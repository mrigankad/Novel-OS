import type { Metadata } from "next";
import { AgentsScreen } from "@/components/settings/agents-screen";

export const metadata: Metadata = { title: "Agents and models" };

export default function AgentsPage() {
  return <AgentsScreen />;
}
