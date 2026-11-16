"""Record real service calls and system replies for manual quality review.

The wrapper observes real generation; it never supplies substitute replies.
No student accounts or submissions are created or modified.
"""
import json
import os
from pathlib import Path
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
import httpx
from coach import services
from coach.models import Problem
from coach.answer_validation import cpp_blocks
from coach.judging import judge


STUDENT='''#include <iostream>
#include <vector>
#include <cstdlib>
using namespace std;
int main() {
    int cases; cin >> cases;
    while (cases--) {
        int count; cin >> count;
        vector<int> houses(count);
        int sum = 0;
        for (int i = 0; i < count; ++i) {
            cin >> houses[i];
            sum += houses[i];
        }
        int place = sum / count;
        int total = 0;
        for (int i = 0; i < count; ++i) total += abs(houses[i] - place);
        cout << total << '\n';
    }
    return 0;
}
'''
TESTS=[{'name':'independent-six-cases',
        'input':'6\n3 1 2 100\n3 10 100 1\n1 7\n4 5 5 5 5\n2 2 4\n4 1 2 100 101\n',
        'expected':'99\n99\n0\n0\n2\n198\n'}]


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',help='Run one named case; preserve earlier evidence files')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refuse to overwrite evidence')
    with httpx.Client(trust_env=False,timeout=10) as client:
        health=client.get('http://127.0.0.1:11436/healthz')
        health.raise_for_status()
    problem=Problem.objects.get(title__icontains='10041')
    report={'prompt_version':services.PROMPT_VERSION,'health':health.json(),
            'method':'Real generation observed; system safeguards active; manual review required; no learner records changed.',
            'cases':[]}
    history=[]
    cases=[
        ('scope','', 'if 大括號內宣告的 int home，可以在大括號外使用嗎？如果保留它的參考，離開區塊後還能安全使用嗎？請解釋原因。'),
        ('division','int main(){int total=5; int count=2; double average=total/count;}',
         '請解釋 average 為什麼是 2 而不是 2.5，並提供必要的 C++ 局部示範。不要修改我的程式。'),
        ('overflow','int main(){int x=100000, y=100000; long long area=x*y;}',
         '請解釋 area 的乘法是否保證正確，以及 long long area = (long long)(x*y) 是否能解決問題？請提供局部示範，不用修改我的程式。'),
        ('scaffold','','可以給我這題程式碼的雛型嗎？需要可編譯的 C++17，核心邏輯留 TODO 給我自己完成。'),
        ('arithmetic','','地址是1、2、100，住在34的距離總和是不是131？請手算，不要給程式。'),
        ('continuation','','我懂為什麼34的總和是131了。那住在2的總和是多少？為什麼比較好？不要重新解釋輸入格式。'),
        ('student-repair',STUDENT,'請在我的原程式上給我完整修正後的 C++。保留 houses、place、total 和原本迴圈，請說明更改原因。'),
    ]
    for name,code,question in cases:
        if args.case and args.case!=name:continue
        row={'case':name,'code':code,'question':question,'raw_generations':[]}
        started=time.monotonic()
        evidence=None
        if name=='student-repair':
            evidence=judge(code,TESTS)
            row['baseline']=evidence
        messages=services.build_messages(problem,code,question,history=history if name=='continuation' else [],
                                        evidence=evidence,validation_tests=TESTS if name=='student-repair' else None)
        payload=json.loads(messages[-1]['content'])
        row['response_mode']=payload['response_mode']
        row['learning_mode']=payload.get('learning_mode')
        original=services._generate_once
        def observe(*a,**kw):
            begin=time.monotonic()
            try:
                reply=original(*a,**kw)
                row['raw_generations'].append({'text':str(reply),'truncated':getattr(reply,'truncated',False),'seconds':round(time.monotonic()-begin,2)})
                return reply
            except Exception as exc:
                row['raw_generations'].append({'error':str(exc),'seconds':round(time.monotonic()-begin,2)})
                raise
        try:
            with patch.object(services,'_generate_once',side_effect=observe):
                reply=services.generate_hint(messages)
            row.update(status='delivered',answer=str(reply),source=getattr(reply,'source','model'))
            if name=='arithmetic':history=[{'question':question,'hint':str(reply),'code':'','delivered':True}]
            if name=='student-repair':
                programs=[c for c in cpp_blocks(str(reply)) if 'main' in c]
                row['independent_judge']=[judge(c,TESTS) for c in programs]
        except services.HintError as exc:
            row.update(status='rejected',error=str(exc),audit=getattr(exc,'reply_audit',None),revision_audit=getattr(exc,'revision_audit',None))
        row['seconds']=round(time.monotonic()-started,2)
        report['cases'].append(row)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'case':name,'status':row['status'],'seconds':row['seconds'],'calls':len(row['raw_generations'])}),flush=True)


if __name__=='__main__':main()
