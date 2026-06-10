import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type ProjectDetail, type ChapterSummary } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="error">Failed to load: {error}</div>;
  if (!project) return <div>Loading…</div>;
  return (
    <div className="dashboard">
      <header>
        <h2>{project.title}</h2>
        <p>{project.genre} · by {project.author || "Unknown"}</p>
      </header>
      <ChapterBoard chapters={chapters} />
    </div>
  );
}
