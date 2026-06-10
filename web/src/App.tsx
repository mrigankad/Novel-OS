import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import ProjectsList from "./routes/ProjectsList";
import ProjectDashboard from "./routes/ProjectDashboard";
import ChapterView from "./routes/ChapterView";

export default function App() {
  return (
    <BrowserRouter>
      <header className="topbar">
        <Link to="/" className="wordmark">🦉 Novel OS</Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<ProjectsList />} />
          <Route path="/projects/:id" element={<ProjectDashboard />} />
          <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
