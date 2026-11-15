"""Persist the recorded GPT/Codex dev self-review; no model/API calls here."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'training/reports/gemma3-quality-v5'

# Scores were assigned after reading both complete outputs and the audited
# mutation. These are subjective self-reviews, not an independent benchmark.
STRUCTURED = [
    (0, 3, [], '基準把遇到氣味說成應停止；候選提及忽略越界前進，但未明確定位漏掉的氣味條件。'),
    (1, 1, ['錯誤指責原本正確的倒序列印方向。'], '兩者未定位底線填補，反而要求改動正確的迴圈方向。'),
    (1, 2, [], '基準錯改排序；候選看到缺少 ASCII 32，但未清楚定位空格過濾條件。'),
    (1, 0, ['誤讀實際與預期數值，沒有指出角分應除以 60。'], '實際錯誤是角分乘以 60；兩者都沒有正確定位。'),
    (0, 0, ['捏造 getline 與迴圈錯誤，忽略案例間缺少空行。'], '數值相同，真正差異是輸出空行；兩者皆錯誤歸因。'),
    (2, 1, ['把同餘數奇數排序錯誤歸因為負數餘數。'], '未定位奇數分支應由大到小。'),
    (1, 1, ['引用通過案例作為失敗依據，並將一維陣列當成二維。'], '真正錯誤是轉置與中心對稱混淆；基準也錯解索引意義。'),
    (0, 0, ['回答無關的累加迴圈，未承接型別提升問題。'], '使用者追問乘法轉型；基準也未提供正確提升運算元的方式。'),
    (3, 2, [], '皆未謊稱 AC，但未直接說明沒有執行證據不能確認，候選過度泛問。'),
]
READABLE = [
    (0, 2, [], '基準錯誤要求更新到非法座標；候選只泛問氣味座標，未定位漏檢。'),
    (3, 3, [], '兩者能談缺字補空格，但仍未明確指出底線輸出的局部變體。'),
    (1, 1, ['把缺少空格計數誤解成排序位置錯誤。'], '兩者錯改排序，沒有定位 ASCII 32 被排除。'),
    (1, 0, ['未要求卻提供整題程式，且保留角分乘以 60 的錯誤。'], '基準也錯誤指責正確的弦長公式。'),
    (1, 0, ['未要求卻提供整題程式，保留缺少案例間空行的錯誤。'], '兩者錯誤歸因輸入迴圈。'),
    (4, 1, ['把奇數排序錯誤歸因於負數餘數。'], '基準正確指出奇數遞減、偶數遞增；候選未改善。'),
    (0, 3, [], '基準捏造奇數階矩陣沒有中心；候選定位轉置索引，但修正說明仍不完整。'),
    (2, 2, [], '都要求再貼程式，未承接前文提供最小轉型片段；沒有足夠變數資訊時詢問並非重大錯誤。'),
    (2, 2, [], '都只要求提供程式，未明確說明沒有執行紀錄不能判定 AC。'),
]

def main():
    decisions = []
    for name, scores in [('dev', STRUCTURED), ('dev-readable', READABLE)]:
        report = json.loads((REPORT / f'{name}.json').read_text(encoding='utf-8'))
        assert len(report['results']) == len(scores)
        cases = [dict(id=row['id'], base_score=b, adapter_score=a,
                      adapter_critical_errors=critical, rationale=why)
                 for row, (b, a, critical, why) in zip(report['results'], scores)]
        review = dict(review_kind='GPT/Codex self-review of every dev output',
                      independent_teacher_review=False, score_range=[0, 5], cases=cases)
        (REPORT / f'{name}_review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        decisions.append(dict(transport=name, rule_summary=report['summary'],
            self_review_mean_base=sum(x['base_score'] for x in cases)/len(cases),
            self_review_mean_adapter=sum(x['adapter_score'] for x in cases)/len(cases),
            cases_with_adapter_critical_errors=sum(bool(x['adapter_critical_errors']) for x in cases)))
    decision = dict(decision='rejected at dev; not enabled', final_test_executed=False,
        untouched_final_cases=14, independent_teacher_review=False, experiments=decisions,
        reason='Loss reduction did not produce reliable diagnosis. Readable transport still fails semantic checks. Do not promote or claim high quality.',
        runtime_retrieval='Audited fixture hints are separate authored retrieval, not model accuracy.')
    (REPORT/'decision.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(decisions, ensure_ascii=True))

if __name__ == '__main__':
    main()
