"""In-process event bus: the agents report what they do; whoever is listening (the API's /runs, the dashboard)
gets the same events the dashboard's run driver understands (see web/src/lib/runDriver.js for the contract).

    from facade.events import emit, listen
    stop = listen(lambda evt: print(evt))
    emit({"stage": "explore", "kind": "page", ...})
Emitting never raises and costs nothing when nobody listens.
"""
import threading

_listeners = []
_lock = threading.Lock()


def listen(fn):
    with _lock:
        _listeners.append(fn)

    def stop():
        with _lock:
            if fn in _listeners:
                _listeners.remove(fn)
    return stop


def emit(evt):
    with _lock:
        fns = list(_listeners)
    for fn in fns:
        try:
            fn(evt)
        except Exception:
            pass
