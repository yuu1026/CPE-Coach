"""Build 49-topic tutor data, with Docker-verified correct/incorrect C++.

Training and evaluation share topics but use separate incorrect programs. No
student data or third-party solutions are scraped. Audit work is resumable.
"""
import hashlib
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'training'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from coach.judging import judge
from coach.services import build_messages
from training.build_data import CATALOG
from tools.validate_cpe49 import REFERENCES, HEAD
from cpe49_mutations import MUTATIONS, FOCUS

DEST = ROOT / 'training/data/cpe49'


def digest(code, tests):
    return hashlib.sha256(json.dumps({'code': code, 'tests': tests, 'policy': 'cpp17-docker-v2'}, sort_keys=True).encode()).hexdigest()


def make_record(item, kind, level, code, question, answer, evidence, history=None):
    messages = build_messages(SimpleNamespace(statement=item['statement']), code, question, level, history or [], evidence)
    return {'id': f"uva{item['uva']}-{kind}-l{level}", 'problem_id': item['uva'], 'variant': kind,
            'hint_level': level, 'source': item['source'],
            'messages': messages + [{'role': 'assistant', 'content': answer}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recheck', action='store_true', help='Recompile all programs instead of reusing matching audit hashes')
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    audit_file = DEST / 'judge_audit.jsonl'
    cache = {}
    cache_file = audit_file if audit_file.exists() else DEST / 'verified_programs.jsonl'
    if cache_file.exists() and not args.recheck:
        for line in cache_file.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['judge']['status'] in ('accepted', 'failed'):
                cache[row['sha256']] = row['judge']
    catalog = json.loads((ROOT / 'data/cpe49.json').read_text(encoding='utf-8'))
    original = {p['uva']: p for p in CATALOG}
    assert len(catalog) == len(FOCUS) == 49
    train, evaluation, verified = [], [], []
    for item in catalog:
        number = item['uva']
        code = original[number]['code'] if number in original else HEAD + REFERENCES[number]
        if number in original:
            mutations = [(m[0], m[1], *m[3:]) for m in original[number]['mutations'][:2]]
        else:
            mutations = MUTATIONS[number]
        variants = [('correct', code, None)]
        for kind, mutation in zip(('bug_train', 'bug_eval'), mutations):
            old, new, *_ = mutation
            if code.count(old) != 1:
                raise RuntimeError(f'Ambiguous mutation {number} {kind}: {old!r}')
            variants.append((kind, code.replace(old, new), mutation))
        for kind, program, mutation in variants:
            key = digest(program, item['tests'])
            evidence = cache.get(key)
            if evidence is None:
                evidence = judge(program, item['tests'])
                with audit_file.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'uva': number, 'variant': kind, 'sha256': key, 'judge': evidence}, ensure_ascii=False) + '\n')
            expected = 'accepted' if kind == 'correct' else 'failed'
            if evidence['status'] != expected or (mutation and not any(c['status'] == 'wrong_answer' for c in evidence['cases'])):
                raise RuntimeError(f'UVa {number} {kind}: {json.dumps(evidence, ensure_ascii=False)}')
            verified.append({'uva': number, 'variant': kind, 'sha256': key, 'judge': evidence})
            for level in (1, 2, 3):
                if mutation:
                    answer = '本次執行有輸出不符。' + mutation[level + 1]
                    question = '請幫我檢查目前程式，依提示程度引導我，不要直接給完整答案。'
                else:
                    answer = ['目前程式通過本次全部測資，沒有已確認需要修改的問題。這只代表提供的測資通過，並非所有合法輸入的保證；目前可以保留程式。',
                              '本次測資全數通過，目前沒有失敗案例可以定位。若你有特定疑問，請指出想理解的片段，我們再一起追蹤，不必任意修改已通過的程式。',
                              '沒有實測證據顯示需要局部修正，因此不提供多餘的改碼建議。保留目前版本即可；之後若有合法失敗案例，再針對第一個差異分析。'][level-1]
                    question = '程式已經執行測試了，現在還需要修改嗎？'
                row = make_record(item, kind, level, program, question, answer, evidence)
                (evaluation if kind == 'bug_eval' else train).append(row)
        # Starting from no code, then responding to the student's previous answer.
        focus = FOCUS[number]
        empty = {'status': 'not_submitted', 'label': '尚未提供程式碼', 'cases': []}
        starters = [f'先不用寫程式。這題中，{focus}你可以先用自己的話說明，題目會給什麼輸入、要得到什麼輸出嗎？',
                    f'我們先挑範例的一組資料手算，不急著寫完整流程。{focus}你可以先指出這組資料的第一個輸入值代表什麼嗎？',
                    f'先處理讀入資料這一小步，不急著完成整題。{focus}你會先讀一個值、一整行，還是另一種形式，為什麼？']
        for level in (1, 2, 3):
            train.append(make_record(item, 'getting_started', level, '', '我完全沒有想法，可以帶我開始嗎？', starters[level-1], empty))
        history = [{'question': '我完全沒有想法，可以帶我開始嗎？', 'hint': starters[0], 'code': ''}]
        for kind, question, answer in [
            ('followup', '我覺得要先釐清每組資料的欄位與輸出格式。', f'先釐清欄位與輸出格式的方向是合理的。{focus}接著請挑範例裡一組輸入，描述讀入後需要保存哪些資料。'),
            ('clarification', '我是不是可以直接猜固定答案，不用讀輸入？', f'固定答案無法涵蓋不同的合法輸入。{focus}請挑兩組不同輸入，想想哪些輸出內容可能跟著改變；先描述其中一個差異即可。'),
        ]:
            train.append(make_record(item, kind, 1, '', question, answer, empty, history))
        print(f'UVa {number}: correct + training/eval bugs verified; tutor conversations ready', flush=True)
    assert len(train) == 539 and len(evaluation) == 147
    for rows, name in [(train, 'train.jsonl'), (evaluation, 'eval.jsonl')]:
        assert all('int main' not in row['messages'][-1]['content'] for row in rows)
        (DEST / name).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    (DEST / 'verified_programs.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in verified), encoding='utf-8')
    summary = {'topics': 49, 'training_conversations': len(train), 'evaluation_conversations': len(evaluation), 'verified_programs': len(verified),
               'training_variants': ['correct', 'bug_train', 'getting_started', 'followup', 'clarification'],
               'evaluation_variant': 'bug_eval', 'judge_policy': 'cpp17-docker-v2',
               'scope': 'All 49 topics appear in training. Evaluation uses separate mutated programs on the same topics, not unseen-problem generalization. Teacher targets are authored, not independently teacher-reviewed.'}
    (DEST / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
