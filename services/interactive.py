"""Console-style runs: the program pauses at input() and waits for a value typed in the page.

How it works: the runner (services/executor.py) prints the prompt followed by an invisible marker
and then waits on stdin. The reader thread here removes the marker and flags the run as "waiting".
The web page polls for new output, shows a text box when the run is waiting, and sends the typed
line back, which is written to the program's stdin.
"""
import codecs
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from .executor import MAX_OUTPUT, check_python_safe, child_env, write_program

MARK = "\x00WAIT\x00"
RUN_LIMIT = 10        # seconds the program may run without asking for input (endless-loop guard)
IDLE_LIMIT = 300      # seconds the program may wait for a typed value
KEEP_FINISHED = 120   # seconds a finished run stays available for polling
MAX_INPUT = 1000      # characters accepted for one typed line


class InteractiveRun:
    def __init__(self, code: str):
        self.id = uuid.uuid4().hex[:12]
        self.lock = threading.RLock()
        self.output = ""
        self.error = ""
        self.reason = ""
        self.waiting = False
        self.done = False
        self.exit_code = None
        self.finished_at = None
        self._wait_since = None
        self._active_since = time.monotonic()
        self._tmp = tempfile.TemporaryDirectory()
        prog, runner = write_program(self._tmp.name, code)
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-u", runner, prog, "interactive"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=self._tmp.name, env=child_env(), bufsize=0)
        self._readers = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for t in self._readers:
            t.start()
        threading.Thread(target=self._wait_for_exit, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    # ---- reading the program's output ---------------------------------
    def _emit(self, text: str):
        if not text:
            return
        with self.lock:
            self.output += text
            if len(self.output) > MAX_OUTPUT:
                self.output = self.output[:MAX_OUTPUT]
                self._kill("Stopped: the program printed too much text (maybe an endless loop).")

    def _consume(self, pending: str, final: bool = False) -> str:
        """Split off complete markers; returns text that must wait for more data."""
        while True:
            i = pending.find(MARK)
            if i < 0:
                break
            self._emit(pending[:i])
            with self.lock:
                self.waiting = True
                self._wait_since = time.monotonic()
            pending = pending[i + len(MARK):]
        if final:
            self._emit(pending)
            return ""
        keep = 0                                   # a marker may be cut in half at the end of a chunk
        for k in range(min(len(MARK) - 1, len(pending)), 0, -1):
            if MARK.startswith(pending[-k:]):
                keep = k
                break
        self._emit(pending[:len(pending) - keep])
        return pending[len(pending) - keep:]

    def _read_stdout(self):
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending = ""
        try:
            while True:
                chunk = self.proc.stdout.read(4096)
                if not chunk:
                    break
                pending = self._consume(pending + decoder.decode(chunk))
        finally:
            self._consume(pending + decoder.decode(b"", final=True), final=True)

    def _read_stderr(self):
        data = self.proc.stderr.read()
        text = data.decode("utf-8", "replace")
        with self.lock:
            self.error += text[:MAX_OUTPUT]

    def _wait_for_exit(self):
        code = self.proc.wait()
        for t in self._readers:
            t.join(timeout=2)
        with self.lock:
            self.exit_code = code
            self.waiting = False
            self.done = True
            self.finished_at = time.monotonic()
        try:
            self._tmp.cleanup()
        except OSError:
            pass

    def _watchdog(self):
        while True:
            time.sleep(0.1)
            with self.lock:
                if self.done:
                    return
                now = time.monotonic()
                if self.waiting:
                    if now - self._wait_since > IDLE_LIMIT:
                        self._kill("Stopped: no value was typed for 5 minutes.")
                elif now - self._active_since > RUN_LIMIT:
                    self._kill(f"Stopped: the program ran for more than {RUN_LIMIT} seconds without asking for "
                               "input (maybe an endless loop).")

    # ---- controls ------------------------------------------------------
    def _kill(self, reason: str):
        with self.lock:
            if self.done or self.reason:
                return
            self.reason = reason
        try:
            self.proc.kill()
        except OSError:
            pass

    def stop(self):
        self._kill("Stopped.")

    def send_input(self, text: str) -> bool:
        line = (text or "").replace("\r", "").split("\n")[0][:MAX_INPUT]
        with self.lock:
            if self.done or not self.waiting:
                return False
            self.waiting = False
            self._active_since = time.monotonic()
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return False
        return True

    def snapshot(self, since: int = 0) -> dict:
        with self.lock:
            since = max(0, min(int(since), len(self.output)))
            return {
                "output": self.output[since:], "next": len(self.output),
                "waiting": self.waiting and not self.done, "done": self.done,
                "exitCode": self.exit_code, "reason": self.reason,
                "error": self.error.strip() if self.done else "",
            }


class RunManager:
    """Keeps the runs started from the page. Only one program runs at a time."""

    def __init__(self):
        self.runs = {}
        self.lock = threading.Lock()

    def start(self, code: str):
        problem = check_python_safe(code)
        if problem:
            return None, problem
        with self.lock:
            now = time.monotonic()
            for rid, run in list(self.runs.items()):
                run.stop()
                if run.done and run.finished_at and now - run.finished_at > KEEP_FINISHED:
                    del self.runs[rid]
            run = InteractiveRun(code)
            self.runs[run.id] = run
        return run, None

    def get(self, rid: str):
        return self.runs.get(rid)
