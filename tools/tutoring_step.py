"""One adaptive simulated-learner step via the actual local-model backend.

The agent authors each learner edit only after reading the preceding reply.
Report carries those rationales; this is not an actual student learning study.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');os.environ['HINT_MODE']='live'
import django
django.setup()
from coach.models import Problem
from coach.services import build_messages,generate_hint,HintError,PROMPT_VERSION
from coach import services
from coach.reply_quality import quality_issue,traditional_reply
from coach.judging import judge

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',type=Path,required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    request=json.loads(args.request.read_text(encoding='utf-8'))
    report=json.loads(args.report.read_text(encoding='utf-8')) if args.report.exists() else {
        'scope':'Adaptive scripted learner, direct app service -> real local model HTTP and Docker. Not live browser or actual student learning. No private student data.',
        'learner_prior_skills':'Can write cin/cout, for loops and vector input; core algorithm and unfamiliar APIs must come from recorded teacher replies.',
        'rule':'Record justification for each code edit; do not insert algorithmic steps the teacher has not supplied.',
        'steps':[]}
    topic=int(request.get('topic',10041))
    problem=Problem.objects.get(title__startswith=f'UVa {topic} ')
    code=request['code'];entry=dict(request,prompt_version=PROMPT_VERSION)
    if request.get('action')=='test':
        tests=[{'name':'題庫範例','input':problem.sample_input,'expected':problem.sample_output}]+problem.test_cases[:8]
        entry['judge']=judge(code,tests)
        print(json.dumps(entry['judge'],ensure_ascii=True),flush=True)
    else:
        history=[{'question':s['question'],'hint':s['answer'],'code':s['code']} for s in report['steps'] if s.get('answer')]
        previous=next((s for s in reversed(report['steps']) if s.get('judge') and s['code']==code),None)
        evidence=previous['judge'] if previous else {'status':'not_run','label':'這份程式尚未測試','cases':[]}
        messages=build_messages(problem,code,request['question'],request.get('level',3),history,evidence,include_diagnostics=False)
        started=time.monotonic()
        original=services._generate_once;attempts=[]
        def capture(prompt,level):
            reply=original(prompt,level)
            attempts.append({'answer':str(reply),'issue':quality_issue(traditional_reply(str(reply)),messages)})
            return reply
        try:
            with patch('coach.services._generate_once',side_effect=capture):
                reply=generate_hint(messages,request.get('level',3))
            entry.update(answer=str(reply),source=reply.source,status='partial' if reply.truncated else 'done',tutoring_projection=reply.tutoring_projection,
                         scaffold_step=json.loads(messages[-1]['content']).get('verified_next_step',{}).get('step'))
        except HintError as exc:entry.update(answer='',status='failed',error=str(exc))
        entry['attempts']=attempts
        entry['seconds']=round(time.monotonic()-started,2)
        print(json.dumps(entry,ensure_ascii=True),flush=True)
    entry['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
    report['steps'].append(entry);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
