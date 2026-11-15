"""Recorded GPT/Codex self-review of v7; keep final generation tests untouched."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    dest=ROOT/'training/reports/gemma3-quality-v7'
    report=json.loads((dest/'dev.json').read_text(encoding='utf-8'))
    scores=[(0,4,False,'候選正確將 meetingPoint 宣告移到分支外，移除不必要分支，通過兩組測資；基準仍編譯失敗。'),
            (2,2,True,'候選修正後程式通過測資，但把整數除法結果說成餘數，說明仍有重大概念錯誤。基準漏 std 命名空間而編譯失敗。'),
            (3,0,True,'基準程式通過測資；候選插入 std::max(left,right)，將負數乘積改成正數，並捏造 cout 會取代值。此例明確退步。'),
            (0,5,False,'候選用局部引用正確解釋作用域與分支外宣告，不洩漏整題程式；基準貼出的程式仍然無法編譯。')]
    cases=[dict(id=r['id'],base_score=b,adapter_score=a,rationale=why,adapter_critical_errors=[why] if critical else [])
           for r,(b,a,critical,why) in zip(report['results'],scores)]
    review=dict(review_kind='GPT/Codex self-review; not independent teacher assessment',independent_teacher_review=False,cases=cases)
    (dest/'dev_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    full=[r for r in report['results'] if r['rubric']['full_solution']]
    result=dict(decision='rejected at dev; not enabled',final_test_executed=False,untouched_final_generation_cases=4,
        dev_rule_passed={label:report['summary'][label]['rule_passed'] for label in ['base','adapter']},dev_total=4,
        generated_programs_passed={label:sum(r[label]['code_judge']['status']=='accepted' for r in full) for label in ['base','adapter']},generated_programs_total=len(full),
        self_review_mean={label:sum(r[label+'_score'] for r in cases)/len(cases) for label in ['base','adapter']},
        independent_teacher_review=False,
        reason='Scope repair improved, but multiplication regression and integer-division explanation error remain. Very low loss is not sufficient for promotion.',
        scope='Named instances of seen concepts, synthetic small curriculum. No independent accuracy or broad CPE-generalization claim. Original quality-v4 final generation tests remain untouched.')
    (dest/'decision.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
