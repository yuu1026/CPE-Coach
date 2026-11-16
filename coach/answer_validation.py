"""Check generated full programs in Docker; never automatically run editor code."""
import re
from .judging import judge
from .scaffold_policy import scaffold_issue
from . import performance


def cpp_blocks(answer):
    blocks=[];fence=None;body=[];language=''
    for line in answer.splitlines(keepends=True):
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',line.rstrip('\r\n'))
        if fence is None and marker:
            fence=marker[1];language=marker[2].strip().lower();body=[]
        elif fence and marker and marker[1][0]==fence[0] and len(marker[1])>=len(fence) and not marker[2].strip():
            code=''.join(body)
            if language in {'','cpp','c++','cxx','cc','cpp17','c++17'}:blocks.append(code)
            fence=None
        elif fence:body.append(line)
    return blocks


def compile_full_reply(answer,payload):
    mode=payload.get('response_mode')
    if mode not in ('solution','scaffold'):return None
    blocks=cpp_blocks(answer)
    programs=blocks if mode=='scaffold' else [code for code in blocks if re.search(r'\bmain\s*\(',code)]
    if not programs:return {'status':'missing_program','compiler':'本輪需要一份封閉的C++程式區塊。'}
    if len(programs)>1:
        return {'status':'multiple_programs','compiler':'請只提供一份完整修正版，避免多個版本混淆。'}
    if mode=='scaffold':
        issue=scaffold_issue(programs[0])
        if issue:return {'status':'missing_program','compiler':issue,'candidate':programs[0]}
    tests=[] if mode=='scaffold' else payload.get('generated_program_tests',[])
    candidate=programs[0]
    if mode=='scaffold' and not re.search(r'\bmain\s*\(',candidate):candidate+='\nint main(){return 0;}\n'
    # Without a real problem test suite, compile/link only; no invented inputs.
    with performance.span('validation'):
        result=judge(candidate,tests)
    if result['status']=='accepted':return {'status':'tested','passed':len(tests)} if tests else {'status':'compiled'}
    if result['status']=='compile_error':
        return {'status':'compile_error','compiler':result.get('compiler','')[:800],'candidate':programs[0]}
    if result['status']=='failed':
        failed=next((c for c in result.get('cases',[]) if c['status']!='accepted'),None)
        message='模型候選程式未通過題庫測資。'
        if failed:
            message+='\n狀態：'+failed['status']+'\n輸入：\n'+failed['input'][:200]+'\n預期：\n'+failed['expected'][:200]+'\n實際：\n'+failed['actual'][:200]
        return {'status':'test_failure','compiler':message,'candidate':programs[0]}
    return {'status':'unavailable','reason':result.get('label','編譯檢查未完成')}
