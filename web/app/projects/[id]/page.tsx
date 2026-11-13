"use client";
import dynamic from "next/dynamic";

const Screen = dynamic(() => import("../../../src/routes/ProjectDashboard"), { ssr: false });

export default function Page() {
  return <Screen />;
}
