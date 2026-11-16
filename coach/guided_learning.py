"""Bounded lesson planning from current code + explicitly graded student answers.

Not an AST or general C++ repair engine. Unknown structures are never rewritten.
"""
import copy
import hashlib
import re
from .diagnostics import TOKENS, code_tokens
from .lesson_catalog import CHECKS, VERSION, signature, topic_for, check_for


def masked(code):
    text=list(code)
    for match in TOKENS.finditer(code):
        if match[0].startswith(('//','/*','"',"'",'#')):
            text[match.start():match.end()]=' '*len(match[0])
    return ''.join(text)


def end_block(text, start):
    if text[start:start+1]!='{': return None
    depth=0
    for index in range(start,len(text)):
        if text[index]=='{':depth+=1
        elif text[index]=='}':
            depth-=1
            if depth==0:return index+1
    return None


def append(code, start, end, snippet, inside=False):
    before=code[start:end]
    if not before or code.count(before)!=1:return None
    line=code[code.rfind('\n',0,start)+1:start]
    indent=line if not line.strip() else ''
    base=indent
    if inside:indent+='    '
    addition=indent+snippet.replace('\n','\n'+indent)
    after=(before.rstrip() if inside else before)+'\n'+addition+('\n'+base if inside else '')
    return {'before':before,'after':after}


def new_name(text, name):
    candidate=name
    while re.search(r'\b'+re.escape(candidate)+r'\b',text):candidate+='Next'
    return candidate


def vito_step(code):
    if code_tokens(code) is None:return None
    text=masked(code)
    vectors=list(re.finditer(r'\b(?:std\s*::\s*)?vector\s*<\s*int\s*>\s+(\w+)\s*\(\s*(\w+)\s*\)\s*;',text))
    if len(vectors)!=1:return None
    vector=vectors[0];values,count=vector[1],vector[2]
    v,n=map(re.escape,(values,count))
    loops=list(re.finditer(r'\bfor\s*\(\s*int\s+(\w+)\s*=\s*0\s*;\s*\1\s*<\s*'+n+r'\s*;\s*(?:\+\+\s*\1|\1\s*\+\+)\s*\)\s*',text))
    inputs=[]
    for loop in loops:
        index=loop[1];i=re.escape(index)
        end=end_block(text,loop.end()) if text[loop.end():loop.end()+1]=='{' else text.find(';',loop.end())+1
        if not end:continue
        body=text[loop.end():end].strip().strip('{}').strip()
        pattern=r'(?:std\s*::\s*)?cin\s*>>\s*'+v+r'\s*\[\s*'+i+r'\s*\]\s*;\s*(?:\w+\s*\+=\s*'+v+r'\s*\[\s*'+i+r'\s*\]\s*;\s*)?'
        if re.fullmatch(pattern,body):inputs.append((loop,end))
    if len(inputs)!=1:return None
    loop,input_end=inputs[0]
    if vector.start()>loop.start():return None
    cases=[]
    for case in re.finditer(r'\bwhile\s*\(\s*(\w+)\s*--\s*\)\s*\{',text):
        end=end_block(text,case.end()-1)
        if end and case.end()<=vector.start()<input_end<end:cases.append((case,end))
    if len(cases)!=1:return None
    case,case_end=cases[0]
    after=text[input_end:case_end-1]
    sort=re.match(r'\s*((?:std\s*::\s*)?sort\s*\(\s*'+v+r'\s*\.\s*begin\s*\(\s*\)\s*,\s*'+v+r'\s*\.\s*end\s*\(\s*\)\s*\)\s*;)',after)
    if not sort:
        # Refuse to add a second sort elsewhere or guess unusual control flow.
        if re.search(r'\bsort\s*\(',after):return None
        edit=append(code,loop.start(),input_end,f'std::sort({values}.begin(), {values}.end());')
        return dict(step='sort',edits=[{'header':'algorithm'},edit],reason=f'這一步將已讀完的 `{values}` 由小到大排序。中位數是排序後的中間地址，後續再核對選址與距離加總。',
                    check='vito_order',probe='sort',values=values,count=count) if edit else None
    sort_start=input_end+sort.start(1);sort_end=input_end+sort.end(1)
    median=re.search(r'\b(?:int|auto|long\s+long)\s+(\w+)\s*=\s*'+v+r'\s*\[\s*'+n+r'\s*/\s*2\s*\]\s*;',text[sort_end:case_end-1])
    if not median:
        mean=list(re.finditer(r'\b(?:int|double|long\s+long)\s+(\w+)\s*=\s*(\w+\s*/\s*'+n+r')\s*;',text[sort_end:case_end-1]))
        if len(mean)>1:return None
        if mean:
            item=mean[0];start=sort_end+item.start(2);end=sort_end+item.end(2)
            before=code[start:end]
            if code.count(before)!=1:return None
            edits=[{'before':before,'after':f'{values}[{count} / 2]'}]
        else:
            if re.search(r'\b(?:cout|printf|total|distanceSum)\b',text[sort_end:case_end-1]):return None
            home=new_name(text,'home')
            edit=append(code,sort_start,sort_end,f'int {home} = {values}[{count} / 2];')
            if not edit:return None
            edits=[edit]
        return dict(step='median',edits=edits,reason=f'`{values}` 已排序。選中間的地址能使一維絕對距離總和最小；整數平均即使計算正確，也未必選到最佳位置。',check='vito_median',probe='median',values=values,count=count)
    home=median[1];home_start=sort_end+median.start();home_end=sort_end+median.end()
    h=re.escape(home)
    distance=re.search(r'\b(\w+)\s*\+=\s*(?:std\s*::\s*)?(?:abs|llabs)\s*\(\s*(?:'+v+r'\s*\[\s*\w+\s*\]|\w+)\s*-\s*'+h+r'\s*\)\s*;',text[home_end:case_end-1])
    if not distance:
        if re.search(r'\b(?:cout|printf)\b|\+=',text[home_end:case_end-1]):return None
        total=new_name(text,'distanceSum');address=new_name(text,'address')
        snippet=f'int {total} = 0;\nfor (int {address} : {values}) {{\n    {total} += std::abs({address} - {home});\n}}'
        edit=append(code,home_start,home_end,snippet)
        return dict(step='distance',edits=[{'header':'cstdlib'},edit],reason=f'每組重新將 `{total}` 設為零，分別計算各地址到 `{home}` 的絕對距離再相加，避免正負互抵。',check='vito_distance',probe='distance',values=values,count=count) if edit else None
    total=distance[1]
    if not re.search(r'\b(?:int|long\s+long)\s+'+re.escape(total)+r'\s*=\s*0\s*;',text[home_end:home_end+distance.start()]):return None
    if re.search(r'\b(?:std\s*::\s*)?cout\s*<<\s*'+re.escape(total)+r'\b',text[home_end+distance.end():case_end-1]):
        return {'step':'test'}
    # Output belongs after the accumulation loop, not inside its body.
    absolute_end=home_end+distance.end()
    enclosing=[]
    for outer in re.finditer(r'\bfor\s*\([^{}]*\)\s*\{',text[home_end:case_end-1]):
        start=home_end+outer.start();end=end_block(text,home_end+outer.end()-1)
        if end and start<absolute_end<end:enclosing.append((start,end))
    if len(enclosing)>1:return None
    start,end=enclosing[0] if enclosing else (home_end+distance.start(),absolute_end)
    edit=append(code,start,end,f'std::cout << {total} << "\\n";')
    return dict(step='output',edits=[edit],reason=f'這組地址的距離全部累加完成後，才輸出 `{total}`，每組一行。',check='vito_output',probe='output',values=values,count=count) if edit else None


