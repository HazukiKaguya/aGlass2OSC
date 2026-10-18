"""Keep vendor native code outside the OSC process, including native shutdown."""
import logging
import multiprocessing as mp
import signal
import time

from .sdk import Samples

LOG = logging.getLogger(__name__)


def _worker(connection, args):
    # The parent handles Ctrl+C and sends a stop request after resetting OSC.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s SDK %(levelname)s %(message)s", datefmt="%H:%M:%S")
    from .cli import make_backend
    samples = Samples()
    backend = directory = None
    try:
        backend, directory = make_backend(args, samples)
        if not args.diagnose:
            backend.start(args)
        connection.send(("ready", getattr(backend, "active_eyes", ())))
        if not args.diagnose:
            previous = None
            interval = 1. / min(240., max(120., args.rate * 2.))
            while not connection.poll(interval):
                snapshot = samples.snapshot()
                if snapshot != previous:
                    connection.send(("samples", snapshot))
                    previous = snapshot
    except (EOFError, BrokenPipeError):
        pass  # Parent exited; release the SDK below.
    except Exception as exc:
        try:
            connection.send(("error", str(exc)))
        except (OSError, EOFError):
            pass
    finally:
        # May block or crash in native code. The parent owns the deadline.
        if backend:
            backend.close()
        if directory:
            directory.close()
        connection.close()


class IsolatedBackend:
    def __init__(self, samples):
        self.samples = samples
        self.process = self.connection = None
        self.active_eyes = ()
        self.ready = False
        self.stop_timeout = 3.
        self.exitcode = None

    def start(self, args, stop_event=None):
        self.stop_timeout = args.sdk_stop_timeout
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker, args=(child, args), name="aGlass SDK", daemon=True)
        try:
            self.process.start()
        finally:
            child.close()
        deadline = time.monotonic() + args.sdk_start_timeout
        while not self.ready:
            if stop_event is not None and stop_event.is_set():
                raise InterruptedError("SDK startup cancelled.")
            if time.monotonic() >= deadline:
                raise RuntimeError("SDK startup timed out; check Runtime / USB / profile, or increase --sdk-start-timeout.")
            self.poll(wait=.05, starting=True)

    def _exited(self):
        self.process.join(.05)
        code = self.process.exitcode
        detail = "closed its connection" if code is None else f"exited with code 0x{code & 0xffffffff:08X}"
        raise RuntimeError(f"aGlass SDK process {detail}. Check the Runtime/DLL pairing; OSC has been stopped.")

    def poll(self, wait=0., starting=False):
        for _ in range(64):
            try:
                if not self.connection.poll(wait):
                    break
                wait = 0.
                kind, value = self.connection.recv()
            except (EOFError, OSError):
                self._exited()
            if kind == "error":
                raise RuntimeError(f"aGlass SDK: {value}")
            if kind == "ready":
                self.active_eyes = tuple(value)
                self.ready = True
                if starting:
                    return  # A diagnose-only worker is allowed to exit immediately.
            elif kind == "samples":
                with self.samples.lock:
                    # Preserve callback arrival time; IPC must not make old data fresh.
                    self.samples.data = value
        if not self.process.is_alive():
            self._exited()

    def close(self):
        if not self.process or self.process.pid is None:
            if self.connection:
                self.connection.close()
            return
        try:
            if self.process.is_alive():
                try:
                    self.connection.send(("stop", None))
                except (BrokenPipeError, EOFError, OSError):
                    pass
                deadline = time.monotonic() + self.stop_timeout
                # Drain any buffered snapshots so the child cannot block on send.
                while self.process.is_alive() and time.monotonic() < deadline:
                    try:
                        if self.connection.poll(.02):
                            self.connection.recv()
                    except (EOFError, OSError):
                        self.process.join(.02)
                    self.process.join(.01)
                if self.process.is_alive():
                    LOG.warning("SDK shutdown exceeded %.1fs; terminating its isolated process.", self.stop_timeout)
                    self.process.terminate()
                    self.process.join(1.)
            else:
                self.process.join()
            self.exitcode = self.process.exitcode
            if self.exitcode:
                LOG.warning("SDK process ended with code 0x%08X; OSC cleanup ran in the parent process.",
                            self.exitcode & 0xffffffff)
        finally:
            self.connection.close()
            if not self.process.is_alive():
                self.process.close()
                self.process = None
