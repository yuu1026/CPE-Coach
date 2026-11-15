"""Replay the recorded Vito failure through real Docker, not fresh inference."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import override_settings
from coach.services import build_messages,generate_hint,HintError
from training.build_repair_data import fixtures

def main():
    path=ROOT/'training/reports/gemma3-quality-v6/compile_guard_replay.json'
    if path.exists():raise RuntimeError('Refuse to overwrite prior report.')
    report=json.loads((ROOT/'training/reports/live-system-vito-20261116-retry.json').read_text(encoding='utf-8'))
    turn=next(t for t in report['model_turns'] if t['name']=='corrected_program_request')
    messages=build_messages(SimpleNamespace(statement='UVa 10041：最小化到各地址的距離總和。'),turn['code'],turn['question'],3,[])
    correction='原本的 `int home = addressSum / relatives;` 應改為排序後取中位數，並在迴圈可使用的外層宣告。\n```cpp\n'+fixtures('vito-mean','home')['good']+'```'
    with override_settings(HINT_MODE='live'),patch('coach.services._generate_once',side_effect=[turn['answer'],correction]) as model:
        recovered=generate_hint(messages,3)
    recovered_calls=model.call_count
    error=''
    with override_settings(HINT_MODE='live'),patch('coach.services._generate_once',return_value=turn['answer']) as model:
        try:generate_hint(messages,3)
        except HintError as exc:error=str(exc)
    result=dict(scope='Recorded bad response plus deterministic audited correction; real Docker compile only, no fresh model inference, no runtime tests.',
        recovery_calls=recovered_calls,recovered_compile_label='通過 C++17 編譯檢查' in recovered,
        repeated_failure_calls=model.call_count,repeated_failure_blocked='仍未通過編譯' in error,error=error,
        original_student_code_preserved=json.loads(messages[-1]['content'])['code']==turn['code'])
    assert result['recovery_calls']==2 and result['recovered_compile_label']
    assert result['repeated_failure_calls']==2 and result['repeated_failure_blocked'] and result['original_student_code_preserved']
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Recorded failure blocked; corrected candidate compiles; second failure blocked. No model-quality claim.')

if __name__=='__main__':main()
