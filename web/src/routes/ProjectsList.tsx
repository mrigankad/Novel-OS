import { useEffect, useState } from "react";
import { api, type ProjectSummary } from "../api/client";
import ProjectCard from "../components/ProjectCard";

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">Failed to load projects: {error}</div>;
  if (!projects) return <div>Loading…</div>;
  if (projects.length === 0)
    return <div>No projects yet. Create one with the CLI: <code>python core/orchestrator.py init …</code></div>;
  return (
    <div className="projects-grid">
      {projects.map((p) => <ProjectCard key={p.id} p={p} />)}
    </div>
  );
}
