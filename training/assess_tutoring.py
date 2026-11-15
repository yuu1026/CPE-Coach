"""Recorded GPT/Codex assessment: functional success is not teaching success."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'training/reports'
    latest=json.loads((folder/'tutoring-vito-v18-20261116.json').read_text(encoding='utf-8'))
    reviews={
        'start':(4,False,'一維小例子與距離計算正確，但已算完後再問答案，互動深度有限。'),
        'confirmed-goal':(4,False,'承接已理解的目標，轉向一個距離計算問題，不再要求重述輸入。'),
        'wrong-mean':(2,False,'沒有再指責131算錯，但只問抽象原因，沒有具體可操作的比較提示。'),
        'even-median':(0,True,'把到同一home的距離錯寫成相鄰地址距離，宣稱選2得100、選100得200；兩者實際均為198。'),
        'read-code':(0,False,'未回傳可用提示，學習者無法依此推進。後續調查發現引用與完整程式檢查的誤擋，以及模型重貼草稿。'),
        'missing-sort':(0,True,'誤稱偶數的int除法會變浮點索引，未定位缺少排序。'),
        'signed-distance':(3,False,'局部abs修正正確，但把本題地址與home說成可能負數，與輸入限制不符；應解釋差值可正可負。'),
        'accepted-code':(4,False,'依4/4實際結果確認無已知錯誤，但可更明確補充這不是所有輸入或官方AC保證。'),
        'transfer':(5,False,'在計算工具輔助下正確說明999，沒有假稱新輸入已執行；不能計作模型獨立算術能力。'),
    }
    cases=[dict(id=r['id'],status=r['status'],score=reviews[r['id']][0],critical=reviews[r['id']][1],reason=reviews[r['id']][2]) for r in latest['turns']]
    phases=[]
    for version in [15,16,17,18]:
        report=json.loads((folder/f'tutoring-vito-v{version}-20261116.json').read_text(encoding='utf-8'))
        phases.append(dict(version=version,turns=len(report['turns']),completed=sum(r['status']=='done' for r in report['turns']),
            all_real_local_model=all(r['mode']=='live' for r in report['turns']),temporary_account_deleted=report['cleanup']))
    result=dict(decision='not achieved: reliable autonomous tutoring',
        review_kind='GPT/Codex self-assessment of every latest complete scripted turn; not independent teacher grading',
        independent_teacher_review=False,
        scope='Repeated seen-topic regression scripts, revised after failures. Predetermined learner progress is not proof of actual student learning. No global 49-topic accuracy claim.',
        acceptance='Every turn >=4/5, no critical semantic error, and actionable progress from incomplete code.',
        phases=phases,latest_complete_script='tutoring-vito-v18-20261116.json',cases=cases,
        mean_self_score=sum(r['score'] for r in cases)/len(cases),turns_at_least_4=sum(r['score']>=4 for r in cases),total_turns=len(cases),
        adaptive_following=dict(report='adaptive-tutoring-vito-20261116.json',completed_program=False,
            observed=['One valid sorting addition delivered after curriculum selection and local-diff projection.','Next reply used home before declaring it.','Actual Docker compilation failed; tester did not silently repair it.','Clarification produced fixed home=0 and repeated main; the guard rejected it.'],
            current_mitigation='Latest code blocks the observed use-before-declaration lesson skip, but blocking is not successful teaching.'),
        deployed_weights='Gemma 3 4B IT base; rejected v6/v7 adapters remain local experiments',
        assistance='Curated topic facts, deterministic calculation, narrow recognizable-draft curriculum, and verified local projection are app support, not proof of bare model ability.')
    targeted=folder/'tutoring-step-integration-v22-20261116.json'
    if targeted.exists():
        turn=json.loads(targeted.read_text(encoding='utf-8'))['turns'][0]
        result['latest_targeted_integration']=dict(report=targeted.name,status=turn['status'],prompt_version=turn['prompt_version'],
            projection=turn.get('tutoring_projection'),semantic_pass=False,
            reason='Correct sorting snippet displayed, but trailing explanation asks for the location nearest an as-yet-unselected home; circular and not a valid next algorithmic step. A single-stage integration success is not a complete teaching pass.')
    (folder/'tutoring_assessment_20261116.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'decision':result['decision'],'mean_self_score':result['mean_self_score'],'turns_at_least_4':result['turns_at_least_4'],'phases':phases}))

if __name__=='__main__':main()
