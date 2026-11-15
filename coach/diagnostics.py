"""Narrow, audited fixture diagnoses. Unknown programs always fall back to the model.

This is retrieval of authored hints, not a model accuracy claim or host execution.
"""
import hashlib
import json
import re
from functools import lru_cache
from django.conf import settings

TOKENS=re.compile(r'^[ \t]*\#[^\r\n]*(?:\r?\n|$)|//[^\n]*(?:\n|$)|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?|\.\d+)(?:[eEpP][+-]?\d+)?[uUlLfF]*|>>=|<<=|->\*|\.\.\.|::|->|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|[^\s]',re.S|re.M)

def code_tokens(code):
    if 'R"' in code or re.search(r'\\\r?\n',code): return None
    tokens=[]
    for match in TOKENS.finditer(code):
        token=match[0]
        if token.startswith(('//','/*')):continue
        # Preprocessor whitespace can change string literals and function-like
        # macro definitions. Preserve it rather than guessing equivalence.
        tokens.append('#pp:'+token.strip() if token.lstrip().startswith('#') else token)
    return tokens

def code_signature(code):
    tokens=code_tokens(code)
    return hashlib.sha256(json.dumps(tokens,ensure_ascii=False).encode()).hexdigest() if tokens is not None else None

@lru_cache(maxsize=1)
def profiles():
    path=settings.BASE_DIR/'data/cpe-diagnostic-profiles.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def lookup(problem,code):
    match=re.match(r'UVa\s+(\d+)\b',getattr(problem,'title',''),re.I)
    item=profiles().get(code_signature(code)) if match and code.strip() else None
    if item and item['problem_id']==int(match[1]) and item['statement_sha256']==hashlib.sha256(problem.statement.encode()).hexdigest():
        return item
    return None

def direct_hint(payload,messages,level):
    profile=payload.get('verified_diagnostic')
    if not profile or payload.get('response_mode')=='solution': return None
    if payload.get('execution_evidence',{}).get('status')=='accepted': return None
    question=payload.get('question','')
    if not re.search(r'(?:幫我|協助|請|如何|怎麼).{0,10}(?:檢查|定位|找錯|修正)|哪.{0,3}(?:錯|出問題)|(?:指出|找出).{0,6}(?:條件|錯誤)|(?:輸出|答案).{0,4}(?:不符|錯)|程式.{0,4}(?:錯|不對)|^提示[？?！!。]*$',question): return None
    # At most one retrieved diagnosis in a branch. Later questions need a direct,
    # contextual model explanation with the verified diagnosis available as evidence.
    if any(m['role']=='assistant' and m['content'].startswith('題庫診斷提示') and any(h in m['content'] for h in profile['hints']) for m in messages[:-1]): return None
    hint=profile['hints'][max(0,min(2,level-1))]
    return ('題庫診斷提示（未呼叫模型）：目前程式與本專案已驗證的錯誤變體相符。\n\n'+hint+
        '\n\n這是既有自編測資與程式差異的比對，不表示這次已重新執行。修改後請再測試；若有其他疑問，可以繼續問具體步驟。')
