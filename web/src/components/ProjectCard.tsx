import { Link } from "react-router-dom";
import type { ProjectSummary } from "../api/client";

export default function ProjectCard({ p }: { p: ProjectSummary }) {
  return (
    <Link to={`/projects/${p.id}`} className="project-card">
      <h3>{p.title}</h3>
      <p>{p.genre}</p>
      <span>{p.chapter_count} chapters · {p.status}</span>
    </Link>
  );
}
