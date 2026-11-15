"""Build a versioned synthetic tutoring set with topic-disjoint splits and audit links."""
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'training'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from coach.services import build_messages, PROMPT_VERSION
from coach.code_format import format_cpp
from training.build_data import CATALOG
from training.cpe49_mutations import MUTATIONS, FOCUS
from training.quality_dialogues import DIALOGUES

DEST = ROOT/'training/data/quality-v3'
DEV = {118,490,10062,10221,10226,11321,11349}
TEST = {272,948,10056,10193,10415,10908,12019}
PROVENANCE = 'GPT/Codex-authored targets and dialogue seeds, assembled with project-authored mutation labels; no external API call or independent teacher review'
KEYWORDS = {
    118:['氣味','scent','同一','危險'],490:['空格','補','缺字'],10062:['ASCII','字元','編碼','遞減','排序'],
    10221:['角度','minute','分','60','單位'],10226:['空格','整行','getline','名稱'],11321:['負數','餘數','%'],11349:['負','非負','0'],
    272:['跨行','引號','狀態','重設'],948:['相等','<=','位權','等於'],10056:['玩家','整輪','指數','次數'],
    10193:['二進位','進位','基底','2'],10415:['手指','指法','B','集合'],10908:['邊界','中心','範圍','座標'],12019:['2011','星期','日期','固定'],
}

def dump(path, rows):
    path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')

def row(item, variant, question, answer, code='', evidence=None, history=None, level=1, keywords=None):
    problem = SimpleNamespace(statement=item['statement'],title=f"UVa {item['uva']} · {item['title']}",
        sample_input=item['tests'][0]['input'],sample_output=item['tests'][0]['expected'])
    messages = build_messages(problem,code,question,level,history or [],evidence,include_reference=False,include_topic_notes=False)
    return {'id':f"quality-uva{item['uva']}-{variant}", 'problem_id':item['uva'], 'variant':variant,
        'hint_level':level,'provenance':PROVENANCE,'messages':messages+[{'role':'assistant','content':answer}],
        'rubric':{'concept_any':keywords or [], 'evidence_status':(evidence or {}).get('status','not_submitted'),
                  'full_solution': 'solution' == json.loads(messages[-1]['content'])['response_mode']},
        'tests':item['tests']}

