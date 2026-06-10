import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, type ChapterDetail } from "../api/client";

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const [chapter, setChapter] = useState<ChapterDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.chapter(id, Number(n)).then(setChapter).catch((e) => setError(String(e)));
  }, [id, n]);

  if (error) return <div className="error">Failed to load: {error}</div>;
  if (!chapter) return <div>Loading…</div>;
  return (
    <div className="chapter-view">
      <header>
        <h2>Chapter {chapter.number}: {chapter.title || "Untitled"}</h2>
        <span>{chapter.status} · {chapter.word_count} words · POV {chapter.pov || "—"}</span>
      </header>
      <div className="panes">
        <section>
          <h3>Outline</h3>
          {chapter.outline ? <ReactMarkdown>{chapter.outline}</ReactMarkdown>
                           : <p className="muted">Outline not generated yet.</p>}
        </section>
        <section>
          <h3>Draft</h3>
          {chapter.draft ? <ReactMarkdown>{chapter.draft}</ReactMarkdown>
                         : <p className="muted">Draft not generated yet.</p>}
        </section>
      </div>
    </div>
  );
}
