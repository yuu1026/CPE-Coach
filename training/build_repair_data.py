"""Failure-driven readable SFT data. All full targets audited in Docker.

Synthetic template variants are not independent student conversations. Dev/test
hold out names/program instances, not concepts or the already-seen Vito topic.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from coach.services import build_messages,PROMPT_VERSION
from coach.model_prompt import readable_messages
from coach.judging import judge

DEST=ROOT/'training/data/quality-v6'
PROVENANCE='GPT/Codex-authored synthetic correction curriculum; no external GPT API or independent teacher review'

def case(stdin,stdout):return {'name':'authored-check','input':stdin,'expected':stdout}

def fixtures(family,name):
    head='#include <iostream>\nusing namespace std;\n'
    if family in ('vito-mean','vito-scope'):
        original=f'int {name} = addressSum / relatives;'
        body='''#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>
using namespace std;
int main() {
    int cases; cin >> cases;
    while(cases--) {
        int relatives; cin >> relatives;
        vector<int> addresses(relatives);
        int addressSum=0;
        for(int &address:addresses) { cin >> address; addressSum+=address; }
        SELECT_HOME
        int distanceSum=0;
        for(int address:addresses) distanceSum+=abs(address-HOME);
        cout << distanceSum << '\\n';
    }
}
'''.replace('HOME',name)
        good=body.replace('SELECT_'+name,f'sort(addresses.begin(),addresses.end());\n        int {name}=addresses[relatives/2];')
        # HOME replacement also changes SELECT_HOME; use that resulting marker.
        bad=body.replace('SELECT_'+name,original)
        if family=='vito-scope':
            original=f'int {name}=addresses[relatives/2];'
            bad=body.replace('SELECT_'+name,f'sort(addresses.begin(),addresses.end());\n        if(relatives%2) {{ {original} }} else {{ {name}=addresses[relatives/2-1]; }}')
            explanation=f'`{original}` 把 {name} 限制在 if 區塊內，else 與後面的累加無法使用它。先排序，直接在分支外宣告 `{name}=addresses[relatives/2]`；偶數筆取上中位數也能最小化距離，不必另外分支。'
        else:
            explanation=f'`{original}` 計算平均數，不能保證絕對距離總和最小。先排序，再讓 {name} 取中位數；例如 1、2、100 選 2 的總和為 99，選 34 為 131。偶數筆取其中一個中間值即可。'
        tests=[case('4\n3 100 1 2\n2 2 4\n1 7\n4 5 5 5 5\n','99\n2\n0\n0\n'),case('2\n4 1 2 100 101\n5 20 1 1 1 2\n','198\n20\n')]
        return dict(problem_id=10041,statement='UVa 10041：先讀組數，每組讀親戚數及地址。輸出最小絕對距離總和，地址可重複。',bad=bad,good=good,tests=tests,explanation=explanation,keywords=['中位數','作用域','區塊'] if family=='vito-scope' else ['中位數'],original=original)
    if family=='scope':
        original=f'int {name}=left;'
        bad=head+f'int main() {{ int left,right; while(cin>>left>>right) {{ if(left>=right) {{ {original} }} else {{ {name}=right; }} cout<<{name}<<"\\n"; }} }}'
        good=head+f'int main() {{ int left,right; while(cin>>left>>right) {{ int {name}; if(left>=right) {{ {name}=left; }} else {{ {name}=right; }} cout<<{name}<<"\\n"; }} }}'
        return dict(problem_id=0,statement='讀取多組兩個 int，直到 EOF；每組輸出較大者。',bad=bad,good=good,tests=[case('5 2\n-2 -5\n9 9\n0 1\n','5\n-2\n9\n1\n')],explanation=f'`{original}` 的作用域只有 if 的大括號，else 與 cout 都不能使用 {name}。在 if 前先宣告 `int {name};`，兩個分支只做賦值；保留原本的比較方式。',keywords=['作用域','區塊','宣告'],original=original)
    if family=='division':
        original=f'double {name}=(a+b+c)/3;'
        bad='#include <iomanip>\n'+head+f'int main() {{ int a,b,c; while(cin>>a>>b>>c) {{ {original} cout<<fixed<<setprecision(6)<<{name}<<"\\n"; }} }}'
        replacement=f'double {name}=(static_cast<double>(a)+b+c)/3;'
        good=bad.replace(original,replacement)
        return dict(problem_id=0,statement='多組三個 int 直到 EOF，每組輸出算術平均，固定六位小數。可能有負數及 int 最大值。',bad=bad,good=good,tests=[case('1 2 2\n-1 -2 -2\n2147483647 2147483647 2147483647\n','1.666667\n-1.666667\n2147483647.000000\n')],explanation=f'`{original}` 的運算元都是 int，先做整數加法與除法，之後存入 double 也無法恢復小數。整數除法向零截斷，不是四捨五入，負數也不是向下取整。把第一個加數先轉為 double，既讓加法與除法以浮點進行，也避免先以 int 相加溢位：`{replacement}`。',keywords=['向零','截斷','整數除法','轉'],original=original)
    if family=='multiply':
        original=f'long long {name}=static_cast<long long>(left*right);'
        bad=head+f'int main() {{ int left,right; while(cin>>left>>right) {{ {original} cout<<{name}<<"\\n"; }} }}'
        replacement=f'long long {name}=static_cast<long long>(left)*right;'
        good=bad.replace(original,replacement)
        return dict(problem_id=0,statement='多組兩個 32-bit int 直到 EOF，以 long long 輸出乘積。',bad=bad,good=good,tests=[case('50000 50000\n-50000 50000\n2147483647 2147483647\n-2147483648 -2147483648\n','2500000000\n-2500000000\n4611686014132420609\n4611686018427387904\n')],explanation=f'`{original}` 在轉型前就以 int 計算乘法，可能先溢位。50000×50000 是 2500000000，超過 32-bit int，仍在 long long 範圍內；問題不是 long long 不夠大。應先提升一個運算元，再乘：`{replacement}`。',keywords=['運算元','轉型','int','2500000000'],original=original)
    raise ValueError(family)

def make_row(identifier,family,name,mode,audits):
    f=fixtures(family,name)
    problem=SimpleNamespace(title='UVa 10041 · Vito\'s family' if f['problem_id'] else 'C++17 修正練習',statement=f['statement'])
    code=f['good'] if mode=='accepted' else f['bad']
    evidence=audits['good'] if mode=='accepted' else audits['bad']
    if mode=='full':question='直接給我修正過的完整程式，保留我的變數與寫法，並說明必要差異。';target=f['explanation']+'\n\n```cpp\n'+f['good']+'```\n這是修正建議；不能把教師程式的驗證當作你的編輯器版本已經執行。'
    elif mode=='accepted':
        anchor={'vito-mean':'addresses[relatives/2]','vito-scope':'addresses[relatives/2]','scope':'if(left>=right)','division':'static_cast<double>(a)','multiply':'static_cast<long long>(left)'}[family]
        question='本次測資都通過，我現在一定要修改嗎？'
        target=f'目前使用 `{anchor}` 的這個版本已通過本次提供的測資。沒有新的失敗證據，不必為了修改而修改；這不代表所有合法輸入或官方評測都一定通過。'
    else:question='請引用我目前的程式，定位問題並說明最小修正，不要另換完整解法。';target=f['explanation']
    history=[]
    if mode=='followup':
        history=[{'question':'請幫我定位錯誤。','hint':f['explanation'],'code':f['bad']}]
        question='我知道要保留原寫法，但不懂這個原因，請針對剛才那一段換個具體說明，不要再從輸入格式問起。'
        extras={'scope':'大括號像一個房間，裡面新宣告的名字離開房間就不能用；把需要共用的宣告移到外層，分支只填入值。','vito-scope':'中位數可以直接在分支外選取；例如偶數地址 1、2、100、101，選 2 或 100 的距離總和都為 198，不必另寫造成作用域問題的分支。','vito-mean':'以 1、2、100 為例，選 2 得到 1+0+98=99；原本平均數的整數結果 34 則得到 33+32+66=131。','division':'例如 -5/3 的 int 結果是 -1，因為向零截斷；-5.0/3 才保留小數。這不是四捨五入。','multiply':'把乘完的結果才轉型，就像先用小盒子計算後才換大盒子，已發生的溢位無法補救。先把 left 轉成 long long，整個乘法才以 long long 計算。'}
        target=f'針對 `{f["original"]}`：'+extras[family]
    structured=build_messages(problem,code,question,3,history,evidence,include_reference=False,include_diagnostics=False,include_topic_notes=False)
    return dict(id=identifier,problem_id=f['problem_id'],variant=family+'-'+mode,hint_level=3,question=question,code=code,
        prompt_transport='readable',provenance=PROVENANCE,messages=readable_messages(structured)+[{'role':'assistant','content':target}],
        rubric={'concept_any':[] if mode=='accepted' else f['keywords'],'evidence_status':evidence['status'],'full_solution':mode=='full'},
        tests=f['tests'],gold_code=f['good'],audit_sha256=audits['sha256'])

def main():
    if DEST.exists():raise RuntimeError('Dataset exists; choose a new version rather than overwrite.')
    DEST.mkdir(parents=True)
    audit_rows=[];cache={}
    def audited(family,name):
        f=fixtures(family,name)
        digest=hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()
        if digest not in cache:
            good=judge(f['good'],f['tests']);bad=judge(f['bad'],f['tests'])
            if good['status']!='accepted' or bad['status'] not in ('compile_error','failed'):
                raise RuntimeError(f'Audit failed: {family}/{name}: good={good["status"]},bad={bad["status"]}')
            cache[digest]={'sha256':digest,'good':good,'bad':bad}
            audit_rows.append(dict(family=family,name=name,**cache[digest]))
            print('AUDIT',family,name,good['status'],bad['status'],flush=True)
        return cache[digest]
    sets={'train':[],'eval':[],'test':[]}
    for family in ['vito-mean','vito-scope','scope','division','multiply']:
        for name in ['home','location','chosen','result']:
            audit=audited(family,name)
            for mode in ['tutor','followup','full','accepted']:
                sets['train'].append(make_row(f'v6-{family}-{name}-{mode}',family,name,mode,audit))
    for split,spec in [('eval',[('vito-scope','meetingPoint','full'),('division','meanValue','full'),('multiply','wideProduct','full'),('scope','maximumValue','tutor')]),
                       ('test',[('vito-mean','residence','full'),('scope','largerValue','full'),('division','floatingMean','followup'),('multiply','safeProduct','accepted')])]:
        for family,name,mode in spec:
            sets[split].append(make_row(f'v6-{split}-{family}-{mode}',family,name,mode,audited(family,name)))
    # Keep a small fixed retention sample of prior topic-grounded teaching.
    old=[json.loads(s) for s in (ROOT/'training/data/quality-v4/train.jsonl').read_text(encoding='utf-8').splitlines()]
    selected=[r for r in old if r['problem_id']>0 and not r['rubric']['full_solution']][:16]
    for r in selected:
        payload=json.loads(r['messages'][-2]['content'])
        row=dict(r,id='v6-retention-'+r['id'],question=payload['question'],code=payload['code'],prompt_transport='readable')
        row['messages']=readable_messages(r['messages'][:-1])+[r['messages'][-1]]
        sets['train'].append(row)
    hashes={}
    for split,rows in sets.items():
        path=DEST/f'{split}.jsonl'
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
        hashes[split]=hashlib.sha256(path.read_bytes()).hexdigest()
    (DEST/'program_audits.json').write_text(json.dumps(audit_rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    manifest=dict(version='quality-v6',prompt_version=PROMPT_VERSION,counts={k:len(v) for k,v in sets.items()},sha256=hashes,
        provenance=PROVENANCE,unique_audited_program_pairs=len(cache),
        evaluation_scope='Failure-driven repair curriculum. Concepts and Vito topic seen in training. Dev/test hold out named program instances, not independent students or unseen topics. Small benchmark; no external teacher review.',
        notes=['All full targets passed authored Docker tests; buggy variants fail or do not compile.','Full-repair target code is not injected into prompts; accepted-program inputs intentionally already contain correct code.','Readable transport matches current runtime; no reference or diagnostic retrieval.','Original quality-v4 final test remains untouched.'])
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(manifest,ensure_ascii=True),flush=True)

if __name__=='__main__':main()
