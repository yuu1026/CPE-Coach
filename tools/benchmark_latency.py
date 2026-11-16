"""Replay fixed synthetic website questions through production service + real judge.

No student-code repairs, live DB writes, or model weight changes. Run one benchmark
at a time; report fingerprints identify the imported working-tree version.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['HINT_MODE'] = 'live'
import django
django.setup()
import httpx
from coach import services


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--cases', default='179,184,186')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild from identical student code/question/history with current production request builder.')
    args = parser.parse_args()
    source = json.loads((ROOT / 'training/reports/ui-v41-records.json').read_text(encoding='utf-8'))
    selected = [int(x) for x in args.cases.split(',')]
    cases = {row['id']: row for row in source['records']}
    fingerprint = hashlib.sha256()
    for path in sorted([*ROOT.glob('local_model_server.py'), *ROOT.glob('coach/*.py')]):
        if path.name.startswith('test'): continue
        fingerprint.update(path.name.encode()); fingerprint.update(path.read_bytes())
    report = {'variant': args.variant, 'prompt_version': services.PROMPT_VERSION,
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_sha256': fingerprint.hexdigest(), 'cases': [],
              'scope': 'Sequential replays of fixed synthetic UI questions; production service, real model HTTP and Docker. No UI or DB writes. Not a human teaching study.'}
    original = httpx.Client.stream
    for key in selected:
        row = cases[key]; calls = []
        messages = row['messages']
        if args.rebuild:
            from types import SimpleNamespace
            payload=json.loads(messages[-1]['content'])
            tests=payload.get('generated_program_tests',[])
            problem=SimpleNamespace(title=row['topic'],statement=payload['problem'],
                sample_input=payload.get('sample_input',''),sample_output=payload.get('sample_output',''),
                test_cases=tests[1:],output_comparison=tests[0].get('comparison','exact') if tests else 'exact')
            history=[]; parent=cases.get(row.get('parent'))
            while parent:
                if parent['action']!='test':
                    history.append({'question':parent['question'],'hint':parent['answer'],
                                    'code':parent['code'],'delivered':parent['status'] in ('done','partial')})
                parent=cases.get(parent.get('parent'))
            messages=services.build_messages(problem,row['code'],row['question'],history=list(reversed(history)),
                                             evidence=row['judge_result'],validation_tests=tests)

        @contextmanager
        def observed(client, *a, **kw):
            started = time.perf_counter()
            entry = {'output_limit': kw.get('json', {}).get('options', {}).get('num_predict'),
                     'stream': kw.get('json', {}).get('stream'),
                     'request_chars': sum(len(m['content']) for m in kw.get('json', {}).get('messages', []))}
            calls.append(entry)
            with original(client, *a, **kw) as response:
                entry['http_status'] = response.status_code

                def capture(data):
                    for name in ('prompt_eval_count', 'eval_count', 'done_reason', 'metrics'):
                        if name in data: entry[name] = data[name]

                class ObservedResponse:
                    def __getattr__(self, name): return getattr(response, name)
                    def iter_bytes(self):
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            entry.setdefault('first_event_seconds', round(time.perf_counter()-started, 3))
                            body.extend(chunk); yield chunk
                        try: capture(json.loads(body))
                        except (ValueError, TypeError): pass
                    def iter_lines(self):
                        for line in response.iter_lines():
                            if line:
                                entry.setdefault('first_event_seconds', round(time.perf_counter()-started, 3))
                                try:
                                    data = json.loads(line); capture(data)
                                    if data.get('message', {}).get('content'):
                                        entry.setdefault('first_text_seconds', round(time.perf_counter()-started, 3))
                                except (ValueError, TypeError): pass
                            yield line
                try: yield ObservedResponse()
                finally: entry['seconds'] = round(time.perf_counter()-started, 3)

        started = time.perf_counter()
        item = {'source_record': key, 'question': row['question'], 'calls': calls}
        try:
            with patch.object(httpx.Client, 'stream', observed):
                reply = services.generate_hint(messages)
            item.update(status='delivered', answer=str(reply), source=getattr(reply, 'source', 'model'),
                        truncated=getattr(reply, 'truncated', False),
                        revision_check=getattr(reply, 'revision_check', None),
                        performance=getattr(reply, 'performance', None))
        except services.HintError as exc:
            item.update(status='blocked', error=str(exc), revision_audit=getattr(exc, 'revision_audit', None),
                        reply_audit=getattr(exc, 'reply_audit', None))
        item['total_seconds'] = round(time.perf_counter()-started, 3)
        report['cases'].append(item)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k: item[k] for k in ('source_record', 'status', 'total_seconds', 'calls')}, ensure_ascii=True), flush=True)


if __name__ == '__main__': main()
