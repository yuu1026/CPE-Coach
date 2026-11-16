"""Nine-turn scripted learner verification through live HTTP and local model.

Not a real student study: the learner's code/progress is authored in advance.
No generated replies are used for training during this evaluation.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
import httpx
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from coach.models import Problem,Submission
from coach.services import PROMPT_VERSION
from tools.test_live_system import GOOD,CUSTOM,EXPECTED

READ_ONLY='''#include <iostream>
#include <vector>
using namespace std;
int main() {
    int cases; cin >> cases;
    while(cases--) {
        int relatives; cin >> relatives;
        vector<int> addresses(relatives);
        for(int &address:addresses) cin >> address;
        // 我還沒選 home 或計算總距離
    }
}
'''
NO_SORT=GOOD.replace('sort(addresses.begin(), addresses.end());','')
NO_ABS=GOOD.replace('abs(address - home)','(address - home)')
STAGES=[
    ('start','','我完全沒有想法，請用一個小例子帶我理解題目，一次只問我一個問題，不要直接給完整解答。',1,None,
     '用具體小例子說明距離總和，一次一小步，不是多項輸入問卷。'),
    ('confirmed-goal','','我了解輸入是親戚地址、輸出是最小距離總和。我想先手算，下一步做什麼？',1,None,
     '承接已知目標，提出可做的小步驟，不重問輸入輸出。'),
    ('wrong-mean','','我先猜住在平均數。地址 1、2、100，我算 home 是 34、距離總和 131，這個猜法有問題嗎？先給提示。',1,None,
     '指出平均數不保證最小，以選2得99作反例或引導比對，不硬說131計算錯。'),
    ('even-median','','我比較後選 2 只要 99，所以想排序取中間。若有 4 個地址 1、2、100、101，中間有兩個，要怎麼選？',2,None,
     '承接中位數；選2或100或兩者間皆可，距離總和198，不能把平均數說成唯一最佳。'),
    ('read-code',READ_ONLY,'我已讀好資料放在 addresses。下一步想選 home 再算總距離，請沿用我的程式給一個小步驟，不要貼整題程式。',3,None,
     '引用目前讀入片段，局部提示排序/選中位數，保留變數，不把尚未完成硬當成編譯錯誤。'),
    ('missing-sort',NO_SORT,'我自己補上取中間及 abs，但測資有錯。請引用我的程式，只定位最主要問題，先不要貼完整解答。',2,'failed',
     '發現未排序就取 addresses[relatives/2]，用失敗案例說明，不歸因於平均數或未宣告home。'),
    ('signed-distance',NO_ABS,'我已加上排序，但自己算 distanceSum 還是不對。請只指出目前這一版該改哪個局部，保留我的變數。',3,'failed',
     '發現直接累加有正負的差值，應用abs，不能繼續指責已補上的sort。'),
    ('accepted-code',GOOD,'我已補上 sort 和 abs，也重新測試了。現在有已確認的錯誤嗎？請依目前版本回答，不要為修改而修改。',2,'accepted',
     '依目前實際通過結果確認提供測資通過，保留程式，不宣稱官方AC或捏造錯誤。'),
    ('transfer',GOOD,'我想確認自己懂了。若地址改成 1、2、1000，仍選 home=2，總距離應是多少？這組我沒有實際執行，請手算說明，不要貼完整程式。',2,None,
     '手算1+0+998=999，承接相同中位數原理，不假稱新輸入已實測。'),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only-stage',choices=[s[0] for s in STAGES],help='Explicit subset integration check, not a complete teaching evaluation')
    args=parser.parse_args()
    stages=[s for s in STAGES if not args.only_stage or s[0]==args.only_stage]
    if args.output.exists():raise RuntimeError('Refuse to overwrite an evaluation.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report={'scope':'Fixed nine-turn learner script on seen UVa10041. Actual HTTP/CSRF, local model and Docker. Learner code authored beforehand; not evidence that a real student learned. No model outputs used for training.',
        'acceptance':'Every reply done/live; no unrequested full program; no critical mathematical or code diagnosis error; each turn self-review >=4/5. Review is not independent teacher assessment.',
        'script_subset':args.only_stage,'stages':[{'id':s[0],'expected_behavior':s[-1]} for s in stages],'turns':[],'tests':[],'cleanup':False}
    def save():args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    save();owner=None;session_key=None
    client=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=270,follow_redirects=False)
    try:
        health=httpx.get('http://127.0.0.1:11436/healthz',timeout=5,trust_env=False)
        report['model_health']=health.json();health.raise_for_status()
        problem=Problem.objects.get(title__startswith='UVa 10041 ')
        password=secrets.token_urlsafe(32)
        owner=get_user_model().objects.create_user('tutoring-test-'+uuid.uuid4().hex[:12],password=password)
        def post(url,data):return client.post(url,data=dict(data,csrfmiddlewaretoken=client.cookies.get('csrftoken')))
        client.get('/login/')
        response=post('/login/',{'username':owner.username,'password':password})
        session_key=client.cookies.get('sessionid')
        if response.status_code!=302 or not session_key:raise RuntimeError('Login failed.')
        parent=None
        for name,code,question,level,expected_judge,expectation in stages:
            if expected_judge:
                data={'submission_id':str(uuid.uuid4()),'action':'test','code':code,'run_custom':'on','custom_input':CUSTOM,'custom_expected':EXPECTED}
                if parent:data['parent_submission']=parent.pk
                response=post(f'/problem/{problem.pk}/test/',data)
                if response.status_code!=200:raise RuntimeError(f'Test endpoint returned {response.status_code}')
                parent=Submission.objects.get(pk=response.json()['record'],owner=owner)
                report['tests'].append(dict(stage=name,expected=expected_judge,actual=parent.judge_result['status'],judge=parent.judge_result))
                if parent.judge_result['status']!=expected_judge:raise RuntimeError('Authored learner fixture verdict mismatch.')
            data={'submission_id':str(uuid.uuid4()),'action':'ask','code':code,'question':question,'hint_level':level,'run_custom':'on','custom_input':CUSTOM,'custom_expected':EXPECTED}
            if parent:data['parent_submission']=parent.pk
            print(name,'WAITING_FOR_LOCAL_MODEL',flush=True);started=time.monotonic()
            response=post(f'/problem/{problem.pk}/',data)
            if response.status_code!=302:raise RuntimeError(f'Ask returned {response.status_code}')
            pk=int(response.headers['location'].strip('/').split('/')[-1])
            parent=Submission.objects.get(pk=pk,owner=owner)
            payload=json.loads(parent.messages[-1]['content']) if parent.messages else {}
            if parent.prompt_version!=PROMPT_VERSION:
                report['deployment_mismatch']={'expected':PROMPT_VERSION,'actual':parent.prompt_version}
                raise RuntimeError('Website has not loaded the expected prompt version; restart the actual listening process.')
            report['turns'].append(dict(id=name,question=question,code=code,expected_behavior=expectation,answer=parent.answer,error=parent.error,
                status=parent.status,mode=parent.mode,model=parent.model,prompt_version=parent.prompt_version,
                seconds=round(time.monotonic()-started,2),editor_code_unchanged=parent.code==code,
                evidence_status=parent.judge_result.get('status'),message_count=len(parent.messages),
                scaffold_step=payload.get('verified_next_step',{}).get('step'),calculation_tool_used=bool(payload.get('verified_calculation')),
                tutoring_projection=bool(parent.messages and parent.messages[-1].get('tutoring_projection')),
                unrequested_main=bool(re.search(r'\b(?:int|auto|signed)\s+main\s*\(',parent.answer))))
            save();print(name,parent.status,report['turns'][-1]['seconds'],flush=True)
    except Exception as exc:
        report['fatal_error']=f'{type(exc).__name__}: {exc}';print('FATAL',report['fatal_error'],flush=True)
    finally:
        client.close()
        if session_key:Session.objects.filter(session_key=session_key).delete()
        if owner:owner.delete()
        report['cleanup']=True;save()
    print('REPORT',str(args.output),flush=True)
    if report.get('fatal_error') or len(report['turns'])!=len(stages):raise SystemExit(1)

if __name__=='__main__':main()
