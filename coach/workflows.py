from django.conf import settings
from django.utils import timezone
from .models import Submission
from . import services
from .judging import judge
import hashlib
import json

def test_inputs(problem, data):
    tests = [{'name': '範例測資', 'input': problem.sample_input, 'expected': problem.sample_output}] + problem.test_cases[:8]
    if data['run_custom']:
        tests.append({'name': '自訂測資', 'input': data['custom_input'], 'expected': data['custom_expected']})
    return tests

def test_fingerprint(code, tests):
    snapshot = json.dumps({'code': code, 'tests': tests, 'policy': 'cpp17-docker-v1'}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(snapshot.encode('utf-8')).hexdigest()

def prior_result(parent, fingerprint):
    current = parent
    visited = set()
    while current and current.pk not in visited:
        if current.owner_id != parent.owner_id or current.problem_id != parent.problem_id:
            break
        visited.add(current.pk)
        result = current.judge_result
        if result.get('fingerprint') == fingerprint and result.get('status') in ('accepted', 'failed', 'compile_error'):
            reused = dict(result)
            reused['reused_from'] = result.get('reused_from', current.pk)
            return reused
        current = current.parent
    return None

def thread_records(record):
    """Follow only this branch, never unrelated attempts on the same problem."""
    turns, visited = [], set()
    current = record
    while current and current.pk not in visited:
        if current.owner_id != record.owner_id or current.problem_id != record.problem_id:
            break
        visited.add(current.pk)
        turns.append(current)
        current = current.parent
    return list(reversed(turns))

def submit(owner, problem, data, parent=None):
    action = data.get('action') or 'ask'
    record, created = Submission.objects.get_or_create(owner=owner, submission_id=data['submission_id'], defaults={'problem': problem, 'parent': parent, 'action': action, 'code': data['code'], 'question': data['question'], 'hint_level': data['hint_level'], 'mode': 'judge' if action == 'test' else settings.HINT_MODE, 'model': '未呼叫模型' if action == 'test' else 'demo' if settings.HINT_MODE == 'demo' else settings.MODEL_NAME, 'prompt_version': services.PROMPT_VERSION})
    if not created:
        return record
    tests = test_inputs(problem, data)
    fingerprint = test_fingerprint(record.code, tests)
    if action == 'test':
        record.judge_result = judge(record.code, tests)
        record.judge_result['fingerprint'] = fingerprint
    elif not record.code.strip():
        record.judge_result = {'status': 'not_submitted', 'label': '尚未提供程式碼：從想法開始', 'note': '本次只詢問助理，未編譯或執行測資。', 'cases': []}
    else:
        record.judge_result = prior_result(parent, fingerprint) or {'status': 'not_run', 'label': '目前程式與測資尚無可沿用的測試結果', 'note': '本次只詢問助理。請按「執行測試」取得此版本的實際結果。', 'cases': []}
    record.judge_result['custom_test'] = {'enabled': data['run_custom'], 'input': data['custom_input'], 'expected': data['custom_expected']}
    record.save(update_fields=['judge_result'])
    if action == 'test':
        record.status = 'tested'
        record.finished_at = timezone.now()
        record.save(update_fields=['status', 'finished_at'])
        return record
    try:
        prior = thread_records(parent) if parent else []
        history = [{'question': s.question, 'hint': s.answer, 'code': s.code} for s in prior if s.status in ('done', 'partial') and s.answer]
        record.messages = services.build_messages(problem, record.code, record.question, record.hint_level, history, evidence=record.judge_result)
        record.save(update_fields=['messages'])
        reply = services.generate_hint(record.messages, record.hint_level)
        record.answer = str(reply)
        record.status = 'partial' if getattr(reply, 'truncated', False) else 'done'
        omitted = getattr(reply, 'omitted_history_turns', 0)
        if omitted:
            record.messages = record.messages[:1] + record.messages[1 + omitted * 2:]
    except services.HintError as exc:
        record.error, record.status = str(exc), 'failed'
    record.finished_at = timezone.now()
    record.save()
    return record
