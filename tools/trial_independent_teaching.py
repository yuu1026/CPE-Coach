"""One recorded learner action using the actual app backend, model and Docker.

Only adoption of a delivered scaffold or a verified edit can change code.
No student accounts or database submissions are created.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
os.environ['HINT_MODE']='live'
os.environ['Model_Name']='gemma-3-4b-it'
import django
django.setup()
from coach import services
from coach.models import Problem
from coach.judging import judge
from coach.answer_validation import cpp_blocks


def fingerprint():
    digest=hashlib.sha256()
    for path in sorted((ROOT/'coach').glob('*.py')):
        if path.name.startswith('test'):continue
        digest.update(path.name.encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def extra_tests(topic):
    rng=random.Random(341116)
    if topic==10055:
        pairs=[(0,0),(0,4294967296),(4294967296,0),(2,9),(9,2)]+[(rng.randrange(4294967297),rng.randrange(4294967297)) for _ in range(35)]
        return [{'name':'40 independent integer pairs','input':''.join(f'{a} {b}\n' for a,b in pairs),
                 'expected':''.join(f'{abs(a-b)}\n' for a,b in pairs)}],40
    arrays=[[1],[1,2,100],[5,5,5,5],[101,1,2,100]]+[[rng.randint(1,70) for _ in range(rng.randint(1,12))] for _ in range(20)]
    values=[min(sum(abs(x-home) for x in xs) for home in range(min(xs),max(xs)+1)) for xs in arrays]
    return [{'name':'24 exhaustive-home examples','input':str(len(arrays))+'\n'+''.join(str(len(xs))+' '+' '.join(map(str,xs))+'\n' for xs in arrays),
             'expected':'\n'.join(map(str,values))+'\n'}],24


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();request=json.loads(args.request.read_text(encoding='utf-8'))
    if args.report.exists():
        report=json.loads(args.report.read_text(encoding='utf-8'))
        if report['backend_sha256']!=fingerprint():raise SystemExit('Application changed; start a separate trial')
        if 'initial_code' in request:raise SystemExit('No manual code replacement after the trial starts')
    else:
        report={'prompt_version':services.PROMPT_VERSION,'backend_sha256':fingerprint(),
                'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'scope':'Agent-simulated learner; direct production backend, real model HTTP and Docker; not a browser test or real human learning study.',
                'topic':request['topic'],'current_code':request.get('initial_code',''),
                'rule':'Use actual delivered scaffolds or exact verified candidates only. No independent algorithm repairs.',
                'steps':[]}
    problem=Problem.objects.get(title__startswith=f"UVa {report['topic']} ")
    tests=[{'name':'topic sample','input':problem.sample_input,'expected':problem.sample_output}]+problem.test_cases[:8]
    for case in tests:case.setdefault('comparison',problem.output_comparison)
    code=report['current_code'];action=request['action'];entry={'action':action,'before':code}
    started=time.monotonic()
    if action in ('test','extra'):
        if action=='extra':selected,count=extra_tests(report['topic']);entry['independent_examples']=count
        else:selected=tests
        entry['judge']=judge(code,selected)
    elif action in ('apply','adopt_scaffold'):
        previous=next((s for s in reversed(report['steps']) if s['action']=='ask'),None)
        if not previous or previous.get('status')!='delivered':raise SystemExit('No delivered answer to apply')
        if action=='apply':
            check=previous.get('revision_check')
            if not check or check['base_code']!=code:raise SystemExit('No matching verified candidate')
            candidate=check['candidate_code']
        else:
            if previous.get('response_mode')!='scaffold':raise SystemExit('Not a scaffold request')
            blocks=cpp_blocks(previous['answer'])
            if len(blocks)!=1 or 'main' not in blocks[0]:raise SystemExit('No unique delivered scaffold')
            candidate=blocks[0]
        report['current_code']=candidate
        entry.update(after=candidate,derived_from_ask=previous['turn'],judge=judge(candidate,tests))
    elif action=='ask':
        if sum(s['action']=='ask' for s in report['steps'])>=5:raise SystemExit('Five learner-question limit reached')
        question=request['question'];entry['question']=question
        history=[{'question':s['question'],'hint':s.get('answer') or '上一輪未交付可用回覆；不可沿用未驗證候選。',
                  'code':s['before'],'delivered':s.get('status')=='delivered'} for s in report['steps'] if s['action']=='ask']
        previous=next((s for s in reversed(report['steps']) if s.get('judge') and (s.get('after',s['before'])==code) and s['action']!='extra'),None)
        evidence=previous['judge'] if previous else {'status':'not_run','label':'目前版本尚未執行','cases':[]}
        messages=services.build_messages(problem,code,question,history=history,evidence=evidence,validation_tests=tests)
        payload=json.loads(messages[-1]['content'])
        entry.update(response_mode=payload['response_mode'],learning_mode=payload.get('learning_mode'),
                     support={'topic_notes':bool(payload.get('verified_topic_notes')),'curriculum':bool(payload.get('verified_next_step')),
                              'calculator':bool(payload.get('verified_calculation')),'knowledge':bool(payload.get('cpp_knowledge')),
                              'known_diagnostic':bool(payload.get('verified_diagnostic'))},raw_generations=[])
        original=services._generate_once
        def observe(*a,**kw):
            reply=original(*a,**kw)
            entry['raw_generations'].append({'answer':str(reply),'truncated':getattr(reply,'truncated',False),'request':services.readable_messages(a[0])})
            return reply
        try:
            with patch.object(services,'_generate_once',side_effect=observe):reply=services.generate_hint(messages)
            entry.update(status='delivered',answer=str(reply),source=getattr(reply,'source','model'),
                         revision_check=getattr(reply,'revision_check',None),quality_audit=getattr(reply,'quality_audit',None))
        except services.HintError as exc:
            entry.update(status='blocked',error=str(exc),revision_audit=getattr(exc,'revision_audit',None),reply_audit=getattr(exc,'reply_audit',None))
    else:raise SystemExit('Unknown action')
    entry.update(turn=len(report['steps'])+1,seconds=round(time.monotonic()-started,2))
    report['steps'].append(entry)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(entry,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
