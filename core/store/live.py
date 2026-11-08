"""Live writes to SpacetimeDB while an agent runs, without slowing the agent down.

    live = Live(site, actor="explorer")
    live.event("page", "Read / -> list Post +30", {...})
    live.record("Post", "42", {"title": ...})
    live.job_start("explore", total=0); live.job_update(done=5)
    live.site(site_map, model)        # site map + data model so far (Console draws them live)
    live.close()                      # waits (briefly) for the queue to drain

Every call is queued and sent by background threads. Failures are counted, never raised:
the agent never blocks on the database (plan rule). If SpacetimeDB is unreachable at start,
Live turns itself off and says so once.
"""
import queue
import threading
import time
import uuid

from store import spacetime as db


class Live:
    def __init__(self, site, actor="explorer", workers=4):
        self.site, self.actor = site, actor
        self.sent = self.failed = 0
        self.job_key = None
        self.enabled = db.sql("SELECT * FROM site WHERE url = 'x'") is not None
        if not self.enabled:
            print("  ! SpacetimeDB not reachable: live updates off (results are still saved to disk)")
            return
        self.q = queue.Queue(maxsize=20000)
        self.threads = [threading.Thread(target=self._work, daemon=True) for _ in range(workers)]
        for t in self.threads:
            t.start()

    def _work(self):
        while True:
            item = self.q.get()
            if item is None:
                self.q.task_done()
                return
            fn, args = item
            try:
                ok = fn(*args)
            except Exception:
                ok = False
            self.sent += 1
            self.failed += 0 if ok else 1
            self.q.task_done()

    def _put(self, fn, *args):
        if self.enabled:
            try:
                self.q.put_nowait((fn, args))
            except queue.Full:
                self.failed += 1

    # ---- what agents call ----
    def event(self, kind, message, data=None, level="info"):
        self._put(db.log_event, self.site, self.actor, message, {"kind": kind, **(data or {})}, level)

    def record(self, entity, legacy_id, data):
        self._put(db.upsert_record, self.site, entity, str(legacy_id), data)

    def schema(self, entity, fields, rules):
        self._put(db.upsert_schema, self.site, entity, fields, rules)

    def site_state(self, site_map, model, ops=None, docs=""):
        self._put(db.save_site, self.site, site_map, model, ops or {}, docs)

    def job_start(self, kind, entity="", total=0):
        self.job_key = f"{kind}-{uuid.uuid4().hex[:10]}"
        self._put(db.start_job, self.job_key, self.site, kind, entity, total)

    def job_update(self, done, total=0, status="running"):
        if self.job_key:
            self._put(db.update_job, self.job_key, done, total, status)

    def close(self, timeout=30):
        if not self.enabled:
            return
        t0 = time.time()
        while not self.q.empty() and time.time() - t0 < timeout:
            time.sleep(0.2)
        for _ in self.threads:
            self.q.put(None)
        print(f"  live: {self.sent} database writes ({self.failed} failed)")
