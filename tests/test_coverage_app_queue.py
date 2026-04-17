import queue
from app import _queue_latest

def test_queue_latest_empty_exception():
    class FakeQueue(queue.Queue):
        def put_nowait(self, item):
            if getattr(self, "called_put", False):
                # The second time it gets here, we just do normal put
                super().put_nowait(item)
            else:
                self.called_put = True
                raise queue.Full

        def get_nowait(self):
            raise queue.Empty

    q = FakeQueue(maxsize=1)
    dropped = _queue_latest(q, 1)
    # The dropped flag is set inside get_nowait() success block. Since get_nowait() raises Empty, dropped remains False.
    assert not dropped
    assert q.qsize() == 1
