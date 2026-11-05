"""商汤钥匙坑位。每把钥匙同时只出一张图，多出来的请求在这里等。"""

import threading


class KeyPool:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._busy: set[int] = set()
        self._cursor = 0

    def acquire(self, size: int) -> int:
        """拿走一把空闲钥匙的序号。都在忙就等到有人还回来。"""
        if size < 1:
            raise ValueError("没有钥匙")
        with self._cond:
            while True:
                for step in range(size):
                    index = (self._cursor + step) % size
                    if index not in self._busy:
                        self._busy.add(index)
                        self._cursor = (index + 1) % size
                        return index
                self._cond.wait()

    def release(self, index: int) -> None:
        with self._cond:
            self._busy.discard(index)
            self._cond.notify_all()


_pool = KeyPool()


def reset_key_pool() -> None:
    """新进程或新测试从第一把钥匙重新排。"""
    global _pool
    _pool = KeyPool()


def run_with_key(keys: list[str], fn):
    """fn 收到一把当前没人用的钥匙。全部占用时，这个调用会停在这里排队。"""
    if not keys:
        return fn("")
    index = _pool.acquire(len(keys))
    try:
        return fn(keys[index])
    finally:
        _pool.release(index)
