"""Verify exact, bounded student-code edits in Docker before publishing them."""
import hashlib
import json
import re
from collections import Counter
from .judging import judge
from .diagnostics import code_tokens
from .code_units import units
from . import performance

STANDARD_HEADERS={'algorithm','cstdlib','vector','iostream','numeric','cmath','iomanip','limits','string','map','set','queue','stack','utility','array','functional','cstdint','climits','cstring','sstream','cstdio'}


class RevisionError(ValueError):
    pass


def digest(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def normalize_header(edit):
    header=edit.get('header')
    if not isinstance(header,str):raise RevisionError('header必須為標準標頭名稱。')
    header=header.strip()
    if header.startswith('<') and header.endswith('>'):header=header[1:-1].strip()
    if header not in STANDARD_HEADERS:raise RevisionError('header必須是允許的標準標頭名稱，不包含路徑。')
    if 'after' in edit:
        redundant=edit['after']
        # Accept an equivalent redundant include, including JSON over-escaped
        # boundary newlines. Never normalize arbitrary C++ or extra statements.
        if not isinstance(redundant,str) or not re.fullmatch(r'(?:\s|\\[nr])*#\s*include\s*<'+re.escape(header)+r'>(?:\s|\\[nr])*',redundant):
            raise RevisionError('header操作的after若存在，只能是相同標頭的include，不能含其他程式。')
    return header


def wrapped_operand(code,target,after):
    """Resolve a parent's unique unchanged operand inside a complete wrapper.

    Never invent the replacement expression, remove text from it, or choose
    between multiple matching operands. Compilation remains mandatory.
    """
    if target['kind']!='statement':return None
    proposed=code_tokens(after)
    if not proposed or any(t in proposed for t in (';','{','}','=','+=','-=','++','--','return','cout','cin')):return None
    if '(' not in proposed or proposed[-1]!=')':return None
    depth=0
    for index in range(proposed.index('('),len(proposed)):
        if proposed[index]=='(':depth+=1
        elif proposed[index]==')':depth-=1
        if depth==0 and index!=len(proposed)-1:return None
    if depth:return None
    matches=[]
    for child in units(code):
        if child['kind']!='expression' or not (target['start']<=child['start']<child['end']<=target['end']):continue
        original=code_tokens(child['code']) or []
        if original and any(proposed[i:i+len(original)]==original for i in range(len(proposed)-len(original)+1)):
            matches.append(child)
    if len(matches)>1:raise RevisionError('敘述內有多個相同運算式，請選擇確切expression片段，不猜位置。')
    return matches[0] if matches else None


def resolve_edit(code,edit):
    if not isinstance(edit,dict):raise RevisionError('修改必須為物件。')
    if 'header' in edit and set(edit)<={'header','after'}:
        header=normalize_header(edit)
        if re.search(r'^\s*#\s*include\s*<'+re.escape(header)+r'>',code,re.M):raise RevisionError('目前程式已有這個標頭，不重複新增。')
        index=1 if code.startswith('\ufeff') else 0
        if len(code)<=index:raise RevisionError('沒有可供修改的原碼。')
        # Anchor to a single original character so existing positional edit
        # validation and version checks still apply; never put it in a body.
        before=code[index:index+1]
        return before,'#include <'+header+'>\n'+before,index,index+1
    if set(edit)=={'unit_id','after'}:
        target=next((unit for unit in units(code) if unit['unit_id']==edit['unit_id']),None)
        if not target:raise RevisionError('片段標記不在目前原碼內，請使用本輪提供的U標記。')
        if not isinstance(edit['after'],str):raise RevisionError('after必須為字串。')
        projected=wrapped_operand(code,target,edit['after'])
        if projected:target=projected
        return target['code'],edit['after'],target['start'],target['end']
    if set(edit)=={'line_id','after'}:
        match=re.fullmatch(r'L([1-9]\d*)',str(edit['line_id']))
        lines=code.splitlines(keepends=True)
        if not match or int(match[1])>len(lines):raise RevisionError('行標記不在目前原碼內。')
        index=int(match[1])-1;before=lines[index];after=edit['after'];start=sum(map(len,lines[:index]))
        if not isinstance(after,str):raise RevisionError('after必須為字串。')
        # A line replacement cannot accidentally concatenate the next line.
        if before.endswith('\n') and after and not after.endswith('\n'):after+='\n'
        return before,after,start,start+len(before)
    if set(edit)=={'before','after'}:
        before,after=edit['before'],edit['after']
        if not isinstance(before,str) or not before or code.count(before)!=1:
            raise RevisionError('原片段必須逐字存在且只出現一次，不猜位置或行號。')
        start=code.index(before)
        return before,after,start,start+len(before)
    raise RevisionError('每個修改必須為header，或unit_id與after、line_id與after、before與after。')


def apply_edits(code, edits):
    if not isinstance(edits,list) or not 1<=len(edits)<=4:
        raise RevisionError('必須提出1至4個局部替換，不可沒有修改。')
    spans=[];changed=0
    for edit in edits:
        before,after,start,end=resolve_edit(code,edit)
        if not isinstance(before,str) or not isinstance(after,str) or not before or max(len(before),len(after))>4096:
            raise RevisionError('替換片段格式或長度不符。')
        if before==after or before.strip()==code.strip():
            raise RevisionError('不能以相同片段替換，也不能整份改寫。')
        if any(start<right and end>left for left,right,_ in spans):
            raise RevisionError('修改範圍不能重疊。')
        changed+=len(before.splitlines())+len(after.splitlines())
        spans.append((start,end,after))
    if changed>32:raise RevisionError('本輪修改過大，請只推進一個局部步驟。')
    result=code
    for start,end,after in sorted(spans,reverse=True):result=result[:start]+after+result[end:]
    if result==code or len(result)>12000:raise RevisionError('沒有有效變更或超過程式長度上限。')
    original_tokens=code_tokens(code);new_tokens=code_tokens(result)
    if original_tokens is not None and original_tokens==new_tokens:
        raise RevisionError('只改空白或註解，不是有效程式修正。')
    return result


def parse_plan(reply):
    raw=str(reply).strip()
    if raw.startswith('```json\n') and raw.endswith('```'):raw=raw[8:-3].strip()
    try:plan=json.loads(raw)
    except (ValueError,TypeError):raise RevisionError('請只回傳指定的JSON修改計畫。') from None
    if not isinstance(plan,dict) or set(plan)!={'explanation','edits'}:
        raise RevisionError('JSON只允許explanation與edits。')
    explanation=plan['explanation']
    if not isinstance(explanation,str) or not 4<=len(explanation)<=600 or '```' in explanation:
        raise RevisionError('理由需為簡短繁體中文，不夾帶另一份程式。')
    if len(re.findall(r'[\u3400-\u9fff]',explanation))<4:
        raise RevisionError('修改理由必須使用繁體中文。')
    if isinstance(plan['edits'],list):
        plan['edits']=[{'header':normalize_header(edit)} if isinstance(edit,dict) and 'header' in edit and set(edit)<={'header','after'} else edit for edit in plan['edits']]
    return plan


def check_candidate(baseline,candidate,tests,allow_partial):
    if candidate.get('status') not in ('accepted','failed') or len(candidate.get('cases',[]))!=len(tests):
        return '候選未完成編譯與測試。\n'+candidate.get('compiler',candidate.get('label',''))[:800]
    old=baseline.get('cases',[]);new=candidate['cases']
    lost=[tests[i]['name'] for i,c in enumerate(old) if c['status']=='accepted' and new[i]['status']!='accepted']
    if lost:return '修改造成退步：原先通過的案例失敗：'+ '、'.join(lost)
    old_pass=sum(c['status']=='accepted' for c in old)
    new_pass=sum(c['status']=='accepted' for c in new)
    if baseline.get('status') in ('accepted','failed') and new_pass<=old_pass and not allow_partial:
        return '修改沒有增加通過案例，尚無證據修正目前問題。'
    return None


def header_setup_only(before,after):
    """Recognize a dependency-only step, never an algorithmic repair verdict."""
    old,new=code_tokens(before),code_tokens(after)
    if old is None or new is None:return False
    is_include=lambda t:bool(re.match(r'^#pp:#\s*include\b',t))
    old_headers=Counter(t for t in old if is_include(t));new_headers=Counter(t for t in new if is_include(t))
    if old_headers-new_headers:return False
    added=list((new_headers-old_headers).elements())
    for header in added:
        match=re.fullmatch(r'#pp:#\s*include\s*<([^>]+)>',header)
        if not match or match[1] not in STANDARD_HEADERS:return False
    return bool(added) and [t for t in old if not is_include(t)]==[t for t in new if not is_include(t)]


def generate_revision(messages,level,generate,traditional):
    payload=json.loads(messages[-1]['content']);code=payload['code'];tests=payload['revision_tests']
    verified=payload.get('verified_baseline')
    fingerprint=digest(json.dumps({'code':code,'tests':tests,'policy':'cpp17-docker-v2'},ensure_ascii=False,sort_keys=True))
    if (verified and verified.get('fingerprint')==fingerprint and verified.get('status') in ('accepted','failed')
            and len(verified.get('cases',[]))==len(tests)):
        baseline=verified
        performance.phase('baseline',baseline_reused=True)
    else:
        with performance.span('baseline'):
            baseline=judge(code,tests)
    if baseline.get('status') not in ('accepted','failed','compile_error','compile_timeout'):
        raise RevisionError('修改驗證服務未就緒，沒有交付未驗證片段。原程式已保留。')
    if baseline.get('status') in ('accepted','failed') and len(baseline.get('cases',[]))!=len(tests):
        raise RevisionError('原程式測試結果不完整，停止修改驗證。')
    if baseline['status']=='accepted':
        return (f'系統測試確認（未呼叫模型）：你的目前程式通過本次 {len(tests)} 組測資，沒有根據這些測資確認到需要修正的錯誤，因此保留原程式。這不是官方AC或所有輸入正確的保證；若有其他失敗案例，請加入測資後再檢查。',None)
    feedback='';last_error='';attempts=[]
    payload=dict(payload,execution_evidence={'status':baseline['status'],'label':baseline['label'],
        'compiler_excerpt':baseline.get('compiler','')[:800],
        'failed_case_excerpts':[{'name':c['name'],'input_excerpt':c['input'][:300],
                               'expected_excerpt':c['expected'][:300],'actual_excerpt':c['actual'][:300]}
                              for c in baseline.get('cases',[]) if c['status']!='accepted'][:2]})
    for attempt in range(2):
        request=[dict(m) for m in messages]
        request[-1]['content']=json.dumps(dict(payload,revision_feedback=feedback),ensure_ascii=False)
        reply=generate(request,level)
        try:
            if getattr(reply,'truncated',False):raise RevisionError('修改計畫被截斷，請縮小片段。')
            plan=parse_plan(reply)
            candidate_code=apply_edits(code,plan['edits'])
            setup_only=header_setup_only(code,candidate_code)
            if payload.get('edit_scope')=='dependency_only' and not setup_only:
                raise RevisionError('使用者本輪只要求新增標頭，不能順便修改運算或加入排序。')
            with performance.span('candidate'):
                candidate=judge(candidate_code,tests)
            no_output=not any(token in (code_tokens(code) or []) for token in ('cout','wcout','printf','puts','putchar','fputs','fwrite'))
            provisional=payload.get('learning_mode')=='next_step' and (setup_only or no_output)
            issue=check_candidate(baseline,candidate,tests,provisional)
            if issue:raise RevisionError(issue)
            attempts.append({'plan':plan,'result':candidate})
            canonical=[dict(zip(('before','after'),resolve_edit(code,edit)[:2]))|({'header':edit['header']} if set(edit)=={'header'} else {}) for edit in plan['edits']]
            check={'base_code':code,'candidate_code':candidate_code,'base_sha256':digest(code),
                   'candidate_sha256':digest(candidate_code),'tests_sha256':digest(json.dumps(tests,sort_keys=True,ensure_ascii=False)),
                   'baseline':baseline,'candidate':candidate,'edits':canonical,'attempts':attempts}
            check['scope_projection']=any('unit_id' in edit and next(u for u in units(code) if u['unit_id']==edit['unit_id'])['code']!=item['before'] for edit,item in zip(plan['edits'],canonical))
            passed=sum(c['status']=='accepted' for c in candidate['cases'])
            old_pass=sum(c['status']=='accepted' for c in baseline.get('cases',[]))
            check['verification_scope']='dependency_only' if setup_only else 'compile_and_no_regression' if passed<=old_pass else 'improved_tests'
            text=traditional(plan['explanation'])+'\n\n'
            if check['scope_projection']:
                text+='系統定位協助：模型選了外層敘述，系統將其提供的完整包裝運算式對應到唯一原運算式；替換內容未改寫，並另行編譯與測試。\n\n'
            for number,edit in enumerate(canonical,1):
                if edit.get('header'):
                    text+=f'修改 {number}：在函式外新增標頭：\n```cpp\n#include <{edit["header"]}>\n```\n\n'
                    continue
                fence='`'*max(3,1+max((len(x) for x in re.findall(r'`+',edit['before']+edit['after'])),default=0))
                text+=f'修改 {number}：系統已定位以下原片段（套用按鈕使用完整版本核對）：\n'+fence+'cpp\n'+edit['before']+'\n'+fence+'\n替換為：\n'+fence+'cpp\n'+edit['after']+'\n'+fence+'\n\n'
            text+=f'系統已在暫存副本編譯與測試：{old_pass}/{len(tests)} → {passed}/{len(tests)}，原先通過的案例沒有退步。'
            if passed<=old_pass:
                text+='這輪只確認可編譯與沒有測資退步；'+('只新增了依賴標頭，尚未修正運算。' if setup_only else '程式仍未完成，尚無證據證明新增步驟的演算法正確。')
            text+='你的編輯器尚未修改；可套用後再自行測試。這不代表官方AC或文字解釋已被證明正確。'
            return text,check
        except RevisionError as exc:
            last_error=str(exc);feedback=last_error
            if attempt == 0: performance.retry('local_revision')
            if 'plan' in locals():feedback+='\n上次候選計畫（未通過，不可照抄）：'+json.dumps(plan,ensure_ascii=False)
            attempts.append({'reply':str(reply),'error':feedback})
    error=RevisionError('模型兩次局部修改仍未通過片段、編譯或退步檢查，未交付修改。原程式已保留。\n'+last_error)
    error.audit={'base_sha256':digest(code),'baseline':baseline,'attempts':attempts}
    raise error
