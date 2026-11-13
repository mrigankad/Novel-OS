"use client";
import dynamic from "next/dynamic";

const Screen = dynamic(() => import("../src/routes/ProjectsList"), { ssr: false });

export default function Page() {
  return <Screen />;
}
