"""Verify guided steps; label model proposals, authored recovery and graded facts."""
import copy
import hashlib
import json
import random
import re
from . import performance
from .diagnostics import code_tokens, TOKENS
from .guided_learning import plan, new_name
from .lesson_catalog import CHECKS, SCAFFOLDS, FACTS, check_for
from .local_revision import apply_edits, parse_plan, check_candidate, digest
from .judging import judge
from .scaffold_policy import scaffold_issue


class LessonError(Exception): pass


def independent_tests(topic):
    rng=random.Random(451117)
    if topic==10055:
        pairs=[(0,0),(0,4294967296),(4294967296,0),(3,8),(8,3)] + [(rng.randrange(4294967297),rng.randrange(4294967297)) for _ in range(35)]
        return [{'name':'40 組額外差距案例','input':''.join(f'{a} {b}\n' for a,b in pairs),
                 'expected':''.join(f'{max(a,b)-min(a,b)}\n' for a,b in pairs)}],40
    arrays=[[1],[1,2,100],[9,1,4],[5,5,5,5],[29999,1]] + [[rng.randint(1,30) for _ in range(rng.randint(1,9))] for _ in range(19)]
    # Exhaustive home search, not a copy of the C++ median implementation.
    costs=[min(sum(abs(x-home) for x in xs) for home in range(min(xs),max(xs)+1)) for xs in arrays]
    return [{'name':'24 組額外選址案例','input':str(len(arrays))+'\n'+''.join(str(len(xs))+' '+' '.join(map(str,xs))+'\n' for xs in arrays),
             'expected':'\n'.join(map(str,costs))+'\n'}],24


def probe(step):
    kind=step['probe']
    if kind=='sort':body='std::vector<int> xs{9,1,4}; std::sort(xs.begin(),xs.end()); for(int x:xs)std::cout<<x<<" ";';expected='1 4 9'
    elif kind=='median':body='std::vector<int> xs{8,1,5};std::sort(xs.begin(),xs.end());int n=xs.size();std::cout<<xs[n/2];';expected='5'
    elif kind=='distance':body='std::vector<int> xs{1,2,100};int home=2,total=0;for(int x:xs)total+=std::abs(x-home);std::cout<<total;';expected='99'
    elif kind=='output':body='int total=7;std::cout<<total<<"\\n";total=0;std::cout<<total<<"\\n";';expected='7\n0\n'
    elif kind=='width':body='long long a=4294967296LL;std::cout<<a;';expected='4294967296'
    else:body='long long a=3,b=8;std::cout<<std::abs(a-b)<<"\\n"<<std::abs(b-a);';expected='5\n5'
    code='#include <iostream>\n#include <vector>\n#include <algorithm>\n#include <cstdlib>\nint main(){'+body+'}\n'
    return judge(code,[{'name':'教學概念小實驗','input':'','expected':expected}])


def state_reply(text,state,source,**extras):
    state=copy.deepcopy(state)
    state['source']=source
    return dict(text=text,state=state,source=source,**extras)


def check_text(check,state):return '\n\n理解確認：'+check_for(state,check)['prompt']


def lesson_messages(payload,step,approved):
    data={'code':payload['code'],'question':payload['question'],'problem_title':payload['problem_title'],
          'response_mode':'tutor','revision_request':True,'approved_lesson_step':{
              'step':step['step'],'reason':step['reason'],'edits':approved},
          'execution_evidence':payload.get('execution_evidence',{})}
    return [{'role':'system','content':'只完成已核對的一個步驟。'}, {'role':'user','content':json.dumps(data,ensure_ascii=False)}]


