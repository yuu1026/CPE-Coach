"""Show only a verified single-step addition when an LLM repeats a draft.

Never transform a changed algorithm: old tokens must be preserved, and every
inserted token must match the already selected curriculum snippet/header.
"""
import re
from difflib import SequenceMatcher
from .diagnostics import code_tokens

PROGRAM=re.compile(r'^ {0,3}(`{3,}|~{3,})(?:cpp|c\+\+|cxx|cc|cpp17|c\+\+17)\s*\n(.*?)^ {0,3}\1\s*$',re.M|re.S|re.I)

def project_next_step(answer,payload):
    step=payload.get('verified_next_step')
    if payload.get('learning_mode')!='next_step' or not step or not step.get('snippet'):return answer,False
    blocks=list(PROGRAM.finditer(answer))
    if len(blocks)!=1 or not re.search(r'\bmain\s*\(',blocks[0][2]):return answer,False
    match=blocks[0];old=code_tokens(payload.get('code',''));new=code_tokens(match[2]);expected=code_tokens(step['snippet'])
    if old is None or new is None or expected is None:return answer,False
    added=[]
    for tag,_,__,left,right in SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
        if tag not in ('equal','insert'):return answer,False
        if tag=='insert':added.extend(new[left:right])
    headers=[t for t in added if t.startswith('#pp:')]
    if len(headers)>1:return answer,False
    if headers:
        header=step.get('header','')
        if not header or not re.fullmatch(r'#pp:\s*#\s*include\s*'+re.escape(header)+r'\s*',headers[0]):return answer,False
    body=[t for t in added if not t.startswith('#pp:')]
    def unqualify(tokens):
        result=[];i=0
        while i<len(tokens):
            if tokens[i:i+2]==['std','::']:i+=2
            else:result.append(tokens[i]);i+=1
        return result
    exact=body==expected
    if not exact and ['using','namespace','std',';'] in [old[i:i+4] for i in range(len(old))]:
        exact=unqualify(body)==unqualify(expected)
    if not exact:return answer,False
    replacement='這次只新增以下片段，省略原本已寫好的程式。\n\n'
    if headers:replacement+='檔案開頭新增標頭：\n```cpp\n#include '+step['header']+'\n```\n\n'
    replacement+='放置位置：'+step['placement']+'。\n```cpp\n'+step['snippet']+'\n```'
    return answer[:match.start()]+replacement+answer[match.end():],True
