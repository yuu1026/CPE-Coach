"""Response needs, not numbered teaching levels. Model chooses explanatory depth."""
import re
from .answer_policy import requests_solution


def wants_edit(question):
    # Restricting a whole rewrite still permits a local edit.
    text=re.sub(r'(?:不要|不用|不必|別).{0,4}(?:整份|整個|全部|整段).{0,4}(?:重寫|改寫|修改)|(?:不要|不用|不必|別)(?:再)?(?:重寫|改寫|修改).{0,3}(?:整份|整個|全部|整段)(?:程式)?','',question)
    if re.search(r'(?:不要|不用|不必|先別|不需要).{0,5}(?:修改|修正|改程式|改寫|貼程式)',text):return False
    return bool(re.search(r'(?:請|幫我|替我|我要|想要).{0,12}(?:修改|修正|更正|替換|新增|加入|加上)|局部(?:修改|修正)|可套用|接下來|下一步',text))


def response_intent(question,history=()):
    text=re.sub(r'\s+','',question)
    if re.fullmatch(r'(?:好|好的|可以|再試一次|請再試一次|再給我看看|請繼續)[。！!？?]*',text) and history:
        previous=history[-1]
        if previous.get('delivered') is False:
            return response_intent(previous.get('question',''))
        if re.search(r'要.{0,8}(?:骨架|雛[型形])',previous.get('hint','')):
            return 'scaffold'
    scaffold=bool(re.search(r'雛[型形]|骨架|模板|\bskeleton\b|\btemplate\b',text,re.I))
    refused=bool(re.search(r'(?:不要|不用|不需要|別|不想要|先不)(?:再|直接)?(?:給我|給|提供)?(?:完整的?|程式碼?的?)?(?:雛[型形]|骨架|模板)',text))
    explicit_answer=requests_solution(question) and bool(re.search(r'完整(?:答案|解答|解法)|正確答案',text))
    asks_scaffold=bool(re.search(r'(?:給我|給|提供|想要|我要|幫我(?:寫|搭)).{0,16}(?:骨架|雛[型形]|模板)|(?:骨架|雛[型形]|模板).{0,8}(?:怎麼寫|如何寫)',text))
    past_scaffold=bool(re.search(r'(?:已|剛|照|貼上|採用|拿到).{0,16}(?:骨架|雛[型形]|模板)',text))
    if scaffold and not refused and not explicit_answer:
        if asks_scaffold and not (past_scaffold and wants_edit(question) and not re.search(r'再(?:給|提供)|重新(?:給|提供|寫)',text)):
            return 'scaffold'
        if not past_scaffold and not re.search(r'什麼是|是什麼|什麼意思|解釋',text) and not wants_edit(question):return 'scaffold'
    return 'solution' if requests_solution(question) else 'conversation'


def explanation_only(question):
    """Past 'your modification' is not a present request to modify code."""
    if wants_edit(question):return False
    no_edit=re.search(r'(?:不要|不用|不必|先別).{0,5}(?:改寫|修改|修正|改程式|貼程式)',question)
    numeric=re.search(r'手算|心算|算術',question)
    trace=re.search(r'程式中的|哪一行|(?:追蹤|引用)(?:我|這|目前)',question)
    if numeric and not trace:return True
    conceptual=re.search(r'觀念|概念|什麼意思|什麼是|解釋.{0,8}(?:語法|意思|原理)|為什麼.{0,8}(?:型別|long long|絕對值)',question)
    return bool(no_edit or conceptual)