def hashmat_step(code):
    if code_tokens(code) is None:return None
    text=masked(code)
    reads=list(re.finditer(r'\bwhile\s*\(\s*(?:std\s*::\s*)?cin\s*>>\s*(\w+)\s*>>\s*(\w+)\s*\)\s*\{',text))
    if len(reads)!=1:return None
    read=reads[0];a,b=read[1],read[2];end=end_block(text,read.end()-1)
    if not end:return None
    declaration=re.search(r'\b(long\s+long|int)\s+'+re.escape(a)+r'\s*,\s*'+re.escape(b)+r'\s*;',text[:read.start()])
    if not declaration:return None
    if declaration[1]=='int':
        original=code[declaration.start():declaration.end()]
        return dict(step='width',edits=[{'before':original,'after':f'long long {a}, {b};'}],reason='題目輸入可達 2^32，一般32位元 int 不足以保存；改用 long long。long long 可以表示負數，差距仍需另取絕對值。',check='hashmat_start',probe='width')
    body=text[read.end():end-1]
    if not body.strip():
        edit=append(code,read.start(),end-1, f'std::cout << std::abs({a} - {b}) << "\\n";',inside=True)
        return dict(step='difference',edits=[{'header':'cstdlib'},edit],reason=f'`{a} - {b}` 可能為負數；題目要非負差距，所以輸出絕對值。long long 可以保存負數，並非型別不能表示負數。',check='hashmat_abs',probe='difference') if edit else None
    # Only a direct output subtraction is covered; preserve every other token.
    from .code_units import units
    expressions=[u for u in units(code) if u['kind']=='expression' and read.end()<=u['start']<u['end']<end]
    for unit in expressions:
        tokens=code_tokens(unit['code'])
        if tokens==[a,'-',b]:
            return dict(step='difference',edits=[{'header':'cstdlib'},{'unit_id':unit['unit_id'],'after':f'std::abs({a} - {b})'}],reason=f'`{a} - {b}` 是帶正負號的差；題目要絕對差，交換兩個輸入時輸出應相同。long long 能表示負數。',check='hashmat_abs',probe='difference')
        if tokens in ([a,'>',b,'?',a,'-',b,':',b,'-',a],['abs','(',a,'-',b,')'],['std','::','abs','(',a,'-',b,')']):return {'step':'test'}
    return None


