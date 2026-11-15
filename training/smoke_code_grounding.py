"""Small real-base-model smoke check of the app reply guard; not a benchmark.

Runs the same local quantized model directly, substituting only HTTP transport.
Does not execute student C++, use reference retrieval, or modify deployment.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['HF_USE_BASE_MODEL']='1'
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import override_settings
from coach.model_prompt import readable_messages
from coach.services import build_messages,generate_hint,HintText,HintError,PROMPT_VERSION
from local_model_server import load_model,fit_history,finish_reason

CASES=[
    ('loop-bound','加總 vector nums 的全部元素。',
     '#include <vector>\nint sum(const std::vector<int>& nums) { int total=0; for(int pos=0;pos<=nums.size();++pos) total+=nums[pos]; return total; }',
     '我的 total 累加有時會當掉，請針對我的程式找出原因，局部怎麼改？'),
    ('integer-average','求三個整數的平均值，需保留小數。',
     'double average(int a,int b,int c) { double result=(a+b+c)/3; return result; }',
     '為什麼我的 result 沒有小數？請沿用原本的變數與函式，只指出最小修正。'),
    ('multiplication-promotion','兩個 int 的乘積以 long long 保存。',
     'long long multiply(int left,int right) { long long product=left*right; return product; }',
     'product 已經是 long long，為什麼 left=50000、right=50000 還是不對？請在我的寫法上改。'),
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Choose a new output; never overwrite a report.')
    import torch
    tokenizer,model=load_model()
    rows=[]
    for name,statement,code,question in CASES:
        attempts=[]
        def local_completion(messages,level):
            readable=readable_messages(messages)
            selected,omitted=fit_history(tokenizer,readable,384,4096)
            inputs=tokenizer.apply_chat_template(selected,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to('cuda')
            with torch.inference_mode():
                generated=model.generate(**inputs,max_new_tokens=384,do_sample=False,repetition_penalty=1.1,pad_token_id=tokenizer.pad_token_id)
            ids=generated[0,inputs['input_ids'].shape[1]:]
            answer=tokenizer.decode(ids,skip_special_tokens=True)
            reason=finish_reason(ids,384,model.generation_config.eos_token_id)
            attempts.append(dict(answer=answer,finish_reason=reason))
            return HintText(answer,truncated=reason=='length',omitted_history_turns=omitted)
        messages=build_messages(SimpleNamespace(title='C++ 局部修正檢查',statement=statement),code,question,3,[],include_reference=False,include_diagnostics=False)
        try:
            with override_settings(HINT_MODE='live'),patch('coach.services._generate_once',side_effect=local_completion):
                answer=generate_hint(messages,3)
            result=dict(status='returned',answer=str(answer),truncated=answer.truncated)
        except HintError as exc:
            result=dict(status='rejected',error=str(exc))
        rows.append(dict(id=name,code=code,question=question,attempts=attempts,result=result))
        print(name,result['status'],len(attempts),flush=True)
    report=dict(prompt_version=PROMPT_VERSION,model='Gemma 3 4B IT base, NF4',
        scope='Three authored smoke cases, no independent grading, no student code execution, no quality-rate claim. App pipeline with direct model inference instead of HTTP.',results=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
