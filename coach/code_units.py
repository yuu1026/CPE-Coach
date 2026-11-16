"""Bounded lexical source ranges, independent of physical line breaks.

This is not a full C++ AST. Unsupported raw strings/macros do not get guessed
expression ranges. Every ID is resolved again against the exact current code.
"""
from .diagnostics import TOKENS,code_tokens


def units(code):
    if code_tokens(code) is None:return []
    tokens=[m for m in TOKENS.finditer(code) if not m[0].startswith(('//','/*')) and not m[0].lstrip().startswith('#')]
    ranges=[('include',m.start(),m.end()) for m in TOKENS.finditer(code) if m[0].lstrip().startswith('#include')]
    start=0;depth=0;blocks=[];contexts={}
    for index,token in enumerate(tokens):
        value=token[0]
        if value=='(':depth+=1
        elif value==')':depth=max(0,depth-1)
        if value=='{':
            header=code[tokens[start].start():token.start()].strip()[:120] if start<index else 'block'
            blocks.append(header)
            start=index+1
        elif value=='}':
            header=blocks.pop() if blocks else 'block'
            ranges.append(('block_end',token.start(),token.end()))
            contexts[(token.start(),token.end())]=header
            start=index+1
        if value==';' and depth==0:
            group=tokens[start:index+1]
            if len(group)>1:
                ranges.append(('statement',group[0].start(),token.end()))
                # Offer assignment RHS and each output operand, excluding the
                # statement terminator. The original offsets stay unchanged.
                values=[t[0] for t in group]
                if '=' in values:
                    position=values.index('=')+1
                    if position<len(group)-1:ranges.append(('expression',group[position].start(),group[-2].end()))
                if '<<' in values and any(v in values for v in ('cout','cerr')):
                    positions=[i for i,v in enumerate(values) if v=='<<']
                    for j,position in enumerate(positions):
                        end=positions[j+1] if j+1<len(positions) else len(group)-1
                        if position+1<end:ranges.append(('expression',group[position+1].start(),group[end-1].end()))
            start=index+1
    return [dict(unit_id=f'U{i}',kind=kind,start=left,end=right,code=code[left:right],context=contexts.get((left,right),''))
            for i,(kind,left,right) in enumerate(ranges,1) if right-left<=4096][:96]


def public_units(code):
    return [{key:value for key,value in unit.items() if key not in ('start','end')} for unit in units(code)]
