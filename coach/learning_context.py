"""Small, explicit learning context derived from student messages, not model prose."""
import re
from .teaching_tools import vito_calculation


def cpp_concept(question, response_mode):
    if response_mode != 'tutor':
        return False
    if re.search(r'(?:請|幫我|替我).{0,4}(?:修正|修改|改寫|新增)|下一步|接下來', question):
        return False
    return bool(re.search(
        r'作用域|生命週期|懸空|大括號|區塊.{0,5}(?:內|外)|整數除法|浮點|'
        r'轉型|型別|溢位|溢出|static_cast|long long|double|template|average|乘法|除法|'
        r'什麼是.{0,8}(?:迴圈|函式|變數|指標|參考)|為什麼.{0,12}(?:小數|除法)', question, re.I))


def vito_context(question, history):
    """Carry only an explicit address list, never a home or an assistant's guess.

    Recompute every numerical result for the current question. A new invalid
    list or an explicit reset clears the state instead of reviving old values.
    """
    address_marker = r'地址(?:改成|分別是|是|為|在)?\s*[:：]?\s*'
    list_pattern = address_marker + r'([+-]?\d+(?:\s*[,，、]\s*[+-]?\d+)+)'
    def extract(text):
        matches = list(re.finditer(list_pattern, text))
        if not matches:
            if re.search(address_marker+r'[+-]?\d',text):
                return False
            return None
        values = list(map(int, re.findall(r'[+-]?\d+', matches[-1][1])))
        if not 1 < len(values) <= 20 or any(not 0 < n < 30000 for n in values):
            return False
        return values

    current = extract(question)
    state = None
    if current is False:
        return None, None
    if current:
        state = {'addresses': current, 'origin': 'current_user_message'}
    elif re.search(r'換(?:一個|個)?例子|重新開始|清除|另一題|不再使用', question):
        return None, None
    else:
        for turn in reversed(history):
            text = turn.get('question', '')
            values = extract(text)
            if values is False or re.search(r'換(?:一個|個)?例子|重新開始|清除|另一題|不再使用', text) and not values:
                break
            if values:
                state = {'addresses': values, 'origin': 'previous_user_message'}
                break
    if not state:
        return None, None
    # Do not guess the selected home from history. An ambiguous current request
    # (e.g. compare homes 2 and 34) remains unresolved by the narrow calculator.
    canonical = '地址是' + '、'.join(map(str, state['addresses']))
    calculation = vito_calculation(canonical + '。' + question)
    if calculation:
        calculation['address_source'] = state['origin']
    return state, calculation
