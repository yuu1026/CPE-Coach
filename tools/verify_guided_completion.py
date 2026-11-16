"""Actual model requests; apply only C++ additions delivered in each reply.

Known Vito curriculum verification, not blind pedagogy or a student study.
Final oracle enumerates all possible integer homes independently of median.
"""
import json
import argparse
import os
from pathlib import Path
import random
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
os.environ['HINT_MODE']='live'
import django
django.setup()
from coach.models import Problem
from coach.services import build_messages,generate_hint,PROMPT_VERSION
from coach.judging import judge

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,default=ROOT/'training/reports/guided-completion-v23.json')
    parser.add_argument('--request',type=Path,default=ROOT/'training/examples/tutoring-start.json')
    parser.add_argument('--steps',type=int,default=4)
    args=parser.parse_args();target=args.report
    if target.exists():raise SystemExit('Report exists; preserve the recorded run.')
    problem=Problem.objects.get(title__startswith='UVa 10041 ')
    request=json.loads(args.request.read_text(encoding='utf-8'))
    code=request['code'];history=[]
    rng=random.Random(230041)
    arrays=[[1],[1,2,100],[101,2,100,1],[5,5,5,5]]
    arrays += [[rng.randint(1,80) for _ in range(rng.randint(1,15))] for _ in range(80)]
    # Exhaustive location enumeration is independent from the teaching rule.
    expected=[min(sum(abs(x-home) for x in xs) for home in range(min(xs),max(xs)+1)) for xs in arrays]
    test={'name':'84組獨立枚舉位置對照','input':str(len(arrays))+'\n'+'\n'.join(str(len(xs))+' '+' '.join(map(str,xs)) for xs in arrays)+'\n',
          'expected':'\n'.join(map(str,expected))+'\n'}
    report={'prompt_version':PROMPT_VERSION,'scope':'Known-topic adaptive delivery, authored insertion location, real local model and Docker; not independent model teaching or real learner evidence.', 'steps':[]}
    try:
        for number in range(args.steps):
            question='我已加入上一步，接下來只教一個步驟，請提供局部片段。' if history else request['question']
            started=time.monotonic()
            answer=generate_hint(build_messages(problem,code,question,3,history,include_diagnostics=False),3)
            blocks=re.findall(r'```cpp\s*\n(.*?)\n```',str(answer),re.S)
            if not blocks or answer.truncated:raise RuntimeError('No complete delivered addition')
            before=code
            # Use delivered text only, never the hidden curriculum plan.
            for block in blocks:
                if block.strip().startswith('#include'):
                    if block.strip() not in code:code=block.strip()+'\n'+code
                elif '放置位置：排序之後' in str(answer):
                    # Follow the delivered location, including repair of an
                    # earlier missing declaration before existing uses.
                    anchor=re.search(r'(?:std::)?sort\([^;]+;',code)
                    if not anchor:raise RuntimeError('Cannot locate delivered placement')
                    code=code[:anchor.end()]+'\n'+block+code[anchor.end():]
                else:code=code.replace('// 下一步放這裡',block+'\n        // 下一步放這裡')
            compilation=judge(code,[])
            entry={'question':question,'before':before,'answer':str(answer),'source':answer.source,
                   'after':code,'compile':compilation,'seconds':round(time.monotonic()-started,2)}
            report['steps'].append(entry)
            if compilation['status']!='accepted':raise RuntimeError('Delivered addition did not compile')
            history.append({'question':question,'code':before,'hint':str(answer)})
        report['final_judge']=judge(code,[test]);report['independent_cases']=len(arrays)
        report['system_completion_pass']=report['final_judge']['status']=='accepted'
        report['model_only_completion_pass']=report['system_completion_pass'] and all(s['source']=='model' for s in report['steps'])
    except Exception as exc:
        report['error']=str(exc);report['system_completion_pass']=False;report['model_only_completion_pass']=False
    finally:
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(target),'system_pass':report['system_completion_pass'],'model_only_pass':report['model_only_completion_pass'],'error':report.get('error')},ensure_ascii=True))
    return 0 if report['system_completion_pass'] else 1

if __name__=='__main__':raise SystemExit(main())
