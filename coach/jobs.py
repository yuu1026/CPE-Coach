"""Single-flight local development worker; no unbounded queues or extra models."""
import logging
import threading
from django.db import close_old_connections
from django.utils import timezone
from .models import Submission
from .workflows import reserve, complete

_slot = threading.BoundedSemaphore(1)
logger = logging.getLogger(__name__)


class BusyError(Exception): pass


def _run(pk, data):
    close_old_connections()
    try:
        record = Submission.objects.select_related('owner', 'problem', 'parent').filter(pk=pk).first()
        if record:
            complete(record, data, record.parent)
    except Exception:
        logger.exception('Local teaching job %s failed', pk)
        Submission.objects.filter(pk=pk).update(status='failed', finished_at=timezone.now(),
            error='本次處理未完成，原程式已保留。請查看網站終端機，或重新送出問題。',
            performance={'phase': 'failed'})
    finally:
        close_old_connections()
        _slot.release()


def launch(owner, problem, data, parent=None):
    previous = Submission.objects.filter(owner=owner, submission_id=data['submission_id']).first()
    if previous: return previous
    if not _slot.acquire(blocking=False):
        raise BusyError('目前有另一個教學請求處理中，請等待完成；你的訊息尚未送出。')
    try:
        record, created = reserve(owner, problem, data, parent)
        if not created:
            _slot.release()
            return record
        threading.Thread(target=_run, args=(record.pk, dict(data)), daemon=True,
                         name=f'coach-reply-{record.pk}').start()
        return record
    except Exception:
        _slot.release()
        raise
