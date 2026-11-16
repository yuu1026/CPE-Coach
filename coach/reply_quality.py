"""Language and repetition checks on prose, preserving code and output literals."""
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from opencc import OpenCC

PROTECTED = re.compile(r'(`+)[^\n]*?\1|https?://[^\s)]+')

@lru_cache(maxsize=1)
def converter():
    return OpenCC('s2twp')

def map_prose(text, transform):
    result, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append(line)
        elif fence is not None or line.startswith(('    ', '\t')):
            result.append(line)
        else:
            parts, start = [], 0
            for match in PROTECTED.finditer(line):
                parts.extend([transform(line[start:match.start()]), match.group()])
                start = match.end()
            parts.append(transform(line[start:]))
            result.append(''.join(parts))
    return ''.join(result)

def traditional_reply(text):
    return map_prose(text, converter().convert)

def prose_only(text):
    # map_prose keeps literals intact; collect only the parts passed to transform.
    collected = []
    map_prose(text, lambda part: collected.append(part) or '')
    return ''.join(collected)

def quality_issue(answer, messages, *, check_grounding=True, check_tutoring=True):
    if non_cpp_code(answer):
        return 'code_language'
    prose = prose_only(answer)
    chinese = len(re.findall(r'[\u3400-\u9fff]', prose))
    english = len(re.findall(r'[A-Za-z]{2,}', prose))
    if chinese < 4 and english >= 8:
        return 'language'
    normalized = re.sub(r'\s+', '', prose)
    latest = next((m['content'] for m in reversed(messages[:-1]) if m['role'] == 'assistant'), '')
    previous = re.sub(r'\s+', '', prose_only(traditional_reply(latest)))
    if len(normalized) >= 30 and previous and SequenceMatcher(None, normalized, previous).ratio() > .88:
        return 'repetition'
    sentences = [s.strip() for s in re.split(r'[。！？\n]', prose) if len(s.strip()) >= 12]
    if len(sentences) >= 3 and len(set(sentences)) <= len(sentences) // 2:
        return 'repetition'
    if check_tutoring:
        try:payload=json.loads(messages[-1]['content'])
        except (ValueError,KeyError,TypeError,IndexError):payload={}
        if isinstance(payload,dict):
            conflict=grounded_conflict(payload,prose)
            if conflict:return conflict
            if payload.get('verified_next_step',{}).get('step')=='median':
                snippets='\n'.join(re.findall(r'```(?:cpp|c\+\+|cxx|cc)?\s*\n(.*?)```',answer,re.S|re.I))
                if re.search(r'\bhome\b',snippets) and not re.search(r'\b(?:int|auto|long\s+long)\s+home\b',snippets):return 'lesson_order'
        if isinstance(payload,dict) and payload.get('response_mode')=='tutor':
            code_blocks=re.findall(r'^ {0,3}(?:`{3,}|~{3,})[^\n]*\n(.*?)(?:^ {0,3}(?:`{3,}|~{3,})|\Z)',answer,re.M|re.S)
            if any(re.search(r'\b(?:int|auto|signed)\s+main\s*\(',block) for block in code_blocks):return 'unrequested_solution'
            if payload.get('learning_mode')=='getting_started' and len(re.findall(r'[?？]',prose))>1:return 'too_many_questions'
    if check_grounding and missing_code_anchor(answer,messages):
        return 'code_grounding'
    return None


def grounded_conflict(payload,prose):
    """Narrow regression guards, not a general semantic correctness checker."""
    if payload.get('verified_calculation'):
        calculation=payload['verified_calculation']
        required=calculation['distance_sum'] if calculation.get('home') is not None else calculation['minimum_sum']
        asks_numeric=re.search(r'總距離.{0,12}(?:多少|是)|距離總和.{0,8}多少|怎麼選|如何選',payload.get('question',''))
        if asks_numeric and not re.search(r'(?<![\d.])'+str(required)+r'(?![\d.])',prose):
            # Replacing a numeric question with another task or code is not
            # a successful answer, even when no false number is asserted.
            return 'calculation_conflict'
        # Verify an explicitly stated cost at an explicitly selected home.
        # Paragraph-local only: do not associate unrelated hypothetical values.
        addresses=payload['verified_calculation']['addresses']
        selected_home=payload['verified_calculation'].get('home')
        for paragraph in re.split(r'\n\n|[。！？]',prose):
            homes=re.findall(r'(?:選擇|住在|home\s*[=是為])\s*(\d+)',paragraph,re.I)
            if homes:
                selected_home=int(homes[0]) if len(set(homes))==1 else None
            totals=re.findall(r'(?:距離總和|總距離|總和)[^。\n]*?=\s*(\d+)(?![\d.])',paragraph)
            # Chained equalities: use the final asserted numeric result.
            if selected_home is not None and totals:
                tail=paragraph[paragraph.find('距離總和'):] if '距離總和' in paragraph else paragraph
                results=re.findall(r'=\s*(\d+)(?![\d.])',tail)
                if results and int(results[-1])!=sum(abs(x-selected_home) for x in addresses):
                    return 'calculation_conflict'
        for expression,value in re.findall(r'(\(?\s*\d+(?:\s*\+\s*\d+)+\s*\)?\s*/\s*\d+)\s*=\s*(\d+\.\d+)',prose):
            if len(expression)>80:continue
            numbers=list(map(int,re.findall(r'\d+',expression)))
            if not numbers[-1] or abs(sum(numbers[:-1])/numbers[-1]-float(value))>10**(-len(value.split('.')[1])):
                return 'calculation_conflict'
    if payload.get('verified_calculation',{}).get('claimed_sum_correct') is True:
        for sentence in re.split(r'[。！？\n]',prose):
            if re.search(r'沒錯|沒有錯|不是.{0,5}錯|並非.{0,5}錯',sentence):continue
            if re.search(r'(?:計算|距離總和).{0,12}(?:錯誤|算錯|不對|有誤)',sentence):return 'calculation_conflict'
    if (payload.get('execution_evidence',{}).get('status')=='accepted' and
        re.search(r'已確認|現在有.{0,5}錯|還有.{0,5}錯|一定要.{0,5}改|通過.{0,6}改',payload.get('question',''))):
        for sentence in re.split(r'[。！？\n]',prose):
            if re.search(r'沒有|未發現|不能確認|無法確認|不代表|不保證|可能|尚未',sentence):continue
            if re.search(r'存在.{0,8}(?:問題|錯誤)|有.{0,4}(?:關鍵|明顯|嚴重)錯誤|需要修正|問題所在',sentence):return 'verdict_conflict'
    if not re.match(r'UVa\s+10041\b',payload.get('problem_title',''),re.I) or not payload.get('verified_topic_notes'):
        return None
    for sentence in re.split(r'[。！？\n]',prose):
        if re.search(r'不是|不能當|不應|不要|並非|錯誤說法',sentence):continue
        if re.search(r'二維|三維|\(\s*x\s*[,，]\s*y\s*\)',sentence):return 'topic_conflict'
        if '歐氏距離' in sentence and not re.search(r'一維|絕對',sentence):return 'topic_conflict'
        if re.search(r'中位數.{0,12}(?:不能|無法|不保證|不一定).{0,12}(?:最小|保證最小)',sentence):return 'topic_conflict'
    return None


