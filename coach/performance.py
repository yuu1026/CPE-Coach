"""Per-request measurements and bounded progress, without prompts or answers."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_current = ContextVar('coach_performance', default=None)


class Measurement:
    def __init__(self, callback=None):
        self.started = time.perf_counter()
        self.callback = callback
        self.last_publish = 0
        self.phase_started = self.started
        self.data = {'phase': 'preparing', 'spans': [], 'model_calls': [], 'retries': []}
        self.phase_seconds = {}

    def snapshot(self):
        now = time.perf_counter()
        phases = dict(self.phase_seconds)
        current = self.data['phase']
        phases[current] = phases.get(current,0) + now-self.phase_started
        return dict(self.data, elapsed_seconds=round(now-self.started, 3),
                    phase_seconds={key:round(value,3) for key,value in phases.items()})

    def publish(self, force=False):
        now = time.perf_counter()
        if self.callback and (force or now-self.last_publish >= 1):
            self.last_publish = now
            self.callback(self.snapshot())


@contextmanager
def measure(callback=None):
    existing = _current.get()
    if existing is not None:
        yield existing
        return
    item = Measurement(callback)
    token = _current.set(item)
    try:
        item.publish(True)
        yield item
    finally:
        item.publish(True)
        _current.reset(token)


def phase(name, **details):
    item = _current.get()
    if item:
        changed = item.data.get('phase') != name
        if changed:
            now = time.perf_counter()
            previous = item.data['phase']
            item.phase_seconds[previous] = item.phase_seconds.get(previous,0) + now-item.phase_started
            item.phase_started = now
        item.data.update(phase=name, **details)
        item.publish(changed)


@contextmanager
def span(name):
    started = time.perf_counter()
    phase(name)
    try:
        yield
    finally:
        item = _current.get()
        if item:
            item.data['spans'].append({'name': name, 'seconds': round(time.perf_counter()-started, 3)})


def model_call(data):
    item = _current.get()
    if item:
        item.data['model_calls'].append(data)
        item.publish(True)


def retry(reason):
    item = _current.get()
    if item:
        item.data['retries'].append(reason)
    phase('retry', reason=reason)
