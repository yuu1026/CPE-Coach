"""Validation-driven revision: grounded problem notes and more concrete contrasts.

Dev cases informed these changes; only the untouched test split is final evaluation.
No reference program is included in any model prompt.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import argparse
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from coach.services import build_messages,PROMPT_VERSION
from training.topic_facts import FACTS

CORRECTED_KEYWORDS={10062:['空格','空白','32',"c!=' '"],10226:['空行','換行','分隔'],
    11321:['遞減','降序','x>y','奇數'],11349:['中心','n*n-1','180','對角線','對應']}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh-test-only',action='store_true',help='Require train/eval to remain byte-identical')
    args=parser.parse_args()
    src=ROOT/'training/data/quality-v3'; dest=ROOT/'training/data/quality-v4'
    catalog={p['uva']:p for p in json.loads((ROOT/'data/cpe49.json').read_text(encoding='utf-8'))}
    if set(catalog)!=set(FACTS): raise ValueError('Each catalog topic must have curated notes.')
    notes={str(n):{'statement_sha256':hashlib.sha256(p['statement'].encode()).hexdigest(),'notes':FACTS[n],
        'source':p['source'],'provenance':'project-curated problem facts; not an execution verdict or independent teacher review'} for n,p in catalog.items()}
    (ROOT/'data/cpe-learning-notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sets={}
    for split in ['train','eval','test']:
        rows=[]
        for old in map(json.loads,(src/f'{split}.jsonl').read_text(encoding='utf-8').splitlines()):
            payload=json.loads(old['messages'][-2]['content'])
            problem=SimpleNamespace(title=payload['problem_title'],statement=payload['problem'],sample_input=payload['sample_input'],sample_output=payload['sample_output'])
            history=[]
            for i in range(1,len(old['messages'])-2,2):
                previous=json.loads(old['messages'][i]['content'])
                history.append({'question':previous['question'],'hint':old['messages'][i+1]['content'],'code':previous.get('previous_code_excerpt','')})
            evidence=payload.get('execution_evidence')
            if evidence:
                # Preserve existing bounded evidence exactly, rather than inventing runs.
                messages=build_messages(problem,payload['code'],payload['question'],old['hint_level'],history,include_reference=False)
                revised=json.loads(messages[-1]['content']); revised['execution_evidence']=evidence
                messages[-1]['content']=json.dumps(revised,ensure_ascii=False)
            else:
                messages=build_messages(problem,payload['code'],payload['question'],old['hint_level'],history,include_reference=False)
            target=old['messages'][-1]['content']
            if old['problem_id']==10226:
                target=target.replace('先檢查 `` 這一段。','先檢查案例之間應輸出空行的位置。')
            row=dict(old,id=old['id'].replace('quality-','quality-v4-',1),messages=messages+[{'role':'assistant','content':target}],rubric=dict(old['rubric']))
            if row['variant']=='heldout-bug' and row['problem_id'] in CORRECTED_KEYWORDS:
                row['rubric']['concept_any']=CORRECTED_KEYWORDS[row['problem_id']]
            rows.append(row)
        sets[split]=rows
    additions=[
        ('空字串 s、j=0，j < s.size() 會成立嗎？','不會。空字串的 size() 是 0，條件變成 0 < 0，結果為 false。若這是三元運算子的條件，會走填補字元的分支，不會讀取 s[0]；接著應檢查填補內容是否符合題意。'),
        ('預期與實際數值都一樣，只少了一行空白，應修改計算公式嗎？','先不要修改公式。數值相同而只缺少空行，應優先檢查案例之間的換行輸出。修改計算公式反而可能破壞原本正確的數值；先補回那個分隔，再重跑。'),
        ('60 min 是 1 deg 還是 3600 deg？','角度中的 60 min 等於 1 deg，所以角分轉角度要除以 60，不是乘以 60。先用同一角度的兩種寫法檢查換算，再處理角度轉弧度。'),
        ('sort 裡 return odd ? x < y : x < y; 能讓奇數遞減嗎？','不能。這兩個分支都是 x < y，奇數與偶數都會升冪。若題目要求奇數遞減，只把奇數分支改為 x > y；偶數分支仍保持 x < y。'),
        ('請只解釋 R 和 L 的轉向，不要換成其他指令。','在這題的機器人指令中，R 是向右轉 90 度，L 是向左轉 90 度；轉向只改朝向，不會移動座標。前進是 F 的工作，不應把 R 說成左轉。'),
        ('程式碼沒有提供，我可以憑題意直接認定是哪行錯嗎？','不可以。題意只告訴我們正確行為，不能直接指出尚未看到的程式錯誤。請先提供目前的相關片段或失敗輸出，再把實際行為和題意比對；不要憑常見錯誤硬套。'),
    ]
    generic=SimpleNamespace(title='C++17 對照教學',statement='回答當前 C++17 學習問題，不存在可用的程式執行紀錄。',sample_input='',sample_output='')
    for i,(question,target) in enumerate(additions):
        messages=build_messages(generic,'',question,2,[],include_reference=False)
        sets['train'].append({'id':f'quality-v4-contrast-{i}','problem_id':0,'variant':'contrast','hint_level':2,
            'provenance':'GPT/Codex-authored validation-driven contrast; not independent teacher review',
            'messages':messages+[{'role':'assistant','content':target}],
            'rubric':{'concept_any':[],'evidence_status':'not_submitted','full_solution':False},'tests':[]})
    refs=json.loads((ROOT/'data/cpe49-solutions.json').read_text(encoding='utf-8'))
    audits={r['uva']:r for r in map(json.loads,(ROOT/'training/data/cpe49/verified_programs.jsonl').read_text(encoding='utf-8').splitlines()) if r['variant']=='correct'}
    for number,variant,question,target in [
        (12019,'accepted-final','本次測資已全數通過，目前一定要再改嗎？','目前提供的測資已全數通過，沒有新的失敗證據就保留程式，不必為了修改而修改。這不等於所有合法輸入皆正確。'),
        (272,'changed-final','我在程式最後加了註解但還沒重跑，可以說這一版已經通過測試嗎？','加註解通常不改變程式行為，但沒有重新執行，就不能說這一版已經實際通過測試。先前的紀錄屬於舊版；若需要目前版本的測試結果，請重新執行。')]:
        item=catalog[number]
        problem=SimpleNamespace(title=f"UVa {number} · {item['title']}",statement=item['statement'],sample_input=item['tests'][0]['input'],sample_output=item['tests'][0]['expected'])
        code=refs[str(number)]['code']
        evidence=audits[number]['judge'] if variant=='accepted-final' else {'status':'not_run','label':'修改後尚未重新執行','cases':[]}
        history=[] if variant=='accepted-final' else [{'question':'舊版通過了嗎？','hint':'之前的版本通過當時提供的測資。','code':code}]
        if history:code+='\n// updated version\n'
        messages=build_messages(problem,code,question,1,history,evidence,include_reference=False)
        sets['test'].append({'id':f'quality-v4-uva{number}-{variant}','problem_id':number,'variant':variant,'hint_level':1,
            'provenance':'GPT/Codex-authored held-out evidence consistency case; no test outputs used for tuning',
            'messages':messages+[{'role':'assistant','content':target}],
            'rubric':{'concept_any':['通過','保留','不必'] if variant=='accepted-final' else ['尚未','未','不能','重新'],
                'evidence_status':evidence['status'],'full_solution':False},'tests':item['tests']})
    dest.mkdir(parents=True,exist_ok=True)
    serialized={split:''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows) for split,rows in sets.items()}
    if args.refresh_test_only:
        for split in ['train','eval']:
            if (dest/f'{split}.jsonl').read_text(encoding='utf-8')!=serialized[split]:
                raise RuntimeError(f'{split} changed; cannot rewrite data used by an active training run')
    for split,rows in sets.items():
        if not args.refresh_test_only or split=='test':
            (dest/f'{split}.jsonl').write_text(serialized[split],encoding='utf-8')
    manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))
    manifest.update(version='quality-v4',prompt_version=PROMPT_VERSION,
        train_records=len(sets['train']),test_records=len(sets['test']),sha256={split:hashlib.sha256((dest/f'{split}.jsonl').read_bytes()).hexdigest() for split in sets},
        provenance=manifest['provenance']+'; v4 adds project-curated spec notes and six contrasts informed by dev failures',
        evaluation_scope='Dev-informed curriculum and grounding. UVa topic IDs remain disjoint; concepts overlap. Only the untouched test situations are final evaluation.',
        changes=['spec notes added to both base/adapter prompts','six dev-informed contrast examples','corrected concept rubrics for four dev bugs; v3 heuristic counts are not directly comparable'])
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({k:len(v) for k,v in sets.items()})

if __name__=='__main__':main()
