"""Persist GPT/Codex review of the completed v6 development experiment."""
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]

def main():
    dest=ROOT/'training/reports/gemma3-quality-v6'
    shutil.copyfile(ROOT/'training/runs/gemma3-quality-v6/training_report.json',dest/'training_report.json')
    report=json.loads((dest/'dev.json').read_text(encoding='utf-8'))
    scores=[(0,0,'兩者都保留區塊內宣告，外部使用仍編譯失敗；候選說只增加空白就能解決作用域，屬重大錯誤。',True),
            (2,3,'基準漏掉 std 命名空間而無法編譯；候選程式通過測資，但後段說明的轉型順序與實際程式不一致，且捏造浮點精度問題。',True),
            (3,3,'兩者程式通過測資；基準誤稱 long long 變數仍為 int，候選增加無關比較大小的建議，文字混簡體。',False),
            (0,2,'基準未修正作用域；候選程式的宣告位置已正確，但解釋仍說放在分支內，且未要求就提供整題程式。',True)]
    cases=[dict(id=row['id'],base_score=b,adapter_score=a,rationale=reason,
                adapter_critical_errors=[reason] if critical else [])
           for row,(b,a,reason,critical) in zip(report['results'],scores)]
    review=dict(review_kind='GPT/Codex self-review; not independent teacher assessment',independent_teacher_review=False,cases=cases)
    (dest/'dev_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    code_rows=[r for r in report['results'] if r['rubric']['full_solution']]
    decision=dict(decision='rejected at dev; not enabled',final_test_executed=False,
        raw_rule_passed={label:report['summary'][label]['rule_passed'] for label in ['base','adapter']},dev_cases=len(cases),
        generated_programs_passed={label:sum(r[label]['code_judge']['status']=='accepted' for r in code_rows) for label in ['base','adapter']},generated_programs_total=len(code_rows),
        self_review_mean={label:sum(r[label+'_score'] for r in cases)/len(cases) for label in ['base','adapter']},
        independent_teacher_review=False,
        limitations=['Small named-instance curriculum; concepts and Vito already seen.','v6 training targets had some inline closing fences; v7 corrects this without overwriting v6.','Historical dev.json by_check counts treated non-applicable checks as passing; generated-program totals here are recomputed from actual code_judge entries. Future evaluator reports include per-check applicable counts.'],
        reason='Critical scope and explanation failures; raw Traditional Chinese and tutoring format not reliable.')
    (dest/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
