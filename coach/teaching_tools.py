"""Small deterministic hand-calculation tool, not student-code execution."""
import re

def vito_calculation(question):
    match=re.search(r'地址(?:改成|分別是|是|為|在)?\s*([1-9]\d*(?:\s*[,，、]\s*[1-9]\d*)+)',question)
    if not match or re.match(r'\s*[,，、]\s*[-+]?\d',question[match.end():]):return None
    numbers=list(map(int,re.findall(r'\d+',match[1])))
    if not 1<len(numbers)<=20 or any(not 0<n<30000 for n in numbers):return None
    homes={int(m[1]) for m in re.finditer(r'(?:home\s*(?:=|是|為|：|:)\s*|住在\s*)(\d+)',question,re.I)}
    if len(homes)>1:return None
    home=next(iter(homes)) if homes else None
    claimed=re.search(r'(?:距離總和|總距離)(?:\s*(?:應該|應|是|為|得|算出|=|：|:))?\s*(\d+)',question)
    claim=int(claimed[1]) if claimed else None
    ordered=sorted(numbers);low=ordered[(len(ordered)-1)//2];high=ordered[len(ordered)//2]
    actual=sum(abs(n-home) for n in numbers) if home is not None else None
    return {'addresses':numbers,'address_sum':sum(numbers),'count':len(numbers),'mean':sum(numbers)/len(numbers),'home':home,'distance_sum':actual,'claimed_sum':claim,
            'claimed_sum_correct':claim==actual if claim is not None and actual is not None else None,
            'optimal_interval':[low,high],'minimum_sum':sum(abs(n-low) for n in numbers)}

def calculation_text(result):
    text='一維地址：'+ '、'.join(map(str,result['addresses']))
    text+=f'\n地址加總={result["address_sum"]}，筆數={result["count"]}，數學平均={result["address_sum"]}/{result["count"]}≈{result["mean"]:.9f}（平均不一定最優）。'
    if result['home'] is not None:text+=f'\nhome={result["home"]} 的絕對距離總和={result["distance_sum"]}'
    if result['claimed_sum_correct'] is not None:
        text+=f'\n學生宣稱總和={result["claimed_sum"]}，這個數值'+('正確；不要把選址策略非最佳說成加總算錯。' if result['claimed_sum_correct'] else '不正確，請核對上面的加總。')
    text+=f'\n最小距離總和={result["minimum_sum"]}，可取的位置區間={result["optimal_interval"][0]} 至 {result["optimal_interval"][1]}。'
    return text

def vito_next_step(code):
    """Narrow lesson scaffold for a recognizable single vector<int> draft.

    This is authored curriculum selection, not arbitrary C++ semantic analysis.
    Unknown layouts return None rather than guessing a program transformation.
    """
    body=re.sub(r'//[^\n]*|/\*.*?\*/','',code,flags=re.S)
    vectors=re.findall(r'(?:std::)?vector\s*<\s*int\s*>\s+(\w+)\s*\(\s*(\w+)\s*\)\s*;',body)
    if len(vectors)!=1:return None
    values,count=vectors[0];v=re.escape(values);n=re.escape(count)
    if not re.search(r'(?:std::)?sort\s*\(\s*'+v+r'\.begin\s*\(\s*\)\s*,\s*'+v+r'\.end\s*\(\s*\)\s*\)',body):
        return {'step':'sort','reason':'中間索引只有在排序後才代表中位數；本輪先只完成排序。',
                'placement':'每組地址全部讀完之後、選位置之前','header':'<algorithm>',
                'snippet':f'std::sort({values}.begin(), {values}.end());'}
    median=re.search(r'\b(?:int|auto|long\s+long)\s+(\w+)\s*=\s*'+v+r'\s*\[\s*'+n+r'\s*/\s*2\s*\]\s*;',body)
    if not median:
        if re.search(r'\bhome\b',body):return None
        return {'step':'median','reason':'已排序，現在選上中位數作為位置；奇偶筆數都可用這個位置。',
                'placement':'排序之後','header':'','snippet':f'int home = {values}[{count} / 2];'}
    home=median[1];accumulation=None
    for item in re.findall(r'for\s*\(\s*(?:int|auto)\s+(\w+)\s*:\s*'+v+r'\s*\)',body):
        accumulation=re.search(r'\b(\w+)\s*\+=\s*(?:std::)?abs\s*\(\s*'+re.escape(item)+r'\s*-\s*'+re.escape(home)+r'\s*\)',body)
        if accumulation:break
    if not accumulation:
        if re.search(r'\bdistanceSum\b',body):return None
        return {'step':'distance','reason':'位置已選好；每位親戚到位置的距離須取絕對值，再加總，避免正負互抵。',
                'placement':'選好位置之後，每組案例的 while 區塊內','header':'<cstdlib>',
                'snippet':f'int distanceSum = 0;\nfor (int address : {values})\n    distanceSum += std::abs(address - {home});'}
    total=accumulation[1]
    if not re.search(r'(?:std::)?cout\s*<<\s*'+re.escape(total)+r'\b',body):
        return {'step':'output','reason':'這組的距離總和已累加；本輪只加入每組一行的輸出。',
                'placement':'距離累加迴圈結束後，但仍在處理這組案例的 while 區塊內','header':'',
                'snippet':f'std::cout << {total} << "\\n";'}
    return {'step':'test','reason':'已辨識到主要步驟，下一步請執行測試核對；靜態辨識不代表已編譯或通過。','placement':'執行測試按鈕','header':'','snippet':''}
