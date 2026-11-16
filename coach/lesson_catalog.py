"""Authored, bounded lessons; not a claim of general LLM teaching competence."""
import hashlib
import json
import re
from functools import lru_cache
from django.conf import settings

VERSION = 'guided-v2'
SUPPORTED = {10041, 10055}


@lru_cache(maxsize=1)
def statements():
    return {row['uva']: row['statement'] for row in json.loads((settings.BASE_DIR/'data/cpe49.json').read_text(encoding='utf-8'))}


def topic_for(title, statement):
    match = re.match(r'UVa\s+(\d+)\b', title)
    topic = int(match[1]) if match else 0
    return topic if topic in SUPPORTED and statements().get(topic) == statement else None


def signature(topic):
    body={'version':VERSION,'statement':statements()[topic],'scaffold':SCAFFOLDS[topic],'checks':CHECKS,'facts':FACTS}
    return hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


SCAFFOLDS = {
    10041: '''#include <iostream>
#include <vector>
#include <algorithm>
#include <cstdlib>
using namespace std;

int main() {
    int cases;
    if (!(cin >> cases)) return 0;
    while (cases--) {
        int count;
        cin >> count;
        vector<int> houses(count);
        for (int i = 0; i < count; ++i) {
            cin >> houses[i];
        }
        // TODO: 在讀完這組地址後，逐步完成核心運算與輸出。
    }
    return 0;
}
''',
    10055: '''#include <iostream>
#include <cstdlib>
using namespace std;

int main() {
    long long first, second;
    while (cin >> first >> second) {
        // TODO: 根據兩個輸入，完成這一組的運算與輸出。
    }
    return 0;
}
''',
}

# Each answer is checked by the application, never by trusting model prose.
CHECKS = {
    'vito_start': {'concept':'distance','prompt':'三位親戚住在 1、2、3。如果住在 1，距離總和是多少？只回答這個數值即可。','expected':[3],
                   'explanation':'住在 1 時，總距離是 |1-1|+|2-1|+|3-1|=0+1+2=3。','retry':'vito_distance_retry'},
    'vito_distance_retry': {'concept':'distance','prompt':'換個例子：地址 2、4、9，住在 4，距離總和是多少？','expected':[7],
                            'explanation':'距離須分別取絕對值，再相加：|2-4|+|4-4|+|9-4|=2+0+5=7。'},
    'vito_order': {'concept':'sorting','prompt':'先確認排序的作用：9、1、4 排序後的順序是什麼？請依序回答三個數字。','expected':[1,4,9],
                   'explanation':'由小到大依序是 1、4、9；排序不會增加或刪除地址。'},
    'vito_median': {'concept':'median','prompt':'換一組地址 8、1、5：排序後，中間那個地址是多少？','expected':[5],
                    'explanation':'排序後是 1、5、8，中間地址為 5。對一維絕對距離總和可選中位數，不是把地址平均。'},
    'vito_distance': {'concept':'accumulation','prompt':'地址 2、4、9，住在 4，三位親戚的距離總和是多少？','expected':[7],
                      'explanation':'每段距離都非負，總和為 2+0+5=7；不能先加有正負號的差再取一次絕對值。'},
    'vito_output': {'concept':'output','prompt':'如果兩組案例的距離總和分別是 7 與 0，應輸出哪些數值？請依序回答。','expected':[7,0],
                    'explanation':'每組案例輸出一行，依序為 7、0，不加提示文字。'},
    'vito_transfer': {'concept':'transfer','prompt':'最後用未在前面示範的地址 3、8、14：請自行選一個最佳位置，回答最小距離總和（不是地址）。','expected':[11],
                      'explanation':'可選中位數 8，總距離為 |3-8|+|8-8|+|14-8|=5+0+6=11。'},
    'hashmat_start': {'concept':'absolute_difference','prompt':'兩軍人數為 3 和 8，差距應輸出多少？','expected':[5],
                       'explanation':'兩軍差距是 |3-8|=5；原來的差為 -5，取絕對值後才是非負差距。','retry':'hashmat_retry'},
    'hashmat_retry': {'concept':'absolute_difference','prompt':'換一組：兩軍人數 4 和 11，差距應輸出多少？','expected':[7],
                       'explanation':'|4-11|=|-7|=7。絕對值表示到零的距離，不是一律取相反數。'},
    'hashmat_abs': {'concept':'absolute_value','prompt':'abs(-7)、abs(0)、abs(7) 的值依序是多少？','expected':[7,0,7],
                    'explanation':'三者依序為 7、0、7；正數不變，零仍為零，負數才去掉負號。'},
    'hashmat_transfer': {'concept':'transfer','prompt':'兩筆新輸入是 100 60 與 60 100，輸出依序是多少？','expected':[40,40],
                         'explanation':'|100-60|=40、|60-100|=40，交換輸入順序不改變差距。'},
}

