"""简易文件锁，避免 published.log 并发写入冲突。"""
import contextlib
import os
import time
from pathlib import Path


@contextlib.contextmanager
def file_lock(lock_path: Path, timeout: float = 10.0, poll: float = 0.1):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"获取文件锁超时: {lock_path}")
            time.sleep(poll)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
