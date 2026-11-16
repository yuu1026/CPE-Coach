"""Render recorded adaptive learner actions; no inferred learning scores."""
import argparse
from difflib import unified_diff
import json
from pathlib import Path


def render(report):
    lines=['# 模擬初學者學習紀錄','',
           '這是代理人扮演初學者、逐輪讀取實際本地模型回覆的模擬，不是真實學生研究。程式不預先依正解改好；每次修改理由與原始候選保留於 JSON。',
           '', '路徑：專案教學服務 → 實際本地模型 HTTP；程式測試使用受限 Docker。這份紀錄未測瀏覽器操作。','']
    previous=None
    for index,step in enumerate(report['steps'],1):
        lines += [f'## {index}. '+('執行程式測試' if step.get('action')=='test' else '詢問本地模型'),'']
        lines += ['修改／追問理由：'+step.get('rationale','未記錄'),'']
        if step.get('new_chat') is True:
            lines += ['**此處模擬清除聊天：保留目前程式與測試證據，不再送出舊教學歷史。不得計為原連續教學成功。**','']
        code=step['code']
        if previous is None:
            lines += ['起始程式：','','```cpp',code.rstrip(),'```','']
        elif code!=previous:
            diff=''.join(unified_diff(previous.splitlines(True),code.splitlines(True),fromfile='上一版本',tofile='目前版本'))
            lines += ['實際程式差異：','','```diff',diff.rstrip(),'```','']
        else:
            lines += ['程式沒有修改。','']
        if step.get('judge'):
            result=step['judge'];lines += ['實際測試結果：'+result['label'],'']
            if result.get('compiler'):lines += ['```text',result['compiler'].rstrip(),'```','']
            for case in result.get('cases',[]):
                lines += [f'- {case["name"]}：{case["label"]}；預期 {case["expected"]!r}，實際 {case["actual"]!r}。']
            lines += ['']
        else:
            lines += ['使用者：'+step.get('question',''),'','回覆來源：'+step.get('source','未成功交付')+
                      f'；狀態：{step.get("status")}；模型請求次數：{len(step.get("attempts",[]))}；耗時：{step.get("seconds")}秒。','',
                      step.get('answer') or step.get('error','沒有回覆'),'']
        previous=code
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(render(json.loads(args.report.read_text(encoding='utf-8'))),encoding='utf-8',newline='\n')