def missing_code_anchor(answer,messages):
    """Enforce a source quotation, NOT a semantic correctness verdict.

    Repair quotations must occur in current code (whitespace may differ).
    Pure hand calculations do not need code quotations; new-step snippets may
    instead reuse a student identifier because the new statement is not written.
    This intentionally does not claim that the diagnosis or patch is correct.
    """
    try:
        payload=json.loads(messages[-1]['content'])
    except (ValueError,KeyError,TypeError,IndexError):
        return False
    code=payload.get('code','') if isinstance(payload,dict) else ''
    if not isinstance(code,str) or not code.strip():return False
    # Conceptual next-step coaching is not a diagnosis of an existing statement.
    # Relevance here is assessed by the lesson evaluation, not a quote gate.
    if payload.get('learning_mode') in ('result_review','next_step'):return False
    question=payload.get('question','')
    if '手算' in question and not re.search(r'追蹤|引用|程式中的|我的程式|哪一行|修正|修改',question):return False
    compact=lambda text: re.sub(r'\s+','',text)
    current=compact(code)
    # Require an original expression/statement; standard boilerplate alone
    # should not let a completely unrelated solution satisfy the contract.
    boilerplate={'intmain(){','return0;','usingnamespacestd;','#include<iostream>','std::','main()','cout','cin','int','long','return'}
    candidates=re.findall(r'(?<!`)`([^`\n]+)`(?!`)',answer)
    for block in re.findall(r'```(?:cpp|c\+\+|cxx|cc)?\s*\n(.*?)```',answer,re.S|re.I):
        candidates.extend(block.splitlines())
    if any(len(fragment)>=4 and fragment not in boilerplate and re.search(r'[A-Za-z_]',fragment) and fragment in current for fragment in map(compact,candidates)):
        return False
    # A next-step snippet cannot necessarily quote code that does not exist yet.
    # Require reuse of a student-owned identifier, not only C++ boilerplate.
    if re.search(r'下一步|接下來|還沒|尚未|我已.{0,3}讀',question):
        reserved={'int','long','double','float','char','bool','auto','const','return','std','main','using','namespace','include','iostream','vector','algorithm','cstdlib','iomanip','string','cin','cout','for','while','if','else','size','begin','end','sort','abs'}
        names=set(re.findall(r'\b[A-Za-z_]\w*\b',code))-reserved
        snippets='\n'.join(re.findall(r'```(?:cpp|c\+\+|cxx|cc)?\s*\n(.*?)```',answer,re.S|re.I))
        if names & set(re.findall(r'\b[A-Za-z_]\w*\b',snippets)):return False
    return True


def non_cpp_code(answer):
    """Reject explicit foreign-language blocks and obvious mislabeled snippets.

    This is a format guard, not a C++ compiler or a correctness verdict.
    """
    foreign = re.compile(r'^\s*(?:def\s+\w+\s*\(|from\s+\w+\s+import\b|import\s+\w+|print\s*\(|for\s+\w+\s+in\s+|function\s+\w+\s*\(|console\.log\s*\(|public\s+static\s+void\s+main\s*\(|System\.out\.print|package\s+\w+)', re.M)
    fence, label, body = None, '', []
    def invalid():
        if label in {'text', 'plaintext', 'output'}:
            return False
        if label not in {'', 'cpp', 'c++', 'cxx', 'cc', 'hpp', 'c++17', 'cpp17'}:
            return True
        return bool(foreign.search(''.join(body)))
    for line in answer.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if fence is None and marker:
            fence, label, body = marker[1], marker[2].strip().lower(), []
        elif fence is not None and marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
            if invalid():
                return True
            fence = None
        elif fence is not None:
            body.append(line)
        elif foreign.match(line):
            return True
    return invalid() if fence is not None else False
