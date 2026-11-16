# 模擬初學者學習紀錄

這是代理人扮演初學者、逐輪讀取實際本地模型回覆的模擬，不是真實學生研究。程式不預先依正解改好；每次修改理由與原始候選保留於 JSON。

路徑：專案教學服務 → 實際本地模型 HTTP；程式測試使用受限 Docker。這份紀錄未測瀏覽器操作。

## 1. 執行程式測試

修改／追問理由：已知Vito題的不同錯誤草稿：使用自己的streets、meeting、cost，先猜第一位親戚家。核心選址修改必須來自模型，不能自行補排序或中位數。

起始程式：

```cpp
#include <iostream>
#include <vector>
#include <cstdlib>
using namespace std;
int main() {
    int rounds; cin >> rounds;
    while (rounds--) {
        int familySize; cin >> familySize;
        vector<int> streets(familySize);
        for (int k = 0; k < familySize; ++k) cin >> streets[k];
        int meeting = streets[0];
        int cost = 0;
        for (int k = 0; k < familySize; ++k) cost += abs(streets[k] - meeting);
        cout << cost << '\n';
    }
}
```

實際測試結果：測資通過 2 / 3

- 題庫範例：答案不符；預期 '99\n'，實際 '100\n'。
- 自編測資2：通過；預期 '99\n'，實際 '99\n'。
- 自編測資3：通過；預期 '0\n0\n'，實際 '0\n0\n'。

## 2. 詢問本地模型

修改／追問理由：先依真實失敗結果詢問本地模型；尚未編輯自己的錯誤演算法。

程式沒有修改。

使用者：我先猜住在第一位親戚家，但範例輸出100，應該99。請根據我現在的streets、meeting、cost程式給一個小步驟，說明為什麼，不要完整答案。

回覆來源：未成功交付；狀態：failed；模型請求次數：2；耗時：35.59秒。

模型兩次局部修改仍未通過片段、編譯或退步檢查，未交付修改。原程式已保留。
修改造成退步：原先通過的案例失敗：自編測資2、自編測資3

## 3. 詢問本地模型

修改／追問理由：只依可見的拒絕訊息追問；沒有讀取或採用被擋下的候選，不自行補中位數或排序。

程式沒有修改。

使用者：系統說修改會讓原本通過的案例失敗，所以沒有交付，我的程式也還沒改。我仍不知道meeting該怎麼選。請沿用streets與familySize，教一個具體可操作的局部修正；如果需要新函式，請教我那行語法，不要完整答案。

回覆來源：未成功交付；狀態：failed；模型請求次數：2；耗時：35.7秒。

模型兩次局部修改仍未通過片段、編譯或退步檢查，未交付修改。原程式已保留。
候選未完成編譯與測試。
main.cpp:11:35: error: stray ‘\’ in program
   11 | int median_index = familySize / 2;\nint median = streets[median_index];\nmeeting = median;
      |                                   ^
main.cpp:11:72: error: stray ‘\’ in program
   11 | int median_index = familySize / 2;\nint median = streets[median_index];\nmeeting = median;
      |                                                                        ^
main.cpp: In function ‘int main()’:
main.cpp:11:36: error: ‘nint’ was not declared in this scope; did you mean ‘uint’?
   11 | int median_index = familySize / 2;\nint median = streets[median_index];\nmeeting = median;
      |                                    ^~~~
      |                                    uint
main.cpp:11:73: error: ‘nmeeting’ was not declared in this scope
   11 | in

## 4. 詢問本地模型

修改／追問理由：只將可見的候選編譯拒絕原因交回模型；原程式未變，也沒有從未交付計畫學取中位數程式。這是本路徑第3次、也是最後一次詢問。

程式沒有修改。

使用者：系統又沒有交付修改，說候選不能編譯，有stray反斜線。我自己的原碼還能編譯，只是答案不對，所以我沒有套用候選。請重新根據原碼給能編譯的最小局部修正，保留meeting與cost，不要完整答案。

回覆來源：未成功交付；狀態：failed；模型請求次數：2；耗時：26.88秒。

模型兩次局部修改仍未通過片段、編譯或退步檢查，未交付修改。原程式已保留。
候選未完成編譯與測試。
main.cpp: In function ‘int main()’:
main.cpp:16:2: error: expected ‘}’ at end of input
   16 | }
      |  ^
main.cpp:5:12: note: to match this ‘{’
    5 | int main() {
      |            ^


## 5. 執行程式測試

修改／追問理由：已達3次詢問上限，沒有任何候選交付，最後重測保留的原程式，確認沒有因錯誤教學退步。

程式沒有修改。

實際測試結果：測資通過 2 / 3

- 題庫範例：答案不符；預期 '99\n'，實際 '100\n'。
- 自編測資2：通過；預期 '99\n'，實際 '99\n'。
- 自編測資3：通過；預期 '0\n0\n'，實際 '0\n0\n'。

