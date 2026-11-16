"""Project-authored C++17 cards: narrow grounding, not a general proof engine."""
import re


CARDS = {
    'integer_division': {
        'rule': '兩個運算元都是整數時先做整數除法，結果向零截斷；之後才轉成左側的double。int total=5,count=2; double average=total/count; 得到2.0。要保留小數，應在除法前轉型，例如static_cast<double>(total)/count，得到2.5。',
        'example': 'double average = static_cast<double>(total) / count;',
    },
    'multiply_promotion': {
        'rule': 'x與y是int時，x*y先以int計算；在常見32位int環境100000*100000超出範圍，有號整數溢位是未定義行為。long long area=(long long)(x*y)是乘法後轉型，不能防止已發生的溢位。應在乘法前提升運算元型別，例如1LL*x*y或static_cast<long long>(x)*y；也須確保結果落在long long範圍。',
        'example': 'long long area = 1LL * x * y;',
    },
    'scope_lifetime': {
        'rule': '一般if區塊內的自動區域int變數只能在其作用域中以該名稱使用，離開區塊生命週期結束。指向已結束生命週期物件的指標或參考會懸空，不能用它存取原物件；保留參考不會延長這個一般區域int的生命週期。把值複製到外部仍存活的另一個int物件則可以安全使用該副本；宣告在外層也可讓分支之後繼續使用。作用域與生命週期不同，不可混為一談。',
        'example': 'int saved = 0;\nif (true) { int home = 7; saved = home; }\n// 區塊結束後可使用 saved；不能以 home 名稱使用原變數。',
    },
}


def retrieve(question, code=''):
    text = question + '\n' + code
    keys = []
    if re.search(r'除法|小數|average|平均值|double', question, re.I) and re.search(r'/|除法|整數', text):
        keys.append('integer_division')
    if re.search(r'乘法|溢位|溢出|x\s*\*\s*y|area', question, re.I):
        keys.append('multiply_promotion')
    if re.search(r'作用域|生命週期|懸空|大括號|區塊.{0,5}(?:內|外)', question):
        keys.append('scope_lifetime')
    cards=[dict(id=key, **CARDS[key]) for key in keys]
    for card in cards:
        if card['id']=='scope_lifetime':
            card['copy_targets']=sorted({match[1] for match in re.finditer(r'\b([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\s*;',code)})
    return cards


def conflict(answer, cards):
    """Detect selected known failures; matching cards never certify correctness."""
    text = re.sub(r'[`\s]', '', answer).replace('**','')
    ids = {card['id'] for card in cards}
    if 'integer_division' in ids:
        for sentence in re.split(r'[。！？\n]',text):
            if '向下取整' in sentence and not re.search(r'不是向下取整|並非向下取整|不等於向下取整|不能說.{0,5}向下取整',sentence):
                return True
            if re.search(r'double(?:型別|類型|型態)(?:本身)?(?:沒有|不能|無法)(?:儲存|保存)小數',sentence):
                return True
        if re.search(r'5/2(?:=|等於|得到|結果是)2\.5', text) and not re.search(r'(?:double|浮點|轉型).{0,25}5/2', text):
            return True
        if not re.search(r'整數除法|整數運算|截斷|截去|捨去|先.{0,12}(?:整數|除法)', text):
            return True
    if 'multiply_promotion' in ids:
        for sentence in re.split(r'[。！？\n]',text):
            late_cast=re.search(r'\(longlong\)\([A-Za-z_]\w*\*[A-Za-z_]\w*\)',sentence)
            if late_cast and re.search(r'可以解決|能解決|可以避免|能避免|防止.*溢',sentence) and not re.search(r'不能|無法|不會|並非|不是|不保證',sentence):
                return True
        if not re.search(r'乘法前|相乘前|運算前|先.{0,12}(?:提升|轉型|轉換)|1LL\*|static_cast<longlong>\(', text):
            return True
    if 'scope_lifetime' in ids:
        # The combined scope/reference question requires both lifetime and the
        # safe-copy distinction. A vague "scope ended" answer is insufficient.
        if not re.search(r'生命週期|銷毀|懸空', text):
            return True
        if re.search(r'(?:ref|參考).{0,12}(?:仍然可以|還可以|能夠繼續|可以安全).{0,8}(?:使用|存取|訪問)',text,re.I):
            return True
        if re.search(r'(?:大括號|區塊|作用域)外也能使用',text):
            return True
        for sentence in re.split(r'[。！？\n]',text):
            if (re.search(r'參考|\bref\b',sentence,re.I) and re.search(r'是安全的|可以安全使用',sentence)
                    and not re.search(r'不安全|仍存活|生命週期內|區塊內|結束前|離開前',sentence)):
                return True
        if re.search(r'(?:複製|副本).{0,25}(?:無法安全|不能安全|不安全)', text):
            return True
        copy_targets=[name for c in cards if c['id']=='scope_lifetime' for name in c.get('copy_targets',[])]
        for sentence in re.split(r'[。！？\n]',text):
            if re.search(r'不會|沒有失去|不受',sentence):continue
            for name in copy_targets:
                if re.search(r'(?<![A-Za-z0-9_])'+re.escape(name)+r'(?![A-Za-z0-9_]).{0,20}(?:失去|失效|變成0|被銷毀|不存在)',sentence):
                    return True
    return False


def fallback(cards):
    sections = ['系統 C++ 知識核對：模型候選未通過已知規則檢查，以下改用專案知識卡說明。']
    for card in cards:
        sections.append(card['rule'] + '\n\n通用示範（未套用至你的程式）：\n```cpp\n' + card['example'] + '\n```')
    return '\n\n'.join(sections)
