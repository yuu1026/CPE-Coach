from django.conf import settings
from django.utils import timezone
from .models import Submission
from . import services
from .judging import judge
from . import performance
import hashlib
import json

def test_inputs(problem, data):
    tests = [{'name': '範例測資', 'input': problem.sample_input, 'expected': problem.sample_output}] + problem.test_cases[:8]
    if data['run_custom']:
        tests.append({'name': '自訂測資', 'input': data['custom_input'], 'expected': data['custom_expected']})
    if problem.output_comparison != 'exact':
        tests = [dict(case, comparison=problem.output_comparison) for case in tests]
    return tests

def test_fingerprint(code, tests):
    snapshot = json.dumps({'code': code, 'tests': tests, 'policy': 'cpp17-docker-v2'}, ensure_ascii=False, sort_keys=True)
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
    record, created = reserve(owner, problem, data, parent)
    if created:
        complete(record, data, parent)
    return record


def reserve(owner, problem, data, parent=None):
    action = data.get('action') or 'ask'
    record, created = Submission.objects.get_or_create(owner=owner, submission_id=data['submission_id'], defaults={'problem': problem, 'parent': parent, 'action': action, 'code': data['code'], 'question': '' if action == 'test' else data['question'], 'hint_level': 1, 'mode': 'judge' if action == 'test' else settings.HINT_MODE, 'model': '未呼叫模型' if action == 'test' else 'demo' if settings.HINT_MODE == 'demo' else settings.MODEL_NAME, 'prompt_version': services.PROMPT_VERSION})
    return record, created


def complete(record, data, parent=None):
    # Only update existing records: clearing a chat must never resurrect it.
    def persist(snapshot):
        Submission.objects.filter(pk=record.pk).update(performance=snapshot)
    with performance.measure(persist) as measurement:
        try:
            _complete(record, data, parent)
            performance.phase('failed' if record.status=='failed' else 'done')
        finally:
            record.performance = measurement.snapshot()


def _complete(record, data, parent=None):
    owner, problem, action = record.owner, record.problem, record.action
    tests = test_inputs(problem, data)
    fingerprint = test_fingerprint(record.code, tests)
    if action == 'test':
        with performance.span('testing'):
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
        performance.phase('preparing')
        prior = thread_records(parent) if parent else []
        history = [{'question':s.question,'hint':s.answer if s.status in ('done','partial') else '上一輪未交付可用回覆；不要沿用未驗證的候選。',
                    'code':s.code,'delivered':s.status in ('done','partial') and bool(s.answer)}
                   for s in prior if s.action!='test' and (s.answer or s.question)]
        record.messages = services.build_messages(problem, record.code, record.question, history=history, evidence=record.judge_result,validation_tests=tests)
        record.save(update_fields=['messages'])
        reply = services.generate_hint(record.messages)
        record.answer = str(reply)
        if getattr(reply,'quality_audit',None):record.messages[-1]['quality_fallback']=reply.quality_audit
        if getattr(reply,'revision_check',None):record.messages[-1]['verified_revision']=reply.revision_check
        if getattr(reply,'tutoring_projection',False):record.messages[-1]['tutoring_projection']=True
        if getattr(reply, 'source', '') == 'reference':
            record.mode, record.model = 'reference', '題庫參考解答（未呼叫模型）'
        elif getattr(reply,'source','')=='verified_hint':
            record.mode,record.model='verified_hint','題庫診斷提示（未呼叫模型）'
        elif getattr(reply,'source','')=='verified_step':
            record.mode,record.model='verified_hint','系統教學步驟（模型候選經題庫規則替代）'
        elif getattr(reply,'source','')=='verified_test':
            record.mode,record.model='verified_hint','系統測試確認（未呼叫模型）'
        elif getattr(reply,'source','')=='knowledge':
            record.mode,record.model='knowledge','系統C++知識核對（模型候選未通過規則檢查）'
        record.status = 'partial' if getattr(reply, 'truncated', False) else 'done'
        omitted = getattr(reply, 'omitted_history_turns', 0)
        if omitted:
            record.messages = record.messages[:1] + record.messages[1 + omitted * 2:]
    except services.HintError as exc:
        record.error, record.status = str(exc), 'failed'
        if getattr(exc,'revision_audit',None) and record.messages:
            record.messages[-1]['revision_failure']=exc.revision_audit
        if getattr(exc,'reply_audit',None) and record.messages:
            record.messages[-1]['reply_failure']=exc.reply_audit
    record.finished_at = timezone.now()
    # A reply finishing in another tab must not recreate chat deleted meanwhile.
    Submission.objects.filter(pk=record.pk, owner=owner).update(answer=record.answer,
        status=record.status, error=record.error, messages=record.messages,
        mode=record.mode, model=record.model, finished_at=record.finished_at)
    return record
