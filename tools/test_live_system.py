"""Opt-in live HTTP/Docker/model verification with an ephemeral local account.

Requires already-running loopback services. Never stops services or executes
C++ on the host. Deletes only its own account/session; keeps an authored report.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
import httpx
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from coach.models import Problem,Submission,ProblemCompletion

BAD='''#include <cstdlib>
#include <iostream>
#include <vector>
using namespace std;
int main() {
    int cases;
    cin >> cases;
    while (cases--) {
        int relatives;
        cin >> relatives;
        vector<int> addresses(relatives);
        int addressSum = 0;
        for (int i = 0; i < relatives; ++i) {
            cin >> addresses[i];
            addressSum += addresses[i];
        }
        int home = addressSum / relatives;
        int distanceSum = 0;
        for (int address : addresses) distanceSum += abs(address - home);
        cout << distanceSum << '\\n';
    }
    return 0;
}
'''
GOOD='#include <algorithm>\n'+BAD.replace('int home = addressSum / relatives;','sort(addresses.begin(), addresses.end());\n        int home = addresses[relatives / 2];')
CUSTOM='6\n2 2 4\n3 2 4 6\n3 1 2 100\n3 10 100 1\n1 7\n4 5 5 5 5\n'
EXPECTED='2\n4\n99\n99\n0\n0\n'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Choose a new report path.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report={'started_at':datetime.now().astimezone().isoformat(),
        'scope':'Live HTTP with CSRF, actual Docker judge and local model. Cross-account access also checked with Django test client. Authored UVa 10041 fixtures. No visual browser QA or general model accuracy claim.',
        'checks':[],'model_turns':[],'cleanup':False}
    def save():args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def check(name,passed,**detail):
        report['checks'].append(dict(name=name,passed=bool(passed),**detail));save()
        print(name,'PASS' if passed else 'FAIL',flush=True)
    owner=None;session_key=None
    client=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=270,follow_redirects=False)
    try:
        response=httpx.get('http://127.0.0.1:11436/healthz',trust_env=False,timeout=5)
        check('model_health',response.status_code==200,health=response.json())
        response=client.get('/')
        check('anonymous_redirects_to_login',response.status_code==302 and '/login/' in response.headers.get('location',''))
        problem=Problem.objects.get(title__startswith='UVa 10041 ')
        other_count=Submission.objects.count()
        password=secrets.token_urlsafe(32)
        owner=get_user_model().objects.create_user('system-test-'+uuid.uuid4().hex[:12],password=password)
        client.get('/login/')
        def post(url,data,**kwargs):
            data=dict(data,csrfmiddlewaretoken=client.cookies.get('csrftoken'))
            return client.post(url,data=data,**kwargs)
        response=post('/login/',{'username':owner.username,'password':password})
        session_key=client.cookies.get('sessionid')
        check('login_with_csrf',response.status_code==302 and bool(session_key))
        if not session_key:raise RuntimeError('Login failed; cannot continue authenticated checks.')
        home=client.get('/')
        check('dashboard_and_cpe_topic',home.status_code==200 and 'Vito' in home.text,topic_count=Problem.objects.filter(category__startswith='CPE ').count())
        response=client.get('/choose-problem/',params={'problem':problem.pk})
        check('choose_vito',response.status_code==302 and response.headers.get('location')==f'/problem/{problem.pk}/')
        response=client.get(f'/problem/{problem.pk}/')
        check('workbench_and_assets',response.status_code==200 and client.get('/assets/coach/workbench.js').status_code==200)

        def submit_test(name,code,parent=None):
            data={'submission_id':str(uuid.uuid4()),'action':'test','code':code,'question':'draft must not be sent to model',
                  'hint_level':3,'run_custom':'on','custom_input':CUSTOM,'custom_expected':EXPECTED}
            if parent:data['parent_submission']=parent.pk
            started=time.monotonic()
            response=post(f'/problem/{problem.pk}/test/',data,headers={'Accept':'application/json'})
            if response.status_code!=200:raise RuntimeError(f'{name} HTTP {response.status_code}')
            record=Submission.objects.get(pk=response.json()['record'],owner=owner)
            check(name,record.status=='tested' and not record.answer and not record.question,
                seconds=round(time.monotonic()-started,2),judge=record.judge_result)
            return record

        def ask(name,code,question,parent=None):
            data={'submission_id':str(uuid.uuid4()),'action':'ask','code':code,'question':question,'hint_level':3,
                  'run_custom':'on','custom_input':CUSTOM,'custom_expected':EXPECTED}
            if parent:data['parent_submission']=parent.pk
            started=time.monotonic()
            print(name,'WAITING_FOR_REAL_MODEL',flush=True)
            response=post(f'/problem/{problem.pk}/',data)
            if response.status_code!=302:raise RuntimeError(f'{name} HTTP {response.status_code}')
            pk=int(response.headers['location'].strip('/').split('/')[-1])
            record=Submission.objects.get(pk=pk,owner=owner)
            report['model_turns'].append(dict(name=name,question=question,code=code,status=record.status,mode=record.mode,
                prompt_version=record.prompt_version,model=record.model,seconds=round(time.monotonic()-started,2),
                response_mode=json.loads(record.messages[-1]['content']).get('response_mode') if record.messages else None,
                evidence_status=record.judge_result.get('status'),answer=record.answer,error=record.error))
            check(name,record.status=='done' and record.mode=='live' and bool(record.answer),
                  status=record.status,seconds=report['model_turns'][-1]['seconds'])
            page=client.get(response.headers['location'])
            check(name+'_result_page',page.status_code==200 and ('Vito' in page.text))
            return record

        compile_record=submit_test('compile_error_request','#include <iostream>\nint main(){std::cout << 1 return 0;}')
        check('compile_error_detected',compile_record.judge_result.get('status')=='compile_error')
        start=ask('blank_code_guidance','','我完全沒有想法，請先引導理解這題，不要直接給完整解答。')
        wrong=submit_test('wrong_answer_request',BAD,start)
        check('wrong_answer_detected',wrong.judge_result.get('status')=='failed')
        diagnosis=ask('diagnose_existing_code',BAD,'我的輸出不符預期。請檢查 home 的選擇方式，引用我的原程式，保留 addresses、home、distanceSum，不要另換解法。',wrong)
        followup=ask('connected_followup',BAD,'請沿用我的 home 計算來解釋：地址 1、2、100，為什麼選 2 比選 34 好？',diagnosis)
        full=ask('corrected_program_request',BAD,'直接給我修正過的程式，保留我的變數與寫法。',followup)
        if full.answer:
            blocks=re.findall(r'```(?:cpp|c\+\+|cxx)\s*\n(.*?)```',full.answer,re.S|re.I)
            generated=next((b for b in blocks if re.search(r'\bmain\s*\(',b)),None)
            if generated:
                generated_test=submit_test('model_generated_program_test',generated,full)
                check('model_generated_program_passes',generated_test.judge_result.get('status')=='accepted')
            else:check('model_generated_program_present',False)
        correct=submit_test('correct_program_request',GOOD,full)
        check('correct_program_passes',correct.judge_result.get('status')=='accepted')
        response=post(f'/problem/{problem.pk}/completion/',{'state':'complete','return_submission':correct.pk})
        check('completion_saved',response.status_code==302 and ProblemCompletion.objects.filter(owner=owner,problem=problem).exists())
        response=client.get(f'/submission/{correct.pk}/')
        check('refresh_restores_code',response.status_code==200 and 'addresses' in response.text)
        second=get_user_model().objects.create_user('system-isolation-'+uuid.uuid4().hex[:12],password=secrets.token_urlsafe(32))
        try:
            from django.test import Client
            isolated=Client();isolated.force_login(second)
            check('other_account_cannot_read_record',isolated.get(f'/submission/{correct.pk}/').status_code==404)
        finally:
            Session.objects.filter(session_key=isolated.session.session_key).delete()
            second.delete()
        tests_before=Submission.objects.filter(owner=owner,action='test').count()
        response=post(f'/problem/{problem.pk}/clear-chat/',{})
        check('clear_chat_preserves_tests_and_completion',response.status_code==200 and
              not Submission.objects.filter(owner=owner,action='ask').exists() and
              Submission.objects.filter(owner=owner,action='test').count()==tests_before and
              ProblemCompletion.objects.filter(owner=owner,problem=problem).exists() and
              Submission.objects.filter(pk=correct.pk,owner=owner,code=GOOD).exists())
        check('existing_user_records_untouched',Submission.objects.exclude(owner=owner).count()==other_count)
    except Exception as exc:
        report['fatal_error']=f'{type(exc).__name__}: {exc}'
        print('FATAL',report['fatal_error'],flush=True)
    finally:
        client.close()
        if session_key:Session.objects.filter(session_key=session_key).delete()
        if owner:owner.delete()
        report['cleanup']=True
        report['finished_at']=datetime.now().astimezone().isoformat()
        report['functional_passes']=sum(x['passed'] for x in report['checks'])
        report['functional_total']=len(report['checks'])
        save()
        print('REPORT',str(args.output),'CHECKS',report['functional_passes'],report['functional_total'],flush=True)
    if report.get('fatal_error') or any(not item['passed'] for item in report['checks']):
        raise SystemExit(1)

if __name__=='__main__':main()
