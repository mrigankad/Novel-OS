import { Link, useParams } from "react-router-dom";
import type { ChapterSummary } from "../api/client";

export default function ChapterBoard({ chapters }: { chapters: ChapterSummary[] }) {
  const { id } = useParams();
  return (
    <div className="chapter-board">
      {chapters.map((c) => (
        <Link key={c.number} to={`/projects/${id}/chapters/${c.number}`} className="chapter-card">
          <strong>Ch {c.number}</strong>
          <span>{c.title || "Untitled"}</span>
          <span className={`pill ${c.status}`}>{c.status}</span>
          <span>{c.word_count} words</span>
        </Link>
      ))}
    </div>
  );
}
