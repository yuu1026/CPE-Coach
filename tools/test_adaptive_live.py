"""Small real-model regression; no mocked replies or learner record changes."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
os.environ['HINT_MODE']='live'
os.environ['Model_Name']='gemma-3-4b-it'
import django
django.setup()
from coach.models import Problem
from coach.services import build_messages,generate_hint,HintError,PROMPT_VERSION


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'training/reports/adaptive-v30-live.json')
    path=parser.parse_args().output
    if path.exists():raise SystemExit('Refuse to overwrite evidence')
    problem=Problem.objects.filter(title__icontains='10041').first()
    if problem is None:raise SystemExit('Missing Vito problem')
    cases=[
        ('scaffold','','可以給我程式碼的雛型嗎？核心邏輯留給我自己完成。',[]),
        ('arithmetic','int main(){int a=2,b=9;return 0;}',
         '我照你的修改測試通過了。2、9與9、2的距離都應該是7，這樣對嗎？請手算確認，不要改程式。',[]),
    ]
    results=[]
    for name,code,question,history in cases:
        started=time.monotonic()
        messages=build_messages(problem,code,question,history=history)
        payload=json.loads(messages[-1]['content'])
        row={'case':name,'question':question,'code':code,'response_mode':payload['response_mode'],'learning_mode':payload.get('learning_mode')}
        try:
            reply=generate_hint(messages)
            row.update(status='delivered',answer=str(reply),source=getattr(reply,'source','model'))
        except HintError as exc:
            row.update(status='rejected',error=str(exc),audit=getattr(exc,'reply_audit',None))
        row['seconds']=round(time.monotonic()-started,2)
        results.append(row)
        path.write_text(json.dumps({'prompt_version':PROMPT_VERSION,'cases':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(row,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
