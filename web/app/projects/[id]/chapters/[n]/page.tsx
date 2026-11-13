"use client";
import dynamic from "next/dynamic";

const Screen = dynamic(() => import("../../../../../src/routes/ChapterView"), { ssr: false });

export default function Page() {
  return <Screen />;
}
