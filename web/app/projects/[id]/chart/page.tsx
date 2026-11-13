"use client";
import dynamic from "next/dynamic";

const Screen = dynamic(() => import("../../../../src/routes/RelationshipChart"), { ssr: false });

export default function Page() {
  return <Screen />;
}
