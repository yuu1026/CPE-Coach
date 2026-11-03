"""Build the website-only catalog. Original ten-topic training data stays unchanged.

Summaries and test cases are authored for this project, not official judge data.
Run from any directory: python tools/build_cpe49.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
items = [{k: p[k] for k in ('uva', 'title', 'statement', 'source', 'tests')}
         for p in json.loads((ROOT / 'training/data/problems.json').read_text(encoding='utf-8'))]


def add(number, title, statement, *cases, comparison=None):
    tests = []
    for index, (stdin, expected) in enumerate(cases, 1):
        case = {'name': f'自編測資{index}', 'input': stdin, 'expected': expected}
        if comparison:
            case['comparison'] = comparison
        tests.append(case)
    items.append({'uva': number, 'title': title, 'statement': statement,
                  'source': f'https://onlinejudge.org/external/{number // 100}/{number}.pdf', 'tests': tests})


add(100, 'The 3n + 1 problem',
    '讀取多組正整數 i、j 到 EOF（皆小於 10000）。從 n 開始，奇數改為 3n+1，偶數除以 2，直到 1；週期長度包含起點及最後的 1。求 i 與 j 之間含端點的最大週期長度。每組輸出原始順序的 i j 及最大長度，以空格分隔。',
    ('1 5\n', '1 5 8\n'), ('5 1\n1 1\n', '5 1 8\n1 1 1\n'), ('22 22\n2 3\n', '22 22 16\n2 3 8\n'))
add(118, 'Mutant Flatworld Explorers',
    '首行給矩形右上角 X Y，左下角為 (0,0)，座標最大 50。之後每個機器人先給 x y 方向（N/E/S/W），再給少於 100 字元的指令串，讀到 EOF。L/R 原地左轉／右轉，F 前進一格，北方為 y 增加。越界即停止並在最後合法座標留下氣味；後續機器人在有氣味的位置遇到任何越界前進指令都忽略。每個機器人輸出最終 x y 方向，失蹤者另接 LOST。',
    ('2 2\n1 1 N\nFRF\n', '2 2 E\n'),
    ('1 1\n0 1 N\nF\n0 1 N\nFRF\n', '0 1 N LOST\n1 1 E\n'),
    ('1 1\n0 0 W\nF\n0 0 S\nFRRF\n', '0 0 W LOST\n0 1 N\n'))
add(299, 'Train Swapping',
    '先讀案例數 T。每例給車廂數 L（0 到 50），再給 1 到 L 的排列。每次只能交換相鄰兩節，求排成遞增順序所需的最少交換次數。每例輸出 Optimal train swapping takes S swaps.，S 為答案。',
    ('2\n3\n3 1 2\n4\n1 2 3 4\n', 'Optimal train swapping takes 2 swaps.\nOptimal train swapping takes 0 swaps.\n'),
    ('2\n0\n\n1\n1\n', 'Optimal train swapping takes 0 swaps.\nOptimal train swapping takes 0 swaps.\n'),
    ('1\n5\n5 4 3 2 1\n', 'Optimal train swapping takes 10 swaps.\n'))
add(490, 'Rotating Sentences',
    '讀入文字行到 EOF，最多 100 行，每行最多 100 個字元，空格也是內容。將整塊文字順時針旋轉 90 度：最後一行成為最左欄，第一行成為最右欄。短行缺少的位置以空格補齊。輸出旋轉後各行；本站只對本題忽略每行結尾的補齊空白，行首及行中空白仍須相符。',
    ('ab\ncd\n', 'ca\ndb\n'), ('abc\nx\n', 'xa\n b\n c\n'), ('A B\n12\nZ\n', 'Z1A\n 2 \n  B\n'), comparison='line_rstrip')
add(948, 'Fibonaccimal Base',
    '先讀數量 T（最多 500），接著每例一個小於 100000000 的正整數。使用位權由低到高為 1、2、3、5、8……的費氏表示，數位只能是 0 或 1，不可有相鄰的 1 或前導 0。每例輸出 n = bits (fib)。',
    ('3\n1\n2\n4\n', '1 = 1 (fib)\n2 = 10 (fib)\n4 = 101 (fib)\n'),
    ('3\n8\n10\n12\n', '8 = 10000 (fib)\n10 = 10010 (fib)\n12 = 10101 (fib)\n'),
    ('2\n17\n20\n', '17 = 100101 (fib)\n20 = 101010 (fib)\n'))
add(10008, "What's Cryptanalysis?",
    '先讀文字行數 n，再讀恰好 n 行。統計英文字母出現次數，大小寫視為相同，忽略其他字元。只輸出有出現的字母，轉為大寫，每行格式為 字母 次數。先依次數遞減，同次數按字母遞增。',
    ('2\nAa b!\ncB 123\n', 'A 2\nB 2\nC 1\n'), ('1\nzzzYYx\n', 'Z 3\nY 2\nX 1\n'), ('2\n123!?\n\n', '' ))
items[-1]['source'] = 'https://onlinejudge.org/external/100/p10008.pdf'
add(10019, 'Funny Encryption Method',
    '先讀案例數 T，每例一個十進位正整數 M（不超過 9999）。分別把輸入數字解讀為十進位與十六進位，計算兩者二進位表示中 1 的個數 b1、b2。每例輸出 b1 b2；不需要輸出 XOR 加密結果。',
    ('3\n1\n10\n15\n', '1 1\n2 1\n4 3\n'), ('2\n99\n100\n', '4 4\n3 1\n'), ('1\n9999\n', '8 8\n'))
add(10050, 'Hartals',
    '先讀案例數 T。每例給天數 N（7 到 3650）、政黨數 P，再給 P 個正整數罷工週期。第 1 天是星期日，各黨於其週期倍數的日期罷工，但星期五與星期六不計。若同一天多黨罷工只計一次。每例輸出損失的工作天數。',
    ('1\n14\n2\n3\n4\n', '5\n'), ('2\n7\n2\n1\n1\n7\n1\n8\n', '5\n0\n'), ('1\n14\n2\n6\n13\n', '1\n'))
add(10056, 'What is the Probability?',
    '先讀案例數 T。每例為 N p I：N 位玩家由 1 開始依序輪流嘗試，每次獨立成功機率為 p，首次成功即結束，求第 I 位玩家最後獲勝的機率。N 最多 1000，1≤I≤N，0≤p≤1。每例輸出小數點後四位；p=0 時無人獲勝。',
    ('2\n2 0.5 1\n2 0.5 2\n', '0.6667\n0.3333\n'),
    ('3\n3 0 2\n3 1 1\n3 1 3\n', '0.0000\n1.0000\n0.0000\n'), ('1\n1 0.25 1\n', '1.0000\n'))
add(10057, "A mid-summer night's dream",
    '每組先讀 n（1 到 1000000），再讀 n 個小於 65536 的非負整數，讀到 EOF。找出使所有 |Xi−A| 總和最小的整數 A。每組輸出三個數：最小可行 A、輸入資料中有多少筆的值也是可行 A、以及不同可行整數 A 的總數；重複輸入需逐筆計算。',
    ('4\n1 3 7 9\n', '3 2 5\n'), ('3\n2 2 8\n1\n0\n', '2 2 1\n0 1 1\n'), ('4\n0 0 10 10\n', '0 4 11\n'))
add(10062, 'Tell me the frequencies!',
    '逐行讀取文字到 EOF，每行獨立統計 ASCII 字元（32 到 127）的頻率，不計換行符。每個出現的字元輸出 ASCII碼 次數。依次數遞增，同次數則 ASCII碼遞減排序。兩組輸出之間空一行。每行輸入最多 1000 字元，空格也要計算。',
    ('ABA\nxy\n', '66 1\n65 2\n\n121 1\n120 1\n'), ('a a\n', '32 1\n97 2\n'), ('!!!\n11\n', '33 3\n\n49 2\n'))
add(10093, 'An Easy Problem!',
    '每行是一個可能帶正負號的整數表示，讀到 EOF。數位依序為 0–9、A–Z、a–z，值為 0 到 61。求最小的進位 N（2 到 62），使表示合法且該數可被 N−1 整除。每組輸出最小 N，找不到則輸出 such number is impossible!。',
    ('0\nA\n10\n', '2\n11\n2\n'), ('z\nzz\n', '62\n62\n'), ('-12\n+5\n1z\n', '4\n6\nsuch number is impossible!\n'))
add(10101, 'Bangla Numbers',
    '讀取不超過 999999999999999 的非負整數到 EOF，依 Bangla 單位展開：kuti=10000000、lakh=100000、hajar=1000、shata=100。零值單位不輸出，kuti 可重複分層使用；輸入 0 時輸出 0。每行先輸出靠右對齊寬度 4 的案例序號及句點，後接一個空格與展開文字，詞間以空格分隔。',
    ('0\n105\n', '   1. 0\n   2. 1 shata 5\n'), ('10000001\n100000000000000\n', '   1. 1 kuti 1\n   2. 1 kuti kuti\n'), ('12345678\n', '   1. 1 kuti 23 lakh 45 hajar 6 shata 78\n'))
add(10170, 'The Hotel with Infinite Rooms',
    '每組輸入 S D 到 EOF，1≤S≤10000、1≤D<10^15。第 1 天起 S 人團體住 S 天，接著 S+1 人住 S+1 天，依此類推，團體間沒有空檔。每組輸出第 D 天入住團體的人數；入住與退房當天都包含在住宿期間內。',
    ('3 3\n3 4\n3 7\n3 8\n', '3\n4\n4\n5\n'), ('1 1\n1 6\n1 7\n', '1\n3\n4\n'), ('10000 10000\n10000 10001\n', '10000\n10001\n'))
add(10189, 'Minesweeper',
    '每組輸入列數 n 與欄數 m（1 到 100），再讀 n 行由 * 與 . 組成的地圖；0 0 結束。保留地雷 *，其餘格改成周圍八格的地雷數字。每組先輸出 Field #k:，再輸出結果地圖；組與組之間空一行，編號從 1 開始。',
    ('2 3\n*..\n..*\n0 0\n', 'Field #1:\n*21\n12*\n'),
    ('1 1\n.\n1 1\n*\n0 0\n', 'Field #1:\n0\n\nField #2:\n*\n'), ('3 3\n***\n*.*\n***\n0 0\n', 'Field #1:\n***\n*8*\n***\n'))
add(10190, 'Divide, But Not Quite Conquer!',
    '反覆讀取非負整數 n、m 到 EOF（均小於 2000000000）。嘗試由 n 開始不斷整除 m，直到 1，且每一步數值必須嚴格遞減、不能有餘數。若可行，輸出含 n 與 1 的完整序列，以單一空格分隔；否則輸出 Boring!。需處理 0、1 與除數不合理的情況。',
    ('16 2\n27 3\n', '16 8 4 2 1\n27 9 3 1\n'), ('12 2\n8 1\n0 2\n', 'Boring!\nBoring!\nBoring!\n'), ('2 2\n81 9\n', '2 1\n81 9 1\n'))
add(10193, 'All You Need Is Love',
    '先讀案例數 T。每例有兩個二進位字串，各長 2 到 30、沒有前導 0。判斷能否找到另一個同樣至少兩位的有效二進位數 L，使這兩個數都可以由若干個 L 相加得到。每例輸出 Pair #k: All you need is love! 或 Pair #k: Love is not all you need!。',
    ('2\n110\n1010\n11\n101\n', 'Pair #1: All you need is love!\nPair #2: Love is not all you need!\n'),
    ('1\n10\n10\n', 'Pair #1: All you need is love!\n'), ('1\n1001\n1111\n', 'Pair #1: All you need is love!\n'))
add(10221, 'Satellites',
    '讀取多組 s a unit 到 EOF。地球半徑為 6440 公里，兩顆衛星離地面高度同為 s，中心夾角為 a；unit 為 deg（度）或 min（角分，60 角分=1 度）。求同一圓軌道上的較短弧長與弦長，單位公里，每行依序輸出兩者、小數點後六位。角度超過半圈時取較小夾角。本站以每個數值絕對誤差不超過 0.000001 比較。',
    ('0 0 deg\n', '0.000000 0.000000\n'), ('560 180 deg\n', '21991.148575 14000.000000\n'),
    ('560 60 deg\n560 18000 min\n', '7330.382858 7000.000000\n7330.382858 7000.000000\n'), comparison='float_1e-6')
add(10222, 'Decode the Mad man',
    '讀入一段編碼文字，保留空格。每個英文字母先視為小寫，再換成標準 QWERTY 鍵盤同列左邊第二個按鍵；標點亦按相同位置規則還原。鍵盤由上至下為 `1234567890-=、qwertyuiop[]\\、asdfghjkl;\'、zxcvbnm,./。輸出解碼後的一行文字，輸入會使用可向左移兩格的按鍵。',
    ("kt''[\n", 'hello\n'), ('K[R\n', 'how\n'), ("dyt kt''[\n", 'are hello\n'))
add(10226, 'Hardwood Species',
    '首行為案例數 T，接一空行；每例為多行樹種名稱，一行一棵樹，名稱可能有空格且不超過 30 字元，案例以空行分隔。依名稱字典序輸出每種樹及其占該例總棵數的百分比，保留四位小數，不加百分號。案例輸出間空一行。',
    ('1\n\nOak\nPine\nOak\nOak\n', 'Oak 75.0000\nPine 25.0000\n'),
    ('2\n\nRed Oak\nAsh\n\nPine\n', 'Ash 50.0000\nRed Oak 50.0000\n\nPine 100.0000\n'),
    ('1\n\nC\nA\nB\n', 'A 33.3333\nB 33.3333\nC 33.3333\n'))
add(10235, 'Simply Emirp',
    '逐行讀取整數 N（1<N<1000000）到 EOF。非質數輸出 N is not prime.；若 N 為質數，反轉十進位數字後是不同的質數，輸出 N is emirp.；其餘質數輸出 N is prime.。迴文質數不算 emirp。',
    ('13\n23\n21\n', '13 is emirp.\n23 is prime.\n21 is not prime.\n'), ('11\n2\n', '11 is prime.\n2 is prime.\n'), ('107\n100\n', '107 is emirp.\n100 is not prime.\n'))
add(10242, 'Fourth Point!!',
    '每組輸入八個浮點數，表示平行四邊形兩條相鄰邊的四個端點，兩邊的共同端點會出現兩次；端點順序不固定。讀到 EOF。輸出尚未給出的第四點 x y，以公尺為單位、保留三位小數。座標介於 −10000 到 10000。',
    ('0 0 2 0 0 0 0 3\n', '2.000 3.000\n'), ('2 1 0 0 4 3 2 1\n', '2.000 2.000\n'), ('-1.5 2 0.5 2 -1.5 2 -1.5 4\n', '0.500 4.000\n'))
add(10252, 'Common Permutation',
    '每兩行是一組小寫英文字串，各最多 1000 字元，讀到 EOF；空字串也須保留。找出兩字串共同擁有的字母及其可共同使用的重複次數，輸出能組成的最長字串，字母以遞增順序排列。每組輸出一行，沒有共同字母時輸出空行。',
    ('banana\nananas\n', 'aaann\n'), ('abc\nxyz\n\nabc\n', '\n\n'), ('aabbcc\nbbccdd\n', 'bbcc\n'))
add(10268, '498-bis',
    '每組兩行：第一行是一個整數 x，第二行是由最高次到常數項的多項式整數係數，次數由該行係數個數決定。讀到 EOF。計算此多項式一階導數在 x 的值，每組輸出一個整數；常數多項式的導數為 0，輸入與輸出皆在 32 位元帶號整數範圍內。',
    ('2\n3 0 -4\n', '12\n'), ('0\n2 3 4\n-2\n1 0 0 0\n', '3\n12\n'), ('7\n9\n1\n-3 2\n', '0\n-3\n'))
add(10409, 'Die Game',
    '每組先輸入指令數 n（1 到 1024），再輸入 n 個 north/east/south/west 滾動指令；n=0 結束。每組骰子重新初始化：上面 1、北面 2、西面 3，對面兩面之和為 7。往某方向滾動時原本上面轉到該方向側面。每組輸出最後朝上的數字。',
    ('1\nnorth\n1\neast\n0\n', '5\n3\n'), ('4\nnorth\nnorth\nnorth\nnorth\n2\neast\nwest\n0\n', '1\n1\n'), ('3\nnorth\neast\nsouth\n0\n', '1\n'))
add(10415, 'Eb Alto Saxophone Player',
    '首行為歌曲數 T，每首佔一行，可為空，最多 200 個音符。音符使用 cdefgabCDEFGAB。每個音符需按住的手指編號：c=23478910、d=234789、e=23478、f=2347、g=234、a=23、b=2、C=3、D=1234789、E=123478、F=12347、G=1234、A=123、B=12（其中 10 為第十指）。每首開始所有手指放開；只有上一音未按、本音需按時才計一次按下。每首輸出第 1 到 10 指的按下次數，以單一空格分隔。',
    ('2\ncc\n\n', '0 1 1 1 0 0 1 1 1 1\n0 0 0 0 0 0 0 0 0 0\n'),
    ('1\nCbC\n', '0 1 2 0 0 0 0 0 0 0\n'), ('1\nBcB\n', '2 1 1 1 0 0 1 1 1 1\n'))
add(10420, 'List of Conquests',
    '先讀紀錄數 n（最多 2000），接著 n 行各有國家及姓名。國家是第一個單字，姓名可能含空格。統計各國出現的紀錄數，依國家名稱字典序逐行輸出 國家 數量。',
    ('3\nJapan A B\nTaiwan C\nJapan D\n', 'Japan 2\nTaiwan 1\n'), ('1\nFrance Same Name\n', 'France 1\n'), ('3\nZed X\nAlpha Y\nZed X\n', 'Alpha 1\nZed 2\n'))
add(10642, 'Can You Solve It?',
    '非負座標沿對角線單向前進，路徑依序為 (0,0)→(0,1)→(1,0)→(0,2)→(1,1)→(2,0)→……，即每條 x+y 相同的對角線由 x=0 走到 y=0，再進入下一條。首行案例數 T，每例給 x1 y1 x2 y2，各座標不超過 100000，保證終點可由起點到達。求移動步數，輸出 Case k: steps。',
    ('2\n0 3 3 0\n1 0 0 2\n', 'Case 1: 3\nCase 2: 1\n'), ('1\n2 1 0 4\n', 'Case 1: 2\n'), ('1\n0 0 100000 100000\n', 'Case 1: 20000200000\n'))
add(10908, 'Largest Square',
    '先讀案例數 T。每例先給 M N Q，再給 M 行、每行 N 個字元的矩形，以及 Q 組查詢 r c，座標從 0 起算，M、N 最多 100。每次求以 (r,c) 為中心、完全在矩形內且所有字元都相同的最大正方形邊長。每例先輸出 M N Q，再依序每行輸出一個查詢答案。',
    ('1\n3 3 2\naaa\naaa\naaa\n1 1\n0 0\n', '3 3 2\n3\n1\n'),
    ('1\n3 3 1\naaa\naba\naaa\n1 1\n', '3 3 1\n1\n'), ('2\n1 1 1\nx\n0 0\n3 5 1\nzzzzz\nzzzzz\nzzzzz\n1 2\n', '1 1 1\n1\n3 5 1\n3\n'))
add(10922, '2 the 9s',
    '每行給最多 1000 位的正整數字串 N，單獨的 0 結束。判斷是否為 9 的倍數；若是，反覆將各位數相加直到得到 9，計算相加輪數（原值為 9 時程度為 1）。輸出 N is a multiple of 9 and has 9-degree d.；否則輸出 N is not a multiple of 9.。',
    ('9\n18\n99\n0\n', '9 is a multiple of 9 and has 9-degree 1.\n18 is a multiple of 9 and has 9-degree 1.\n99 is a multiple of 9 and has 9-degree 2.\n'),
    ('10\n999\n0\n', '10 is not a multiple of 9.\n999 is a multiple of 9 and has 9-degree 2.\n'), ('9999999999\n0\n', '9999999999 is a multiple of 9 and has 9-degree 2.\n'))
add(10929, 'You can say 11',
    '逐行讀取最多 1000 位的正整數字串 N，單獨的 0 結束。判斷 N 是否為 11 的倍數，逐行輸出 N is a multiple of 11. 或 N is not a multiple of 11.；保留原輸入數字供輸出，不需要將整個大數存成一般整數。',
    ('11\n121\n123\n0\n', '11 is a multiple of 11.\n121 is a multiple of 11.\n123 is not a multiple of 11.\n'),
    ('22\n101\n0\n', '22 is a multiple of 11.\n101 is not a multiple of 11.\n'), ('11111111111111111111\n0\n', '11111111111111111111 is a multiple of 11.\n'))
costs = ' '.join(['1'] * 36)
all_bases = ' '.join(map(str, range(2, 37)))
add(11005, 'Cheapest Base',
    '首行案例數 T。每例先讀 36 個整數成本（依序對應 0–9、A–Z，值為 1 到 128），再讀查詢數 Q 及 Q 個十進位非負整數（最多 2000000000）。在 2 到 36 進位、不補前導零的表示中，找出總字元成本最低的所有進位，0 本身仍需一個數位 0。每例先輸出 Case k:；每個查詢輸出 Cheapest base(s) for number n:，接所有最低成本進位，遞增且各前置一個空格。案例間空一行。',
    (f'1\n{costs}\n2\n0\n1\n', f'Case 1:\nCheapest base(s) for number 0: {all_bases}\nCheapest base(s) for number 1: {all_bases}\n'),
    (f'1\n{costs}\n2\n10\n36\n', 'Case 1:\nCheapest base(s) for number 10: ' + ' '.join(map(str, range(11,37))) + '\nCheapest base(s) for number 36: ' + ' '.join(map(str, range(7,37))) + '\n'),
    (f'2\n{costs}\n1\n35\n{costs}\n1\n2\n', 'Case 1:\nCheapest base(s) for number 35: 36\n\nCase 2:\nCheapest base(s) for number 2: ' + ' '.join(map(str,range(3,37))) + '\n'),
    ('1\n' + ' '.join(['1', '1'] + ['128'] * 34) + '\n2\n2\n3\n', 'Case 1:\nCheapest base(s) for number 2: 2\nCheapest base(s) for number 3: 2 3\n'))
add(11063, 'B2-Sequence',
    '每組輸入 N（2 到 100）及 N 個整數，讀到 EOF。B2 序列要求所有元素為正且嚴格遞增，並且所有 bi+bj（i≤j）的和互不相同。每組輸出 Case #k: It is a B2-Sequence. 或 Case #k: It is not a B2-Sequence.，每組之後空一行。',
    ('3\n1 2 4\n3\n1 2 3\n', 'Case #1: It is a B2-Sequence.\n\nCase #2: It is not a B2-Sequence.\n\n'),
    ('2\n0 2\n2\n2 1\n', 'Case #1: It is not a B2-Sequence.\n\nCase #2: It is not a B2-Sequence.\n\n'), ('2\n3 3\n2\n3 8\n', 'Case #1: It is not a B2-Sequence.\n\nCase #2: It is a B2-Sequence.\n\n'))
add(11150, 'Cola',
    '每行給最初買到的可樂瓶數 N（1 到 200），讀到 EOF。喝完會留下空瓶，每 3 個空瓶可換 1 瓶可樂；可以借空瓶，但最後必須有足夠空瓶歸還。求最多總共能喝幾瓶，包含原先買的 N 瓶，每組輸出一個整數。',
    ('1\n2\n3\n', '1\n3\n4\n'), ('7\n8\n', '10\n12\n'), ('199\n200\n', '298\n300\n'))
add(11321, 'Sort! Sort!! and Sort!!!',
    '每組給 N M（皆為正且最多 10000），接著 N 個 32 位元整數，0 0 結束。依數字除以 M 的餘數遞增排序；負數餘數採 C/C++ 規則，可為負。餘數相同時奇數先於偶數；兩奇數由大到小、兩偶數由小到大。每組先輸出 N M，再每行一個排序後數字，最後也須輸出結束標記 0 0。',
    ('6 3\n1\n2\n3\n4\n5\n6\n0 0\n', '6 3\n3\n6\n1\n4\n5\n2\n0 0\n'),
    ('5 3\n-5\n-2\n-3\n0\n3\n0 0\n', '5 3\n-5\n-2\n3\n-3\n0\n0 0\n'), ('4 1\n2\n1\n-1\n-2\n0 0\n', '4 1\n1\n-1\n-2\n2\n0 0\n'))
add(11349, 'Symmetric Matrix',
    '首行案例數 T。每例先讀 N = n，再讀 n×n 個整數，n 最多 100，元素可達 ±2^32。只有當所有元素非負，且每個位置都與矩陣中心旋轉 180 度後對應位置相等，才算對稱；不是沿主對角線對稱。輸出 Test #k: Symmetric. 或 Test #k: Non-symmetric.。',
    ('2\nN = 2\n1 2\n2 1\nN = 2\n1 2\n2 3\n', 'Test #1: Symmetric.\nTest #2: Non-symmetric.\n'),
    ('2\nN = 1\n-1\nN = 1\n0\n', 'Test #1: Non-symmetric.\nTest #2: Symmetric.\n'), ('1\nN = 2\n4294967296 0\n0 4294967296\n', 'Test #1: Symmetric.\n'))
add(11417, 'GCD',
    '每行給整數 N（2 到 500），0 結束。對所有 1≤i<j≤N 的整數配對，計算 gcd(i,j) 並加總，每組輸出一個整數。配對不可包含 i=j，也不重複計算反向配對。',
    ('2\n3\n0\n', '1\n3\n'), ('4\n5\n0\n', '7\n11\n'), ('6\n0\n', '20\n'))
add(11461, 'Square Numbers',
    '每組給 a b（1≤a≤b≤100000），0 0 結束。計算閉區間 [a,b] 內有多少個完全平方數，兩端點符合時也要計入，每組輸出一個整數。',
    ('1 1\n2 3\n0 0\n', '1\n0\n'), ('4 9\n5 8\n0 0\n', '2\n0\n'), ('1 100000\n0 0\n', '316\n'))
add(12019, "Doom's Day Algorithm",
    '首行案例數 T，每例給月份 M 與日期 D，保證是西元 2011 年的合法日期。計算星期幾，每組輸出英文全名 Monday、Tuesday、Wednesday、Thursday、Friday、Saturday 或 Sunday。注意年份固定為 2011，並非今天所在年份。',
    ('3\n1 1\n1 2\n1 3\n', 'Saturday\nSunday\nMonday\n'), ('2\n2 28\n3 1\n', 'Monday\nTuesday\n'), ('2\n12 31\n4 4\n', 'Saturday\nMonday\n'))

if __name__ == '__main__':
    assert len(items) == len({p['uva'] for p in items}) == 49
    target = ROOT / 'data/cpe49.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(sorted(items, key=lambda p: p['uva']), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(items)} topics to {target}')
