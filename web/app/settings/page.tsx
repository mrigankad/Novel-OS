"use client";
import dynamic from "next/dynamic";

const Screen = dynamic(() => import("../../src/routes/Settings"), { ssr: false });

export default function Page() {
  return <Screen />;
}
