"""Application/controller + real Docker; injected model plan, NOT a neural eval."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');os.environ['HINT_MODE']='live'
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client
from coach.models import Problem,Submission
from coach.services import HintText,PROMPT_VERSION


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    if args.report.exists():raise SystemExit('Refuse to overwrite previous results.')
    report={'scope':'Injected deterministic model JSON, actual Django controller/templates and real restricted Docker. No actual model call or browser visual QA.',
            'prompt_version':PROMPT_VERSION,'checks':{},'cleanup':False}
    owner=None;session=None
    try:
        owner=get_user_model().objects.create_user('revision-test-'+uuid.uuid4().hex[:12])
        client=Client();client.force_login(owner);session=client.cookies['sessionid'].value
        problem=Problem.objects.get(title__startswith='UVa 10041 ')
        code=json.loads((ROOT/'training/examples/learner-vito-01.json').read_text(encoding='utf-8'))['code']
        plan={'explanation':'讀完地址後先排序，再取中間值選址，保留原本的距離累加。',
              'edits':[{'line_id':'L1','after':'#include <algorithm>\n#include <iostream>'},
                       {'line_id':'L15','after':'        sort(houses.begin(), houses.end());\n        int place = houses[r / 2];'}]}
        data={'submission_id':str(uuid.uuid4()),'action':'ask','code':code,'question':'請依我的程式給局部修改，保留變數與迴圈。','hint_level':3,
              'run_custom':'on','custom_input':'1\n4 101 2 100 1\n','custom_expected':'198\n'}
        with patch('coach.services._generate_once',return_value=HintText(json.dumps(plan,ensure_ascii=False))) as model:
            response=client.post(f'/problem/{problem.pk}/',data)
            record=Submission.objects.get(owner=owner)
            check=record.messages[-1].get('verified_revision',{})
            page=client.get(response.url)
            report['checks'].update(original_unchanged=record.code==code,
                editor_not_marked_passed=record.judge_result['status']=='not_run',
                actual_base_and_candidate_saved=bool(check.get('baseline')) and check.get('candidate',{}).get('status')=='accepted',
                custom_case_verified=len(check.get('candidate',{}).get('cases',[]))==4,
                apply_and_undo_controls=b'id="apply-revision"' in page.content and b'id="undo-revision"' in page.content)
            report['verification']=check
            if not all(report['checks'].values()):raise RuntimeError('Application revision checks failed')
            test_response=client.post(f'/problem/{problem.pk}/test/',dict(data,action='test',code=check['candidate_code'],
                parent_submission=record.pk,submission_id=str(uuid.uuid4())))
            result=Submission.objects.get(owner=owner,pk=test_response.json()['record'])
            report['checks'].update(explicit_test_passed=result.judge_result['status']=='accepted',
                                    explicit_test_did_not_call_model=model.call_count==1)
            report['student_test']=result.judge_result
    except Exception as exc:report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if session:Session.objects.filter(session_key=session).delete()
        if owner:owner.delete()
        report['cleanup']=True
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    passed=not report.get('error') and bool(report['checks']) and all(report['checks'].values())
    print(json.dumps({'passed':passed,'checks':report['checks'],'error':report.get('error')},ensure_ascii=True))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
