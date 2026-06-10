import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ProjectsList from "./routes/ProjectsList";
import ProjectDashboard from "./routes/ProjectDashboard";
import ChapterView from "./routes/ChapterView";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-full">
        <Sidebar />
        <main className="h-full flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<ProjectsList />} />
            <Route path="/projects/:id" element={<ProjectDashboard />} />
            <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
