"""Real Docker regression replays, optionally one real local-model request."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');os.environ['HINT_MODE']='live'
import django
django.setup()
from coach.models import Problem
from coach.judging import judge
from coach.local_revision import apply_edits,check_candidate,RevisionError,digest
from coach.services import build_messages,generate_hint,HintError,PROMPT_VERSION
from coach import services


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if args.report.exists():raise SystemExit('Do not overwrite an experiment.')
    problem=Problem.objects.get(title__startswith='UVa 10041 ')
    initial=json.loads((ROOT/'training/examples/learner-vito-01.json').read_text(encoding='utf-8'))['code']
    tests=[{'name':'範例','input':problem.sample_input,'expected':problem.sample_output}]+problem.test_cases[:8]
    baseline=judge(initial,tests)
    report={'prompt_version':PROMPT_VERSION,'scope':'Known Vito regression replays with real restricted Docker. Optional live model call. No student study or all-topic claim.',
            'baseline':baseline,'replays':[]}
    median=initial.replace('int place = sum / r;','int place = houses[r / 2];')
    median_verdict=judge(median,tests)
    replays=[('identical_replacement',initial,baseline,[{'before':'int place = sum / r;','after':'int place = sum / r;'}],False),
             ('missing_sort_partial_progress',initial,baseline,[{'before':'int place = sum / r;','after':'int place = houses[r / 2];'}],True),
             ('place_before_input',median,median_verdict,[{'before':'        int place = houses[r / 2];\n','after':''},
                {'before':'        vector<int> houses(r);','after':'        vector<int> houses(r);\n        int place = houses[r / 2];'}],False),
             ('sort_at_main_start',median,median_verdict,[{'before':'#include <iostream>','after':'#include <algorithm>\n#include <iostream>'},
                {'before':'int main() {','after':'int main() {\n    sort(houses.begin(), houses.end());'}],False),
             ('correct_minimal_repair',initial,baseline,[{'before':'#include <iostream>','after':'#include <algorithm>\n#include <iostream>'},
                {'before':'int place = sum / r;','after':'sort(houses.begin(), houses.end());\n        int place = houses[r / 2];'}],True)]
    for name,code,old,edits,expected in replays:
        item={'name':name,'expected_publish':expected,'base_sha256':digest(code),'edits':edits}
        try:
            candidate=apply_edits(code,edits);result=judge(candidate,tests)
            error=check_candidate(old,result,tests,False)
            item.update(candidate=result,publish=error is None,error=error)
        except RevisionError as exc:item.update(publish=False,error=str(exc))
        item['check_pass']=item['publish']==expected;report['replays'].append(item)
    if args.live:
        started=time.monotonic();attempts=[];original=services._generate_once
        def capture(messages,level):
            reply=original(messages,level);attempts.append(str(reply));return reply
        messages=build_messages(problem,initial,'我用平均數選place，範例輸出131而非99。請依我的程式給最小局部修改，保留變數與迴圈，不要完整答案。',3,[],include_diagnostics=False)
        live={'original_code':initial,'original_sha256':digest(initial),'attempts':attempts}
        try:
            with patch('coach.services._generate_once',side_effect=capture):answer=generate_hint(messages,3)
            live.update(status='done',answer=str(answer),check=answer.revision_check,
                        source=answer.source,original_preserved=json.loads(messages[-1]['content'])['code']==initial)
        except HintError as exc:live.update(status='blocked',error=str(exc),original_preserved=True)
        live['seconds']=round(time.monotonic()-started,2);report['live']=live
    report['regression_replays_pass']=all(x['check_pass'] for x in report['replays'])
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'replays_pass':report['regression_replays_pass'],'live_status':report.get('live',{}).get('status'),'report':str(args.report)},ensure_ascii=True))
    return 0 if report['regression_replays_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
