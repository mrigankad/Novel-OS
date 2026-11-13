from sqlmodel import Session

from server.db import engine
from server.models import ResearchTask, Run
from server.recovery import INTERRUPTED, recover_interrupted


def test_interrupted_work_is_marked_failed_and_retryable(client, project):
    pid = project["id"]
    with Session(engine()) as s:
        s.add(Run(project_id=pid, task="draft", status="running"))
        s.add(Run(project_id=pid, task="check", status="done"))
        s.add(ResearchTask(project_id=pid, question="Grafting knives?", status="browsing"))
        s.commit()

    assert recover_interrupted() == {"runs": 1, "research": 1}

    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert {r["status"] for r in runs} == {"failed", "done"}
    assert any(r["error"] == INTERRUPTED for r in runs)
    task = client.get(f"/api/projects/{pid}/research").json()["tasks"][0]
    assert task["status"] == "failed"
    assert client.post(f"/api/projects/{pid}/research/{task['id']}/retry").status_code in (200, 202)