FACTS = {
    'median':'地址是一維門牌，目標是絕對距離總和。例：1、2、100，平均取 34 時總距離為 33+32+66=131；選中位數 2 時為 1+0+98=99。排序後將最左、最右成對看，住在一對地址之間時該對距離和不變；中位數落在所有這些區間內，因此可使總和最小。',
    'sorting':'中位數是排序後的中間值，不是原來讀入順序的中間元素。std::sort 要用容器的 begin()、end() 範圍，並在這組地址全部讀完後才排序。排序不會刪除重複地址。',
    'absolute':'絕對值是數到零的距離，結果非負。abs(-7)=7、abs(0)=0、abs(7)=7；它不是一律取相反數。距離應分別取絕對值後再相加。',
    'width':'long long 可以表示正數、零與負數。此題選用它，是為了保存可達 2^32 的非負輸入；兩數相減仍可能為負，所以差距要另外取絕對值。型別可表示負數，與題目要求非負輸出是兩件事。',
}


def check_for(state, key):
    base=CHECKS[key]
    index=state.get('variants',{}).get(key,0)
    if not index:return dict(base)
    concept=base['concept']
    if concept in ('distance','accumulation'):
        a=index+2;b=a+index+2;c=b+2*index+3;value=c-a
        prompt=f'換一個例子：地址 {a}、{b}、{c}，住在 {b}，距離總和是多少？'
        expected=[value];explanation=f'分別取絕對距離：{b-a}+0+{c-b}={value}。'
    elif concept=='sorting':
        a=index+1;b=index+4;c=index+8
        prompt=f'換一組：{b}、{c}、{a} 排序後的三個數字依序是多少？'
        expected=[a,b,c];explanation=f'由小到大依序為 {a}、{b}、{c}。'
    elif concept=='median':
        a=index+1;b=index+4;c=index+8
        prompt=f'換一組地址 {c}、{a}、{b}：排序後的中間地址是多少？'
        expected=[b];explanation=f'排序為 {a}、{b}、{c}，中間地址是 {b}。'
    elif concept=='output':
        a=index+2;b=index*2+5
        prompt=f'兩組案例各算出 {a} 與 {b}，應依序輸出哪些數值？'
        expected=[a,b];explanation=f'每組一行，依序輸出 {a} 與 {b}。'
    elif concept=='transfer' and key.startswith('vito'):
        a=2;b=7+index;c=15+2*index;value=c-a
        prompt=f'再獨立算一組：地址 {a}、{b}、{c}，最小距離總和是多少？'
        expected=[value];explanation=f'可住在中位數 {b}，總和為 {b-a}+0+{c-b}={value}。'
    elif concept=='transfer':
        a=index+10;b=3*index+30;value=b-a
        prompt=f'兩筆輸入為 {a} {b} 與 {b} {a}，應依序輸出多少？'
        expected=[value,value];explanation=f'兩筆都取絕對差，所以均為 {value}。'
    elif concept=='absolute_value':
        a=index+3;b=index+1
        prompt=f'換一組：abs(-{a})、abs(0)、abs({b}) 的值依序是多少？'
        expected=[a,0,b];explanation=f'依序為 {a}、0、{b}；絕對值是到零的距離。'
    else:
        a=index+2;b=3*index+9;value=b-a
        prompt=f'換一組人數 {a} 與 {b}，差距應輸出多少？'
        expected=[value];explanation=f'取絕對差：|{a}-{b}|={value}。'
    return dict(base,prompt=prompt,expected=expected,explanation=explanation)