def main():
    catalog = json.loads((ROOT/'data/cpe49.json').read_text(encoding='utf-8'))
    originals = {p['uva']:p for p in CATALOG}
    refs = json.loads((ROOT/'data/cpe49-solutions.json').read_text(encoding='utf-8'))
    audits = {(r['uva'],r['variant']):r for r in map(json.loads,(ROOT/'training/data/cpe49/verified_programs.jsonl').read_text(encoding='utf-8').splitlines())}
    train, dev, test = [], [], []
    for item in catalog:
        n=item['uva']; correct=refs[str(n)]['code']
        mutations=[(m[0],m[1],*m[3:]) for m in originals[n]['mutations'][:2]] if n in originals else MUTATIONS[n]
        programs=[]
        for label,mutation in zip(('bug_train','bug_eval'),mutations):
            old,new,*hints=mutation
            if correct.count(old)!=1: raise ValueError(f'Ambiguous mutation {n}')
            code=correct.replace(old,new)
            digest=hashlib.sha256(json.dumps({'code':code,'tests':item['tests'],'policy':'cpp17-docker-v2'},sort_keys=True).encode()).hexdigest()
            audit=audits[n,label]
            if audit['sha256']!=digest or audit['judge']['status']!='failed': raise ValueError(f'Audit mismatch {n}')
            programs.append((code,mutation,audit))
        if n in DEV or n in TEST:
            code,mutation,audit=programs[1]; old,new,*hints=mutation
            target=f'先檢查 `{new}` 這一段。{hints[1]}{hints[2]}只針對這個局部修改，再重跑目前失敗的測資。'
            sample=row(item,'heldout-bug','我看過輸出不符了，請定位第一個應檢查的條件，說明下一步，不要只重述測資失敗。',target,code,audit['judge'],level=2,keywords=KEYWORDS[n])
            sample['audit_sha256']=audit['sha256']
            (dev if n in DEV else test).append(sample)
            continue
        code,mutation,audit=programs[0]; old,new,*hints=mutation
        failing=next(case for case in audit['judge']['cases'] if case['status']!='accepted')
        trace=f"其中一筆預期輸出是 `{failing['expected'].strip()[:80]}`，實際是 `{failing['actual'].strip()[:80]}`。"
        targets=[f'這一版確實有測資輸出不符。{trace}{hints[0]}先只追蹤這個問題，不必重寫整題。',
            f'先看目前程式的 `{new}`。{hints[1]}{trace}把第一次偏離題意的位置記下來，再決定局部修正。',
            f'目前的 `{new}` 是應優先檢查的局部。{hints[2]}修改後重跑失敗案例，確認差異是否消失；不要同時改動其他部分。']
        for level,target in enumerate(targets,1):
            example=row(item,f'diagnosis-l{level}','請依提示程度協助我定位目前的錯誤，不要給完整答案。',target,code,audit['judge'],level=level)
            example['audit_sha256']=audit['sha256']; train.append(example)
        good=audits[n,'correct']
        train.append(row(item,'accepted','本次所有測資通過，還有一定要改的地方嗎？',
            '目前程式通過本次提供的全部測資，沒有已確認的錯誤就先保留。不要為了修改而修改；這仍不等於官方評測一定通過。如果你想理解某一段，可以只討論那段。',correct,good['judge']))
        none={'status':'not_run','label':'本次尚未執行','cases':[]}
        train.append(row(item,'no-evidence','我改過程式但還沒重跑，可以沿用之前通過的結果嗎？',
            '不能沿用舊版本的通過結論。這一版沒有可用的執行紀錄，我只能先做靜態分析；請先重跑測試，再依新的實際結果判斷。',correct,none))
        train.append(row(item,'scope','請直接說明這題最容易看錯的條件，不要反問輸入輸出是什麼。',
            FOCUS[n]+'先把這個條件和範例對照，再決定如何保存讀到的資料。現在可以先處理這一點，不必一次完成整題。'))
        history=[{'question':'請幫我找第一個應檢查的位置。','hint':targets[1],'code':code}]
        train.append(row(item,'followup',f'我已經找到 `{new}` 了，不用再告訴我定位結果，接下來怎麼修？',
            f'對，現在就針對這個局部往下修。{hints[2]}改好後先重跑那一筆失敗測資，其他已確認的部分先保留。',code,audit['judge'],history,level=3))
        train.append(row(item,'rephrase','你一直重複測資失敗，我已經知道了。請換一個具體的檢查方式。',
            f'好，不再只重述失敗結果。請把 `{new}` 的執行前後值單獨記下來。{hints[1]}先比較這一步和題意的差異，還不必改寫整個演算法。',code,audit['judge'],history,level=2))
        # Full-code targets are opt-in only, drawn from already audited references.
        if len(correct)<700:
            train.append(row(item,'requested-solution','請直接給我這題的完整 C++17 解答。',
                '你已明確要求完整解答，以下是 C++17 參考程式。\n```cpp\n'+format_cpp(correct)+'```\n這份參考程式有專案自編測資通過紀錄，不代表你目前的程式已通過官方評測。'))
    generic={'uva':0,'title':'C++ 教學對話','statement':'回答學生的 C++17 程式學習問題，沒有程式執行紀錄，不可聲稱已通過測試。','tests':[{'input':'','expected':''}]}
    for i,(question,target,prior,reply) in enumerate(DIALOGUES):
        history=[{'question':prior,'hint':reply,'code':''}] if prior else []
        train.append(row(generic,f'conversation-{i:02}',question,target,history=history))
    # Independently authored held-out dialogues: no target is copied into training.
    extra=[
        ('dev-next-step','現在我知道要把變數先提升再相乘，不用再解釋 int 上限。可給我一行局部修正嗎？','可以，讓乘法在足夠大的型別中進行：\n```cpp\nlong long total = 1LL * count * price;\n```\n這只修正中間運算型別，不需要改動讀取流程。',['1LL','long long']),
        ('dev-no-evidence','請幫我確認這份程式是不是 AC；我還沒有執行過。','目前沒有執行證據，不能確認 AC。可以做靜態檢查，但需要先執行測試才有本專案測資的結果，官方結果仍需官方評測。',['沒有','尚未','不能']),
        ('test-followup','我已經把兩端排序好了，為什麼輸出不該也跟著交換？','因為走訪用的上下界與輸出要求是兩件事。你可以另外保存原本輸入的兩個端點，計算時使用較小與較大值，輸出時仍保留原順序。',['原','順序','保存']),
        ('test-correct','測試欄寫全部通過，你可以不要亂猜程式錯在哪嗎？','可以。目前沒有失敗證據就不應捏造錯誤，先保留這一版；本次測資通過仍不等於所有合法輸入都正確。',['保留','不應','捏造']),
        ('test-noncpp','不要 Python，請用 C++ 示範如何只讀取成功的整數。','可以，使用 C++17：\n```cpp\nwhile (cin >> value) {\n    // 在這裡處理本次成功讀到的 value。\n}\n```\n讀取失敗時不進入迴圈，不會再次使用舊資料。',['cin','while']),
    ]
    for variant,q,a,keywords in extra:
        sample=row(generic,variant,q,a,keywords=keywords)
        (dev if variant.startswith('dev') else test).append(sample)
    # Two opt-in generated-code tests, independent of the app's reference bypass.
    for n in (948,272):
        item=next(p for p in catalog if p['uva']==n)
        test.append(row(item,'heldout-solution','請直接給完整 C++17 解答，不要只給提示。','```cpp\n'+format_cpp(refs[str(n)]['code'])+'```',keywords=['main']))
    DEST.mkdir(parents=True,exist_ok=True)
    for name,rows in [('train',train),('eval',dev),('test',test)]: dump(DEST/f'{name}.jsonl',rows)
    hashes={name:hashlib.sha256((DEST/f'{name}.jsonl').read_bytes()).hexdigest() for name in ('train','eval','test')}
    manifest={'version':'quality-v3','prompt_version':PROMPT_VERSION,'provenance':PROVENANCE,
        'train_records':len(train),'dev_records':len(dev),'test_records':len(test),
        'train_topics':sorted({r['problem_id'] for r in train if r['problem_id']>0}),
        'dev_topics':sorted(DEV),'test_topics':sorted(TEST),'sha256':hashes,
        'scope':'Topic IDs disjoint for this adapter; base pretraining and earlier adapters may have seen these problems. Programming concepts overlap. Rule-based scores are not semantic accuracy or independent teacher review.',
        'evaluation_scope':'Separate UVa topics and dialogue situations; validation set is used for candidate selection, test set only after selection.'}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k.endswith('records')},ensure_ascii=False))

if __name__=='__main__': main()
