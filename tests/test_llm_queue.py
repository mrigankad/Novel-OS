"""Tests for LLM request queue."""

from __future__ import annotations

import threading
import time

import pytest

from llm_queue import LLMRequestQueue, QueueCancelledError, QueueFlushedError, flush_llm_queue


def test_queue_respects_max_concurrent():
    q = LLMRequestQueue(max_concurrent=2)
    gate = threading.Event()
    peak = {"value": 0}
    lock = threading.Lock()

    def worker():
        with q.acquire():
            with lock:
                s = q.status()
                peak["value"] = max(peak["value"], int(s["active"]))
            gate.wait(timeout=2)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(0.2)
    assert peak["value"] <= 2
    assert q.status()["queued"] >= 1
    gate.set()
    for t in threads:
        t.join(timeout=3)


def test_flush_rejects_queued_waiters():
    q = LLMRequestQueue(max_concurrent=1)
    blocker = threading.Event()
    errors: list[str] = []

    def hold_slot():
        with q.acquire():
            blocker.wait(timeout=3)

    t1 = threading.Thread(target=hold_slot)
    t1.start()
    time.sleep(0.05)

    def wait_for_slot():
        try:
            with q.acquire():
                pass
        except QueueFlushedError as e:
            errors.append(str(e))

    t2 = threading.Thread(target=wait_for_slot)
    t2.start()
    time.sleep(0.05)
    assert q.status()["queued"] >= 1

    q.flush("Cancelled by restart")
    t2.join(timeout=2)
    assert errors and "Cancelled by restart" in errors[0]

    blocker.set()
    t1.join(timeout=2)


def test_flush_blocks_new_acquires():
    q = LLMRequestQueue(max_concurrent=2)
    q.flush("done")
    with pytest.raises(QueueFlushedError, match="done"):
        with q.acquire():
            pass


def test_configure_and_flush_helpers(monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", "/tmp/novel-os-test-queue")
    import llm_queue as mod

    mod._queue = None
    q = mod.configure_llm_queue(3)
    assert q.max_concurrent == 3
    status = mod.flush_llm_queue("test flush")
    assert status["flushed"] is True
    mod._queue = None


def test_status_lists_active_and_queued_entries():
    q = LLMRequestQueue(max_concurrent=1)
    started = threading.Event()
    release = threading.Event()

    def hold():
        with q.acquire("First call"):
            started.set()
            release.wait(timeout=3)

    t1 = threading.Thread(target=hold)
    t1.start()
    started.wait(timeout=2)

    def wait_in_queue():
        with q.acquire("Second call"):
            pass

    t2 = threading.Thread(target=wait_in_queue)
    t2.start()
    time.sleep(0.08)

    status = q.status()
    assert status["active"] == 1
    assert status["queued"] >= 1
    assert len(status["active_items"]) == 1
    assert status["active_items"][0]["label"] == "First call"
    assert status["active_items"][0]["submitted_at"]
    assert any(item["label"] == "Second call" for item in status["queued_items"])

    release.set()
    t1.join(timeout=2)
    t2.join(timeout=2)


def test_cancel_queued_entry():
    q = LLMRequestQueue(max_concurrent=1)
    started = threading.Event()
    release = threading.Event()
    errors: list[str] = []

    def hold():
        with q.acquire("Active"):
            started.set()
            release.wait(timeout=3)

    t1 = threading.Thread(target=hold)
    t1.start()
    started.wait(timeout=2)

    def wait_in_queue():
        try:
            with q.acquire("Waiting"):
                pass
        except Exception as e:
            errors.append(type(e).__name__)

    t2 = threading.Thread(target=wait_in_queue)
    t2.start()
    time.sleep(0.08)

    status = q.status()
    queued_id = status["queued_items"][0]["id"]
    q.cancel_queued(queued_id)
    t2.join(timeout=2)
    assert "QueueCancelledError" in errors

    release.set()
    t1.join(timeout=2)


def test_reorder_and_move_queued():
    q = LLMRequestQueue(max_concurrent=1)
    gate = threading.Event()

    def block():
        with q.acquire("block"):
            gate.wait(timeout=3)

    t = threading.Thread(target=block)
    t.start()
    time.sleep(0.05)

    ids: list[str] = []

    def enqueue(label: str):
        def run():
            try:
                with q.acquire(label):
                    pass
            except Exception:
                pass
        threading.Thread(target=run).start()

    for label in ("A", "B", "C"):
        enqueue(label)
    time.sleep(0.1)

    status = q.status()
    queued = [e["id"] for e in status["queued_items"]]
    assert len(queued) >= 2
    first = queued[0]
    q.move_queued(first, "last")
    after_move = [e["id"] for e in q.status()["queued_items"]]
    assert after_move[-1] == first

    q.reorder_queued(list(reversed(after_move)))
    reordered = [e["id"] for e in q.status()["queued_items"]]
    assert reordered == list(reversed(after_move))

    gate.set()
    t.join(timeout=2)
