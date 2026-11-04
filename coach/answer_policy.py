import hashlib
import json
import re
from functools import lru_cache
from django.conf import settings
from .code_format import format_cpp

def requests_solution(question):
    text = re.sub(r'\s+', '', question)
    # A student may discuss wrong answers without requesting a solution.
    if re.search(r'(不要|不想|不用|別|先不|不需要)(直接|再|先)?(給我|给我|提供|顯示|显示|告訴我|告诉我|給|给|看)?(完整|正確|正确)?(答案|解答|解法|程式|代码|代碼)', text) or re.search(r"\b(don't|do not)\s+(give|show|provide)\b", question, re.I):
        return False
    return bool(re.search(r'(給我|提供|顯示|显示|告訴我|告诉我|我要|想看|想要|直接給|直接给|請給|请给).{0,12}(答案|解答|完整解法|完整程式|完整代码|完整代碼|完整代码)', text)
        or re.search(r'(正確答案|正确答案|完整解答|完整解法|完整程式碼)(是什麼|是什么|怎麼寫|怎么写|如何寫|如何写|[？?]|$)', text)
        or re.search(r'\b(show|give|provide)\s+(me\s+)?(the\s+)?(full|complete|correct)\s+(answer|solution|code)\b', question, re.I))

@lru_cache(maxsize=1)
def references():
    path = settings.BASE_DIR / 'data' / 'cpe49-solutions.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def reference_for(problem):
    match = re.match(r'UVa\s+(\d+)\b', getattr(problem, 'title', ''), re.I)
    if not match:
        return None
    item = references().get(match.group(1))
    if not item or item['statement'] != problem.statement:
        return None
    # Do not reuse an audit when the reference program or problem test suite changed.
    tests = [{'name':'範例測資','input':problem.sample_input,'expected':problem.sample_output}] + problem.test_cases[:8]
    if problem.output_comparison != item['tests'][0].get('comparison', 'exact'):
        return None
    expected = [(c['input'], c['expected']) for c in item['tests']]
    if any((c['input'], c['expected']) not in expected for c in tests):
        return None
    digest = hashlib.sha256(json.dumps({'code':item['code'], 'tests':item['tests'], 'policy':'cpp17-docker-v2'}, sort_keys=True).encode()).hexdigest()
    return item if digest == item['audit_sha256'] else None

def reference_answer(item):
    return ('你已明確要求完整解答，以下是本專案題庫的 C++17 參考程式（不是模型臨時生成）。\n\n'
        f"```cpp\n{format_cpp(item['code'])}```\n\n"
        f"這份參考程式的既有驗證紀錄：通過 {len(item['tests'])} 筆專案自編測資；不代表已通過官方評測，也不代表你的程式已通過。\n\n"
        '你可以比較自己的寫法，或指出其中一段，讓助理繼續解釋。')
