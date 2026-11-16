"""Conservative input/setup-only scaffold contract, not general C++ semantics."""
import re
from .diagnostics import TOKENS,code_tokens
from .code_units import units


def scaffold_issue(code):
    tokens=code_tokens(code)
    if tokens is None:return '骨架含有尚不支援的原始字串或巨集續行，無法確認核心留白。'
    comments=[m[0] for m in TOKENS.finditer(code) if m[0].startswith(('//','/*'))]
    if not any(re.search(r'TODO|待完成|待實作|自行.{0,5}(?:完成|補上)|在此.{0,5}(?:實作|填入)',c,re.I) for c in comments):
        return '骨架應以TODO註解留下真正的核心空缺，不可只在文字或字串中標記TODO。'
    if any(re.search(r'for\s*\(|(?:std::)?(?:sort|abs|accumulate)\s*\(|\b(?:int|long|double)\s+\w+\s*=',c) for c in comments):
        return '不要將可直接啟用的完整解法藏在註解中；骨架只保留簡短TODO說明。'
    if any(t in tokens for t in ('cout','printf','puts','sort','nth_element','abs','llabs','accumulate')):
        return '本輪骨架只搭輸入與流程，核心計算及輸出保留TODO；不要先完成排序、距離計算或印出答案。'
    for unit in units(code):
        if unit['kind']!='statement':continue
        ts=code_tokens(unit['code']) or []
        if 'cin' in ts or 'scanf' in ts:continue
        if any(t in ts for t in ('+=','-=','*=','/=','%=')):
            return '骨架仍含核心累加或更新運算，請以TODO註解取代。'
        if '=' in ts:
            rhs=ts[ts.index('=')+1:-1]
            if any(t in rhs for t in ('+','-','*','/','%','[','?')):
                return '骨架仍在計算或選取解題資料，請保留核心TODO。'
    # Avoid the common generated early-return-inside-case-loop bug.
    stack=[];prefix=[]
    for token in tokens:
        if token=='{':stack.append('for' in prefix or 'while' in prefix);prefix=[]
        elif token=='}':
            if stack:stack.pop()
            prefix=[]
        elif token=='return' and any(stack):return '不要在案例迴圈內提早return，否則後面的案例不會讀取。'
        else:
            prefix.append(token)
            if token==';':prefix=[]
    return None
