"""Paired raw base/adapter generation. Heuristic rubrics are NOT semantic accuracy.

No app language conversion, answer lookup, repair retry, or formatter is applied.
Full generated C++ is executed only inside the existing isolated Docker judge.
"""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from opencc import OpenCC
from coach.reply_quality import quality_issue, map_prose
from coach.judging import judge
from coach.model_prompt import readable_messages
from local_model_server import fit_history, finish_reason
from model_backend import model_path, load_text_model, validate_adapter

def score(row,answer,reason):
    rubric=row['rubric']
    flags={'traditional_prose':map_prose(answer,OpenCC('s2t').convert)==answer,
        'language_and_repetition':quality_issue(answer,row['messages'][:-1]) is None,
        'complete':reason=='stop',
        'requested_concept':not rubric['concept_any'] or any(word.lower() in answer.lower() for word in rubric['concept_any']),
        'no_unrequested_full_code':rubric['full_solution'] or not re.search(r'\bint\s+main\s*\(',answer)}
    if rubric['evidence_status'] in ('not_run','not_submitted'):
        claims=[]
        for sentence in re.split(r'[。！？\n]',answer):
            if re.search(r'不能|無法|不代表|不等於|尚未|沒有|未執行|不應',sentence): continue
            if re.search(r'已經?(通過|執行|編譯)|測資全(數|部)通過|保證.*AC',sentence): claims.append(sentence)
        flags['no_unsupported_execution']=not claims
    if rubric['full_solution']:
        match=re.search(r'```(?:cpp|c\+\+|cxx)\s*\n(.*?)```',answer,re.S|re.I)
        result=judge(match[1],row['tests']) if match else {'status':'missing_cpp'}
        flags['generated_code_passes_tests']=result['status']=='accepted'
        return flags,result
    return flags,None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--adapter',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,default=ROOT/'training/data/quality-v3')
    parser.add_argument('--split',choices=['eval','test'],default='eval')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plain-prompts',action='store_true',help='Evaluate the readable app transport, keeping retrieval/repair disabled')
    args=parser.parse_args()
    if args.output.exists(): raise RuntimeError('Output exists; choose a new report path.')
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer,BitsAndBytesConfig
    validate_adapter(args.adapter,model_path())
    rows=[json.loads(line) for line in (args.data_dir/f'{args.split}.jsonl').read_text(encoding='utf-8').splitlines()]
    tokenizer=AutoTokenizer.from_pretrained(str(model_path()),local_files_only=True)
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    base=load_text_model(model_path(),device_map={'':0},quantization_config=quant,dtype=torch.bfloat16,attn_implementation='sdpa')
    model=PeftModel.from_pretrained(base,str(args.adapter),is_trainable=False,local_files_only=True)
    model.eval(); results=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for row in rows:
        result={'id':row['id'],'problem_id':row['problem_id'],'question':json.loads(row['messages'][-2]['content'])['question'],
            'reference_target':row['messages'][-1]['content'],'rubric':row['rubric']}
        maximum=1024 if row['rubric']['full_solution'] else 384
        prompt=readable_messages(row['messages'][:-1]) if args.plain_prompts else row['messages'][:-1]
        messages,omitted=fit_history(tokenizer,prompt,maximum,4096)
        inputs=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to('cuda')
        for label in ('base','adapter'):
            started=time.monotonic()
            context=model.disable_adapter() if label=='base' else nullcontext()
            with context,torch.inference_mode():
                output=model.generate(**inputs,max_new_tokens=maximum,do_sample=False,repetition_penalty=1.1,pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            tokens=output[0][inputs['input_ids'].shape[-1]:]
            answer=tokenizer.decode(tokens,skip_special_tokens=True)
            reason=finish_reason(tokens.tolist(),maximum,model.generation_config.eos_token_id)
            flags,code_result=score(row,answer,reason)
            result[label]={'answer':answer,'finish_reason':reason,'tokens':len(tokens),
                'seconds':round(time.monotonic()-started,2),'checks':flags,'rule_pass':all(flags.values()),'code_judge':code_result}
        results.append(result)
        args.output.with_suffix('.partial.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{row['id']}: base={result['base']['rule_pass']} adapter={result['adapter']['rule_pass']}",flush=True)
    # An unscored plain-language probe helps distinguish prompt overload from
    # a basic capability/loading problem. It is not an independent benchmark.
    probe=[{'role':'user','content':'請用繁體中文直接回答：a 和 b 都是 int，為什麼 long long ans = a * b 仍可能溢位？請示範一行 C++17 修正，不要反問。'}]
    probe_inputs=tokenizer.apply_chat_template(probe,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to('cuda')
    sanity={}
    for label in ('base','adapter'):
        with (model.disable_adapter() if label=='base' else nullcontext()),torch.inference_mode():
            output=model.generate(**probe_inputs,max_new_tokens=160,do_sample=False,repetition_penalty=1.1,pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
        sanity[label]=tokenizer.decode(output[0][probe_inputs['input_ids'].shape[-1]:],skip_special_tokens=True)
    summary={label:{'rule_passed':sum(r[label]['rule_pass'] for r in results),'total':len(results),
        'by_check':{key:sum(r[label]['checks'].get(key,True) for r in results) for key in sorted({k for r in results for k in r[label]['checks']})}} for label in ('base','adapter')}
    report={'split':args.split,'adapter':args.adapter.name,'dataset_sha256':hashlib.sha256((args.data_dir/f'{args.split}.jsonl').read_bytes()).hexdigest(),
        'summary':summary,'prompt_transport':'readable app transport' if args.plain_prompts else 'structured JSON baseline','unscored_plain_language_sanity_probe':sanity,'scope':'Raw paired outputs. Rule pass is a heuristic compliance score, NOT independent semantic accuracy. Explicit full-answer code is judged on authored cases only. Retrieval answers, audited hints and repair retries are disabled. Read every output before deployment.', 'results':results}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