def answer_values(text):
    text=re.split(r'接下來|下一步|請',text,maxsplit=1)[0].strip()
    if re.search(r'為什麼|怎麼|如何|測試|測資|編譯|程式|是不是',text):return None
    if re.search(r'不確定|不知道|我懂了|了解了',text) and not re.search(r'\d',text):return None
    if re.fullmatch(r'[零一二三四五六七八九十][。！!\s]*',text):
        return ['零一二三四五六七八九十'.index(text.strip('。！! '))]
    # For arithmetic explanations grade only the asserted RHS, not operands.
    if '=' in text:text=text.rsplit('=',1)[1]
    if re.search(r'[A-Za-z]|[+*/]',text):return None
    values=re.findall(r'(?<![\d.])-?\d+(?![\d.])',text)
    if not values or len(values)>6:return None
    return list(map(int,values))


def plan(payload, history):
    topic=topic_for(payload.get('problem_title',''),payload.get('problem',''))
    if not topic or payload.get('response_mode')=='solution':return None
    previous=next((h.get('lesson_record') for h in reversed(history) if h.get('lesson_record')),None)
    resume=bool(re.search(r'恢復引導|重新開始|從頭開始|重置教學',payload['question']))
    if previous and previous.get('disabled') and not resume:return None
    active=previous and previous.get('signature')==signature(topic)
    explicit=re.search(r'引導|教我|陪我|一步|下一步|接下來|骨架|沒有.{0,5}想法|不知道.{0,5}開始|帶我|繼續學',payload['question'])
    if not active and not explicit and not resume:return None
    state=copy.deepcopy(previous) if active else {'version':VERSION,'topic':topic,'signature':signature(topic),'checks':[],'passed':[],'pending':None}
    question=payload['question'];code=payload['code']
    if resume:
        state={'version':VERSION,'topic':topic,'signature':signature(topic),'checks':[],'passed':[],'pending':None}
    if state.get('validation',{}).get('code_sha256')!=hashlib.sha256(code.encode()).hexdigest():
        state.pop('completion',None)
    if re.search(r'退出引導|停止引導|不要引導|跳過|先不要測驗|不要再問問題',question):
        state['disabled']=True;state['pending']=None
        return {'kind':'exit','state':state,'topic':topic}
    if payload.get('response_mode')=='scaffold':return {'kind':'scaffold','state':state,'topic':topic}
    if re.search(r'為什麼|不懂|是什麼|意思|解釋|說明|是否|對嗎|嗎[？?]?$',question) and not re.search(r'下一步|修改|修正|新增|加入',question):
        fact=None
        if topic==10055 and re.search(r'long\s*long|型別|負數.{0,5}表示',question,re.I):fact='width'
        elif re.search(r'abs|絕對值|相反數',question,re.I):fact='absolute'
        elif topic==10041 and re.search(r'中位數|平均',question):fact='median'
        elif topic==10041 and re.search(r'排序|sort',question,re.I):fact='sorting'
        if fact:return {'kind':'fact','fact':fact,'state':state,'topic':topic}
    pending=state.get('pending')
    if pending and pending in CHECKS:
        check=check_for(state,pending);values=answer_values(question)
        if values is not None:
            correct=values==check['expected']
            state['checks'].append({'id':pending,'variant':state.get('variants',{}).get(pending,0),'answer':question[:250],'correct':correct})
            state['checks']=state['checks'][-30:]
            if correct:
                if check['concept'] not in state['passed']:state['passed'].append(check['concept'])
                state['pending']=None
                return {'kind':'graded','correct':True,'check':pending,'checked':check,'state':state,'topic':topic}
            state['pending']=check.get('retry',pending)
            if state['pending']==pending:
                variants=state.setdefault('variants',{})
                variants[pending]=variants.get(pending,0)+1
            return {'kind':'graded','correct':False,'check':pending,'checked':check,'state':state,'topic':topic}
        if re.search(r'下一步|接下來|懂了|繼續|不懂|不知道|再試一次',question):
            return {'kind':'check','check':pending,'state':state,'topic':topic}
        elif not explicit:
            # Specific conceptual questions still use normal contextual Q&A.
            return None
    if not code.strip():
        if re.search(r'骨架|輸入|開始寫',question):return {'kind':'scaffold','state':state,'topic':topic}
        if state.get('scaffold_sha256'):return {'kind':'await_code','state':state,'topic':topic}
        first='vito_start' if topic==10041 else 'hashmat_start'
        if 'distance' in state['passed'] or 'absolute_difference' in state['passed']:
            return {'kind':'scaffold','state':state,'topic':topic}
        state['pending']=first
        return {'kind':'start','check':first,'state':state,'topic':topic}
    step=vito_step(code) if topic==10041 else hashmat_step(code)
    if step is None:return {'kind':'unsupported','state':state,'topic':topic}
    if step['step']=='test':
        transfer='vito_transfer' if topic==10041 else 'hashmat_transfer'
        return {'kind':'validate','check':transfer,'state':state,'topic':topic}
    return {'kind':'edit','step':step,'state':state,'topic':topic}
