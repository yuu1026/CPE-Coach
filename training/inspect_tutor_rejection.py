"""Capture two real local candidate replies for one authored regression case."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');os.environ['HINT_MODE']='live'
import django
django.setup()
from coach.models import Problem
from coach import services
from coach.reply_quality import quality_issue,traditional_reply

def main():
    path=ROOT/'training/reports/tutoring-read-code-trace-v17.json'
    if path.exists():raise RuntimeError('Do not overwrite captured candidates.')
    report=json.loads((ROOT/'training/reports/tutoring-vito-v17-20261116.json').read_text(encoding='utf-8'))
    index=next(i for i,r in enumerate(report['turns']) if r['id']=='read-code')
    current=report['turns'][index]
    history=[{'question':r['question'],'hint':r['answer'],'code':r['code']} for r in report['turns'][:index] if r['status']=='done']
    messages=services.build_messages(Problem.objects.get(title__startswith='UVa 10041 '),current['code'],current['question'],3,history,{'status':'not_run','label':'目前程式與測資尚無可沿用的測試結果','cases':[]})
    original=services._generate_once;attempts=[];result={}
    def capture(prompt,level):
        reply=original(prompt,level)
        attempts.append({'answer':str(reply),'issue':quality_issue(traditional_reply(str(reply)),messages)})
        return reply
    with patch('coach.services._generate_once',side_effect=capture):
        try:result['answer']=str(services.generate_hint(messages,3))
        except services.HintError as exc:result['error']=str(exc)
    result.update(scope='Real local inference with reconstructed authored case; no student data.',attempts=attempts)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
