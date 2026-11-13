import { Suspense } from "react";
import Room from "@/components/agents/room";

export default function RoomPage() {
  return (
    <Suspense>
      <Room />
    </Suspense>
  );
}
