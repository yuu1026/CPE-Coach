"""Fixed synthetic learner journeys; only apply delivered/verified code.

Answers are authored fixtures below, not read from the production answer key.
This tests system progression, not whether an actual beginner has learned.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
os.environ['HINT_MODE']='live'
import django
django.setup()
from coach import services
from coach.models import Problem
from coach.judging import judge
from coach.workflows import test_fingerprint
from coach.answer_validation import cpp_blocks


def scenarios():
    old=json.loads((ROOT/'training/reports/independent-v34-inputs/vito-start.json').read_text(encoding='utf-8'))['initial_code']
    old=old.replace('houses','addresses').replace('count','people').replace('place','homePosition')
    return {
        'vito_blank':(10041,'',[
            '我沒有想法，請用小例子引導我。','4','我懂了，下一步','7',
            '下一步，請只改一小處。','1、4、9，下一步','5，下一步','7，下一步','7、0，下一步','11，下一步']),
        'vito_own_code':(10041,old,[
            '請教我下一步，根據我的平均地址程式只修正一小處，不要整份重寫。',
            '9、4、1','2、5、9，下一步','5，下一步','7，下一步','7、0，下一步','11，下一步']),
        'hashmat_own_code':(10055,'#include <iostream>\nusing namespace std;\nint main(){long long armyA,armyB;while(cin>>armyA>>armyB){cout<<armyA-armyB<<endl;}return 0;}\n',[
            '請引導我修正這份程式，只改錯的地方，保留 armyA 與 armyB。',
            '7、0、-7','4、0、2，下一步','40、40，下一步']),
        'hashmat_blank':(10055,'',[
            '我沒有想法，請引導我。','5','下一步，請只教一個修改。','7、0、7，下一步','40、40，下一步']),
    }


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=list(scenarios()),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    topic,code,questions=scenarios()[args.scenario]
    problem=Problem.objects.get(title__startswith=f'UVa {topic} ')
    tests=[{'name':'範例測資','input':problem.sample_input,'expected':problem.sample_output}]+problem.test_cases[:8]
    if problem.output_comparison!='exact':tests=[dict(t,comparison=problem.output_comparison) for t in tests]
    fingerprint=hashlib.sha256()
    for path in sorted((ROOT/'coach').glob('*.py')):
        if path.name.startswith('test'):continue
        fingerprint.update(path.name.encode());fingerprint.update(path.read_bytes())
    report={'scenario':args.scenario,'topic':topic,'prompt_version':services.PROMPT_VERSION,'backend_sha256':fingerprint.hexdigest(),
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'scope':'Fixed agent-authored learner answers; real production service/model/Docker. No database writes. Only delivered scaffolds and exact verified candidates adopted. Not a human learning study or proof of model-only competence.',
            'initial_code':code,'steps':[]}
    history=[];evidence=None
    if code:
        evidence=judge(code,tests);evidence['fingerprint']=test_fingerprint(code,tests)
        report['initial_judge']=evidence
    for question in questions:
        started=time.perf_counter();entry={'question':question,'before':code}
        messages=services.build_messages(problem,code,question,history=history,evidence=evidence,validation_tests=tests)
        try:
            reply=services.generate_hint(messages)
            entry.update(status='delivered',answer=str(reply),source=getattr(reply,'source','model'),
                lesson_record=getattr(reply,'lesson_record',None),performance=getattr(reply,'performance',None),
                revision_check=getattr(reply,'revision_check',None))
            history.append({'question':question,'hint':str(reply),'code':code,'delivered':True,'lesson_record':entry['lesson_record']})
            if entry['revision_check']:
                assert entry['revision_check']['base_code']==code
                code=entry['revision_check']['candidate_code'];entry['adoption']='exact_verified_candidate'
            elif not code and '骨架' in str(reply):
                blocks=cpp_blocks(str(reply))
                if len(blocks)==1 and 'main' in blocks[0]:code=blocks[0];entry['adoption']='exact_delivered_scaffold'
            if 'adoption' in entry:
                evidence=judge(code,tests);evidence['fingerprint']=test_fingerprint(code,tests)
                entry['after']=code;entry['judge']=evidence
        except services.HintError as exc:
            entry.update(status='blocked',error=str(exc))
        entry['seconds']=round(time.perf_counter()-started,3)
        report['steps'].append(entry);report['current_code']=code
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'turn':len(report['steps']),'status':entry['status'],'source':entry.get('source'),
             'pending':(entry.get('lesson_record') or {}).get('pending'),'judge':entry.get('judge',{}).get('label'),
             'completion':(entry.get('lesson_record') or {}).get('completion'),'seconds':entry['seconds']},ensure_ascii=True),flush=True)
        if entry['status']=='blocked':break


if __name__=='__main__':main()