def deliver(action,payload,generate):
    state=copy.deepcopy(action['state']);topic=action['topic'];kind=action['kind'];code=payload['code']
    if kind=='exit':return state_reply('已暫停逐步核對，程式與聊天紀錄保留。接下來可以一般問答；要重新接續核對教學時，可說「恢復引導」。尚未完成的理解檢查不會算通過。',state,'lesson_system')
    if kind=='graded':
        check=action['checked']
        if not action['correct']:
            return state_reply('這個作答還不正確。'+check['explanation']+check_text(state['pending'],state),state,'lesson_system')
        # Answering a concrete check advances in this same reply, no extra button.
        next_action=plan(dict(payload,question='下一步',response_mode='tutor'),[{'lesson_record':state}])
        if not next_action:raise LessonError('本題教學狀態無法接續，原程式已保留。')
        result=deliver(next_action,payload,generate)
        result['text']='這個小例題答對了。'+check['explanation']+'\n\n'+result['text']
        return result
    if kind=='check':return state_reply('我們先算這個小例子，確認後再接下一步。'+check_text(action['check'],state),state,'lesson_system')
    if kind=='fact':return state_reply('系統核對教學：\n\n'+FACTS[action['fact']]+(check_text(state['pending'],state) if state.get('pending') else ''),state,'lesson_system')
    if kind=='await_code':return state_reply('輸入骨架已提供，但本輪編輯器仍是空白。請先把骨架放入編輯器，再說「下一步」；也可以直接詢問骨架中不懂的那一行。',state,'lesson_system')
    if kind=='start':
        text=('本題要選一個住址，讓到所有親戚地址的距離總和最小。例：地址 1、2、3，住在 2 的總距離為 1+0+1=2。' if topic==10041 else
              '本題反覆讀兩軍人數到 EOF，輸出非負差距。例：8 和 3 的差距是 5；交換順序仍是 5。')
        return state_reply('系統核對教學：\n\n'+text+check_text(action['check'],state),state,'lesson_system')
    if kind=='scaffold':
        state.pop('completion',None)
        candidate=SCAFFOLDS[topic]
        issue=scaffold_issue(candidate)
        if issue:raise LessonError('輸入骨架的內容檢查未通過，未交付程式。')
        with performance.span('validation'):result=judge(candidate,[])
        if result['status']!='accepted':raise LessonError('輸入骨架尚未完成編譯驗證，請確認 Docker 已啟動。原程式已保留。')
        state['pending']=None
        state['scaffold_sha256']=digest(candidate)
        return state_reply('系統核對教學：以下是本題的輸入骨架，已通過 C++17 編譯，核心留白，尚未執行題目測資。\n\n```cpp\n'+candidate+'```\n\n可將它放入編輯器，再說「下一步」。已有程式時不會自動覆寫。',state,'lesson_system',scaffold_code=candidate)
    if kind=='unsupported':
        return state_reply('目前這份程式的結構超出本題已核對的局部教學範圍，我先保留原碼，不猜測替換位置。請先執行測試，並指出希望一起檢查的那個運算式；你也可以說「退出引導」，繼續一般問答。這不表示你的寫法錯誤。',state,'lesson_system')
    if kind=='validate':
        state.pop('completion',None)
        tests=payload.get('generated_program_tests',[])
        extra,count=independent_tests(topic)
        test_hash=digest(json.dumps(tests+extra,ensure_ascii=False,sort_keys=True))
        prior=state.get('validation',{})
        if prior.get('code_sha256')!=digest(code) or prior.get('tests_sha256')!=test_hash or prior.get('status')!='accepted':
            with performance.span('validation'):result=judge(code,tests+extra)
            if result['status'] not in ('accepted','failed'):
                return state_reply('這個版本尚未完成編譯與額外測資驗證，不能算完成。請先確認 Docker 與測試結果，原程式保留。',state,'lesson_system')
            state['validation']={'code_sha256':digest(code),'tests_sha256':test_hash,'status':result['status'],'independent_examples':count,'result':result}
            if result['status']!='accepted':
                failed=next((x for x in result['cases'] if x['status']!='accepted'),{})
                return state_reply('這個版本仍有反例，尚未完成。\n\n輸入（節錄）：\n```text\n'+failed.get('input','')[:180]+'\n```\n預期（節錄）：\n```text\n'+failed.get('expected','')[:180]+'\n```\n請依此例追蹤目前程式；已通過的少量測資不等於所有輸入正確。',state,'lesson_system')
        required=['vito_order','vito_median','vito_distance','vito_output','vito_transfer'] if topic==10041 else ['hashmat_abs','hashmat_transfer']
        pending=next((key for key in required if CHECKS[key]['concept'] not in state['passed']),None)
        state['pending']=pending
        if pending:return state_reply(f'系統核對教學：目前程式通過題庫測資與額外 {count} 組輸入（額外輸入合併為一個 judge 案例）。這不是官方 AC。接著確認你能自行運用觀念。'+check_text(pending,state),state,'lesson_system')
        state['completion']='tests_and_checks_complete'
        state['independent_rebuild']='not_assessed'
        return state_reply(f'這條教學路徑已完成：目前程式通過題庫測資與額外 {count} 組輸入，也完成 {len(state["passed"])} 個具體觀念作答。\n\n這不代表已證明你能獨立重寫或通過官方評測。下一個練習是先保存目前程式，再不看原碼自行重寫；完成後重新測試。完成標記仍由你自行決定。',state,'lesson_system')
    if kind!='edit':raise LessonError('未知教學步驟。')
    step=action['step'];tests=payload.get('generated_program_tests',[])
    if not tests:raise LessonError('缺少本題驗證測資，未交付修改。')
    edits=[]
    for edit in step['edits']:
        if not edit:raise LessonError('找不到唯一修改位置，原程式保留。')
        if 'header' in edit and re.search(r'^\s*#\s*include\s*<'+re.escape(edit['header'])+r'>',code,re.M):continue
        edits.append(edit)
    expected=apply_edits(code,edits)
    source='lesson_model';audit={}
    try:
        reply=generate(lesson_messages(payload,step,edits),None)
        audit['raw_candidate']=str(reply)
        if getattr(reply,'truncated',False):raise ValueError('模型計畫被截斷。')
        proposed=parse_plan(reply)
        candidate=apply_edits(code,proposed['edits'])
        if code_tokens(candidate)!=code_tokens(expected):raise ValueError('模型候選超出本輪已核對修改。')
        comments=lambda text:[m[0] for m in TOKENS.finditer(text) if m[0].startswith(('//','/*'))]
        if comments(candidate)!=comments(expected):raise ValueError('模型候選加入或改寫了未核對的程式註解。')
    except Exception as exc:
        # One bounded attempt. Recovery is disclosed and still fully verified.
        audit['recovery_reason']=str(exc)[:800]
        candidate=expected;source='lesson_fallback'
    verified=payload.get('verified_baseline')
    baseline_key=digest(json.dumps({'code':code,'tests':tests,'policy':'cpp17-docker-v2'},ensure_ascii=False,sort_keys=True))
    if verified and verified.get('fingerprint')==baseline_key:baseline=verified
    else:
        with performance.span('baseline'):baseline=judge(code,tests)
    with performance.span('candidate'):result=judge(candidate,tests)
    if baseline.get('status') not in ('accepted','failed') or check_candidate(baseline,result,tests,True):
        raise LessonError('這一步未通過編譯或防退步檢查，沒有交付修改。原程式保留。')
    with performance.span('validation'):concept_probe=probe(step)
    if concept_probe.get('status')!='accepted':raise LessonError('本輪概念小實驗未通過，沒有交付修改。')
    old=sum(c['status']=='accepted' for c in baseline['cases']);new=sum(c['status']=='accepted' for c in result['cases'])
    check={'base_code':code,'candidate_code':candidate,'base_sha256':digest(code),'candidate_sha256':digest(candidate),
           'baseline':baseline,'candidate':result,'verification_scope':'lesson_step','lesson_step':step['step'],
           'concept_probe':concept_probe,'tests_sha256':digest(json.dumps(tests,sort_keys=True,ensure_ascii=False))}
    state['pending']=step['check'];state['last_step']=step['step'];state['proposal_audit']=audit
    prefix='模型提出局部修改；步驟與原因由系統教學卡核對。' if source=='lesson_model' else '模型這輪未交付符合本步驟的修改，改用系統核對教學；以下不是模型獨立產生的解法。'
    text=prefix+'\n\n'+step['reason']
    for edit in edits:
        if 'header' in edit:text+='\n\n在函式外加入：\n```cpp\n#include <'+edit['header']+'>\n```'
        else:
            from .local_revision import resolve_edit
            before,after,*_=resolve_edit(code,edit)
            text+='\n\n原片段：\n```cpp\n'+before+'\n```\n本步替換為：\n```cpp\n'+after+'\n```'
    text+=f'\n\n暫存副本已編譯，測資 {old}/{len(tests)} → {new}/{len(tests)}，原先通過案例沒有退步；概念小實驗也通過。'
    if new<=old:text+='本步只建立已核對的前置步驟，整題尚未完成。'
    text+='編輯器尚未覆寫，可使用「套用已驗證修改」，再自行測試。'+check_text(state['pending'],state)
    return state_reply(text,state,source,revision_check=check)
