"""Real Docker failure replay plus one isolated live base-model view request."""
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from coach.models import Problem,Submission
from coach.services import build_messages,generate_hint,HintError
from training.build_repair_data import fixtures

def main():
    dest=ROOT/'training/reports/runtime-validation-v14.json'
    if dest.exists():raise RuntimeError('Refuse to overwrite an existing check.')
    old=json.loads((ROOT/'training/reports/live-system-vito-v13-20261116.json').read_text(encoding='utf-8'))
    turn=next(r for r in old['model_turns'] if r['name']=='corrected_program_request')
    problem=Problem.objects.get(title__startswith='UVa 10041 ')
    messages=build_messages(problem,turn['code'],turn['question'],3,[])
    correction='原本的 `int home = addressSum / relatives;` 要改成排序後取中位數。\n```cpp\n'+fixtures('vito-mean','home')['good']+'```'
    with override_settings(HINT_MODE='live'),patch('coach.services._generate_once',side_effect=[turn['answer'],correction]) as model:
        recovered=generate_hint(messages,3)
    result={'scope':'Recorded wrong-answer replay uses fixed candidate responses and real Docker. Live section uses base model, Django view client and real Docker; not v7 model accuracy.',
            'wrong_answer_replay':{'calls':model.call_count,'corrected_candidate_passed': '組題庫測資' in recovered}}
    with override_settings(HINT_MODE='live'),patch('coach.services._generate_once',return_value=turn['answer']) as model:
        try:generate_hint(messages,3)
        except HintError as error:result['wrong_answer_replay']['repeated_failure_blocked']='仍未通過編譯或測資' in str(error)
    assert result['wrong_answer_replay']['corrected_candidate_passed'] and result['wrong_answer_replay'].get('repeated_failure_blocked')
    print('Recorded wrong answer blocked; audited correction passes real problem tests.',flush=True)
    owner=get_user_model().objects.create_user('validation-test-'+uuid.uuid4().hex[:12],password=secrets.token_urlsafe(32))
    client=Client();client.force_login(owner)
    try:
        print('LIVE_BASE_MODEL_REQUEST',flush=True)
        with override_settings(HINT_MODE='live',MODEL_NAME='gemma-3-4b-it'):
            response=client.post(f'/problem/{problem.pk}/',{'submission_id':str(uuid.uuid4()),'action':'ask','code':turn['code'],'question':turn['question'],'hint_level':3})
        record=Submission.objects.get(owner=owner)
        result['live_base_model']=dict(http_status=response.status_code,status=record.status,answer=record.answer,error=record.error,
            prompt_version=record.prompt_version,model=record.model,student_code_preserved=record.code==turn['code'])
        if record.status=='done':
            assert '組題庫測資' in record.answer
            result['live_base_model']['safety_outcome']='returned program after actual problem tests passed'
        elif record.status=='failed':
            assert not record.answer
            result['live_base_model']['safety_outcome']='no unverified full answer published'
        else:result['live_base_model']['safety_outcome']='partial or unexpected; manual review required'
    finally:
        Session.objects.filter(session_key=client.session.session_key).delete()
        owner.delete()
        result['temporary_account_deleted']=True
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result['live_base_model']['status'],result['live_base_model']['safety_outcome'],flush=True)

if __name__=='__main__':main()
