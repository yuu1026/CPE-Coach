"""Original teaching examples; official problem statements are linked, not copied."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from coach.judging import judge
from coach.services import SYSTEM

HEADER = '#include <bits/stdc++.h>\nusing namespace std;\n'
CATALOG = []

def add(number, title, statement, code, tests, mutations):
    url = f'https://onlinejudge.org/external/{number // 100}/{number}.pdf'
    CATALOG.append({'uva': number, 'title': title, 'statement': statement, 'source': url, 'code': HEADER + code, 'tests': [{'name': f'自編測資{i+1}', 'input': x, 'expected': y} for i, (x, y) in enumerate(tests)], 'mutations': mutations})

add(10055, 'Hashmat the brave warrior', '反覆讀取兩個非負整數到 EOF，逐行輸出兩者差的絕對值。輸入可達 2^32，順序不固定。',
'''int main(){long long a,b;while(cin>>a>>b)cout<<llabs(a-b)<<"\\n";}''',
[('8 3\n3 8\n','5\n5\n'),('4294967296 0\n','4294967296\n'),('9 9\n1 4\n','0\n3\n')],
[('llabs(a-b)','b-a','差值方向','輸入兩數的先後順序不代表大小。','檢查輸出差值的運算式；交換 8 與 3 的順序，距離應相同。','保留讀入迴圈，局部調整差值的正負處理，使兩種順序都輸出非負距離。'),
 ('long long a,b','int a,b','整數範圍','請比較題目的最大輸入與變數能表示的範圍。','檢查讀入變數的型別；試輸入 4294967296 與 0。','只調整承接輸入與差值的整數型別，讓它能容納題目上界，再重新測試。'),
 ('while(cin>>a>>b)','if(cin>>a>>b)','多筆讀入','題目不只包含一組輸入。','檢查讀入條件是否會持續處理 EOF 前的每一組數值。','保留每組運算，讓讀入與輸出重複到 EOF，而非只執行一次。')])

add(10071, 'Back to High School Physics', '每組讀入 v 與 t，依題意的等加速度運動關係，輸出兩倍時間的位移；多組資料到 EOF。v 可為負，t 可為 0。',
'''int main(){long long v,t;while(cin>>v>>t)cout<<2*v*t<<"\\n";}''',
[('3 4\n','24\n'),('-5 3\n','-30\n'),('7 0\n2 5\n','0\n20\n')],
[('2*v*t','v*t','時間倍數','請重新對照題目要求的是哪一段時間。','檢查位移算式是否對應兩倍時間，先用 v=3、t=4 驗證。','針對目前的算式補上時間尺度所需的倍率，不必改寫讀入流程。'),
 ('2*v*t','llabs(2*v*t)','位移符號','位移與距離的符號意義不同。','題目允許負速度；檢查是否有運算強制把結果變成非負。','移除不符合位移定義的符號處理，保留方向資訊並測試負速度。'),
 ('2*v*t','2*v','遺漏時間','請檢查結果是否真的隨輸入時間改變。','固定 v，改變 t；目前輸出算式是否使用了 t？','只修正位移運算式，讓時間參與計算，並測試 t=0。')])

add(10783, 'Odd Sum', '先讀 T，每組讀 a、b（0≤a≤b≤100），計算閉區間內奇數總和。輸出 Case k: 總和，編號從 1 開始。',
'''int main(){int T;cin>>T;for(int k=1;k<=T;k++){int a,b,sum=0;cin>>a>>b;for(int i=a;i<=b;i++)if(i%2==1)sum+=i;cout<<"Case "<<k<<": "<<sum<<"\\n";}}''',
[('2\n3\n3\n0\n0\n','Case 1: 3\nCase 2: 0\n'),('2\n2\n7\n1\n1\n','Case 1: 15\nCase 2: 1\n')],
[('i<=b','i<b','右邊界','閉區間是否包含兩端？','當 a=b 且為奇數時，檢查內層迴圈會執行幾次。','只調整內層迴圈上界，使合法的右端點能被處理。'),
 ('i%2==1','i%2==0','奇偶條件','題目要累加哪一類整數？','檢查篩選條件，先追蹤區間 2 到 3 會加入哪個數。','局部調整奇偶判斷，讓被加入的是奇數，保留目前累加架構。'),
 ('int a,b,sum=0;','int a,b;static int sum=0;','累加器未重設','不同測試案例的總和應彼此獨立。','觀察第二個案例開始時 sum 是否仍保留前一組結果。','讓每個案例開始時重新初始化累加器，不要跨案例累積。')])

add(11332, 'Summing Digits', '讀取正整數 n（≤2000000000），反覆把十進位各位數加總直到一位數，逐行輸出。遇 0 結束且不輸出。',
'''int main(){long long n;while(cin>>n&&n){while(n>=10){long long s=0;while(n){s+=n%10;n/=10;}n=s;}cout<<n<<"\\n";}}''',
[('99\n19\n0\n','9\n1\n'),('10\n7\n0\n','1\n7\n'),('2000000000\n0\n','2\n')],
[('while(n>=10)','if(n>=10)','只加總一次','一次各位數加總後，結果一定是一位數嗎？','以 99 追蹤：第一次加總後還需要再處理嗎？檢查外層控制。','讓各位數加總可以重複進行，直到真正只剩一位數，不只執行一次。'),
 ('while(n>=10)','while(n>10)','十的邊界','停止條件應涵蓋所有兩位數。','請單獨追蹤 n=10，觀察目前條件是否會進入加總。','調整外層條件對 10 的處理，保留一位數直接輸出的行為。'),
 ('while(cin>>n&&n)','while(cin>>n)','終止值','題目的 0 是資料還是停止訊號？','檢查遇到 0 時是否仍會執行輸出。','在處理一組資料前判斷終止值，使 0 不產生結果。')])

add(10931, 'Parity', '逐行讀正整數到 0 結束。輸出二進位表示與其中 1 的個數，格式為 The parity of B is P (mod 2).；P 保留計數，不先取模。',
'''int main(){unsigned n;while(cin>>n&&n){string b;int c=0;while(n){b+=char('0'+n%2);c+=n%2;n/=2;}reverse(b.begin(),b.end());cout<<"The parity of "<<b<<" is "<<c<<" (mod 2).\\n";}}''',
[('10\n0\n','The parity of 1010 is 2 (mod 2).\n'),('7\n1\n0\n','The parity of 111 is 3 (mod 2).\nThe parity of 1 is 1 (mod 2).\n')],
[('reverse(b.begin(),b.end());','','位元順序','連續取餘數時，先取得高位還是低位？','以 10 追蹤每次附加到 b 的字元，與正常二進位閱讀方向比較。','在輸出前局部整理累積的位元順序，不要改動 1 的計數。'),
 ('<<c<<','<<(c%2)<<','錯誤取模','請對照輸出中的 P 要呈現計數還是取模結果。','用 7 測試，二進位有三個 1；檢查輸出前是否把計數縮成 0 或 1。','保留計數器的完整值，讓固定文字 (mod 2) 與實際計數分開處理。'),
 (' (mod 2).',' (mod 2)','標點格式','文字輸出題也需要精確符合格式。','請比對每行輸出最後一個標點，數字正確仍可能格式不符。','只修正固定輸出文字中缺漏的標點，無須改寫進位轉換。')])

add(272, 'TEX Quotes', '讀取全文到 EOF，將雙引號交替換為兩個反引號與兩個單引號；引號配對狀態跨行延續，其他字元與換行保持原樣。',
'''int main(){char c;bool open=true;while(cin.get(c)){if(c=='"'){cout<<(open?"``":"''");open=!open;}else cout<<c;}}''',
[('"a\nb"\n',"``a\nb''\n"),('x y "z"\n',"x y ``z''\n"),('"" "q"\n',"``'' ``q''\n")],
[('while(cin.get(c)){','while(cin.get(c)){if(c==\'\\n\')open=true;','跨行狀態','換行不一定表示一段引文結束。','檢查遇到換行時是否重設 open；用跨兩行的一對引號追蹤。','讓引號狀態只在真正遇到雙引號時切換，不因換行重新開始。'),
 ('cin.get(c)','cin>>c','空白遺失','除了雙引號，其他字元都要保留。','檢查目前讀字元的方法是否跳過空白與換行。','改用能保留所有字元的讀取方式，維持既有引號切換邏輯。'),
 ('bool open=true','bool open=false','初始狀態','全文第一個雙引號應是開引號。','追蹤第一個引號出現前 open 的初始值，與輸出分支對照。','局部修正初始狀態，讓第一個引號先輸出開引號形式。')])

add(10035, 'Primary Arithmetic', '每組讀兩個不到十位的非負整數，計算直式加法的進位次數，遇 0 0 結束。輸出 No carry operation.、1 carry operation. 或 N carry operations.。',
'''int main(){long long a,b;while(cin>>a>>b&&(a||b)){int carry=0,count=0;while(a||b){carry=(a%10+b%10+carry)>=10;count+=carry;a/=10;b/=10;}if(!count)cout<<"No carry operation.\\n";else if(count==1)cout<<"1 carry operation.\\n";else cout<<count<<" carry operations.\\n";}}''',
[('99 1\n0 0\n','2 carry operations.\n'),('5 5\n123 456\n0 0\n','1 carry operation.\nNo carry operation.\n'),('0 7\n0 0\n','No carry operation.\n')],
[('a%10+b%10+carry','a%10+b%10','未傳遞進位','上一位的進位會影響下一位加法。','用 99 加 1 逐位追蹤，檢查十位是否納入個位產生的進位。','在每位相加時保留傳入進位，之後再更新下一位所需狀態。'),
 ('while(a||b)','while(a&&b)','位數不同','兩數位數不同時，剩下的高位仍可能受到進位影響。','用 99 加 1，檢查其中一個數先除到 0 時迴圈是否太早結束。','調整逐位迴圈的繼續條件，讓仍有位數的一側能被處理。'),
 ('1 carry operation.','1 carry operations.','單複數','輸出文法會依進位次數改變。','專門測試只有一次進位的案例，比對 operation 的字尾。','只修正單次進位分支的固定文字，保持零次與多次分支獨立。')])

add(10038, 'Jolly Jumpers', '每組先讀 n（1≤n≤3000）與 n 個整數，直到 EOF。相鄰差的絕對值須恰好涵蓋 1 到 n-1，成立輸出 Jolly，否則 Not jolly。單元素成立。',
'''int main(){int n;while(cin>>n){vector<int>a(n),seen(n);for(int&i:a)cin>>i;bool ok=true;for(int i=1;i<n;i++){int d=abs(a[i]-a[i-1]);if(d<=0||d>=n||seen[d])ok=false;else seen[d]=1;}cout<<(ok?"Jolly":"Not jolly")<<"\\n";}}''',
[('4 1 4 2 3\n','Jolly\n'),('4 1 2 3 4\n','Not jolly\n'),('1 7\n2 8 8\n','Jolly\nNot jolly\n')],
[('||seen[d]','','重複差值','每個差值需要出現幾次？範圍合法不一定代表涵蓋完整。','用 1、2、3、4 追蹤三個相鄰差，檢查是否有重複卻遺漏其他值。','保留差值範圍檢查，補回已出現差值的判斷，避免重複被接受。'),
 ('abs(a[i]-a[i-1])','(a[i]-a[i-1])','差值符號','題目比較的是相鄰差的絕對值。','對合法序列 1、4、2、3，檢查下降的一步會得到什麼符號。','局部修正差值計算，使上升與下降都以非負差的大小比較。'),
 ('bool ok=true','bool ok=n>1','單元素','沒有相鄰元素時，題目如何定義結果？','單獨測試 n=1，檢查 ok 初始化是否直接否定此案例。','修正初始化對單元素的處理，不要額外排除題目允許的情況。')])

add(10041, 'Vito\'s family', '先讀案例數，每組讀親戚數與地址（可重複），選居住位置使到所有地址的距離總和最小，逐行輸出該最小總和。',
'''int main(){int T;cin>>T;while(T--){int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;sort(a.begin(),a.end());int p=a[n/2],s=0;for(int x:a)s+=abs(x-p);cout<<s<<"\\n";}}''',
[('1\n3 1 2 100\n','99\n'),('1\n3 10 100 1\n','99\n'),('2\n1 7\n4 5 5 5 5\n','0\n0\n')],
[('p=a[n/2]','p=accumulate(a.begin(),a.end(),0)/n','平均數誤用','最小化距離總和與最小化平方距離不相同。','用地址 1、2、100 比較目前選點與較靠近多數人的位置。','先用小例子檢驗選點依據，不要直接假定平均地址最適合；只修正選點部分。'),
 ('sort(a.begin(),a.end());','','未排序','用陣列中間索引前，需要先確認元素具有什麼順序。','將同一組地址換順序輸入，檢查選到的 p 是否會改變結果。','讓索引對應到有序位置後再選點，保留後面的距離累加。'),
 ('abs(x-p)','(x-p)','未取距離','距離能否因方向不同而互相抵消？','追蹤 p 左右兩側地址的貢獻，檢查是否出現負值。','將每個地址的貢獻改為距離大小，再累加，避免方向相消。')])

add(10812, 'Beat the Spread!', '先讀 T，每組給非負整數總分 s 與差 d。求兩個非負整數分數，大者先輸出；無解輸出 impossible。',
'''int main(){int T;cin>>T;while(T--){long long s,d;cin>>s>>d;if(s<d||(s+d)%2)cout<<"impossible\\n";else cout<<(s+d)/2<<" "<<(s-d)/2<<"\\n";}}''',
[('3\n10 3\n2 8\n12 4\n','impossible\nimpossible\n8 4\n'),('2\n0 0\n9 9\n','0 0\n9 0\n')],
[('s<d||(s+d)%2','s<d','奇偶可解性','分數必須是整數，整數除法會隱藏什麼資訊？','用總分 10、差 3 代回檢查，截斷後兩分數能同時滿足條件嗎？','在除法前補上整數可解性的檢查，不要依靠截斷結果當作合法分數。'),
 ('s<d||(s+d)%2','(s+d)%2','非負條件','解除了是整數，還需要滿足什麼符號限制？','用總分 2、差 8，檢查較小分數是否變成負數。','在可解判斷中保留非負分數所需條件，再進行分數計算。'),
 ('<<(s+d)/2<<" "<<(s-d)/2','<<(s-d)/2<<" "<<(s+d)/2','輸出順序','題目指定哪一個分數先輸出？','用總分 12、差 4 對照目前兩個輸出欄位的大小。','只交換輸出欄位次序，確保較大分數先出現。')])

def build():
    destination = ROOT / 'training' / 'data'
    destination.mkdir(parents=True, exist_ok=True)
    train, evaluation, audit = [], [], []
    for item in CATALOG:
        programs = [('correct', item['code'], None)]
        for i, mutation in enumerate(item['mutations']):
            old, new, *rest = mutation
            if item['code'].count(old) != 1:
                raise RuntimeError(f"Ambiguous mutation {item['uva']} {old}")
            programs.append((f'bug{i+1}', item['code'].replace(old, new), mutation))
        for kind, code, mutation in programs:
            evidence = judge(code, item['tests'])
            if kind == 'correct' and evidence['status'] != 'accepted':
                raise RuntimeError(f"Reference failed: {item['uva']} {evidence}")
            if kind != 'correct' and (evidence['status'] != 'failed' or not any(c['status'] == 'wrong_answer' for c in evidence['cases'])):
                raise RuntimeError(f"Mutation not detected as WA: {item['uva']} {kind} {evidence}")
            audit.append({'uva': item['uva'], 'variant': kind, 'judge': evidence})
            for level in (1, 2, 3):
                case_summary = [{'name': c['name'], 'status': c['status']} for c in evidence['cases']]
                failed = next((c for c in evidence['cases'] if c['status'] != 'accepted'), None)
                proof = {'status': evidence['status'], 'label': evidence['label'], 'case_summary': case_summary}
                if failed:
                    proof['failed_case_excerpts'] = [{k: failed[k][:200] for k in ('input', 'expected', 'actual')}]
                payload = {'problem': item['statement'], 'code': code, 'question': '請依指定層級提供回饋，不要給完整答案。', 'hint_level': level, 'previous_attempts': [], 'execution_evidence': proof}
                if kind == 'correct':
                    answer = ['目前程式已通過本次全部測資，未發現需要修改的明確問題。這只代表本次測試結果，不保證涵蓋所有輸入；目前不必為了取得提示而更動程式。', '本次測資全部通過，程式的處理方式與目前題目敘述一致。沒有已確認的錯誤可供定位；如有另一組合法失敗輸入，再一起追蹤。', '目前沒有測試證據顯示需要局部修正，因此不建議加入除錯輸出或任意改動。保留程式即可；若要擴充驗證，可另外加入合法測資。'][level-1]
                else:
                    answer = mutation[3 + level - 1]
                    answer = '測試已出現輸出不符。' + answer
                record = {'id': f"uva{item['uva']}-{kind}-l{level}", 'problem_id': item['uva'], 'variant': kind, 'hint_level': level, 'source': item['source'], 'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}, {'role': 'assistant', 'content': answer}]}
                (evaluation if kind == 'bug3' else train).append(record)
        print(f"Validated UVa {item['uva']}: reference + 3 mutations", flush=True)
    for name, records in [('train.jsonl', train), ('eval.jsonl', evaluation), ('judge_audit.jsonl', audit)]:
        (destination / name).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in records), encoding='utf-8')
    catalog = [{k: v for k, v in p.items() if k != 'mutations'} for p in CATALOG]
    (destination / 'problems.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(train)} training and {len(evaluation)} evaluation examples. Eval is same-problem, held-out bug type; not unseen-problem generalization.')

if __name__ == '__main__':
    build()
