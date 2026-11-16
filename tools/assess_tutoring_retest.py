"""Summarize recorded v29 trials, preserving coding vs teaching distinction."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'training/reports'
REVIEWS={
    'hashmat':[(4,'沿用原變數，以abs修正正負差；GCC實測可用，理由將帶符號差值說成符號稍不精確。'),
               (0,'兩個手算候選均正確，但交付被程式引用規則誤擋；這是系統誤擋，不是模型算錯。'),
               (5,'重問後正確手算7、7、0，承接絕對值概念，未要求新程式。')],
    'vito':[(0,'未交付；相同程式只改空白、選址改0造成原通過案例退步。'),
            (0,'未交付；候選含字面反斜線n、未正確完成選址與排序。'),
            (0,'未交付；將候選錯誤歸到原碼的輸出字元，錯換括號導致不能編譯。')],
    'draft':[(2,'交付標頭新增，卻誤稱學生已用sort且有編譯錯；實際原稿可編譯、只是未完成。'),
             (4,'正確保留輸入，在其後加入排序，這是可操作的局部進展。'),
             (0,'未交付；選址候選破壞括號、換行轉義錯誤。'),
             (0,'未交付；要求一行卻提出住址、加總與輸出，且破壞原括號。'),
             (0,'未交付；再次破壞括號、第二候選JSON無效，未能繼續教選址。')]
}


def main():
    output=REPORTS/'retest-v29-assessment.json'
    if output.exists():raise SystemExit('Assessment already exists; preserve it.')
    result={'scope':'Frozen application 04fa415/v29, agent-simulated learners on two seen topics and three paths. Not independent educators, real students, or an all-49-topic accuracy estimate.',
            'reviewer':'Implementing agent; manual delivery-quality review, not blinded teacher review.',
            'rubric':'0=no usable delivered teaching; 1-3=material errors/incomplete guidance; 4=correct actionable teaching; 5=clear correct teaching. Coding completion scored separately.',
            'raw_attempt_issue_note':'Legacy attempts.issue runs a prose checker on raw JSON. It is not the structured-revision pipeline verdict and is NOT used to grade those plans.',
            'paths':{},'overall_reliable_independent_teaching':False}
    for name,reviews in REVIEWS.items():
        session=json.loads((REPORTS/f'retest-v29-{name}.json').read_text(encoding='utf-8'))
        steps=session['steps'];asks=[s for s in steps if s['action']=='ask']
        assert len(asks)==len(reviews)
        assert len(asks)<=(5 if name=='draft' else 3)
        assert all(s['response_mode']=='tutor' and not s.get('new_chat') for s in asks)
        for index,step in enumerate(steps):
            assert hashlib.sha256(step['code'].encode()).hexdigest()==step['code_sha256']
            if index and steps[index-1]['code']!=step['code']:
                previous=steps[index-1]
                assert previous.get('revision_check',{}).get('candidate_code')==step['code']
            check=step.get('revision_check')
            if check:
                assert check['base_code']==step['code']
                old,new=check['baseline']['cases'],check['candidate']['cases']
                assert all(new[i]['status']=='accepted' for i,c in enumerate(old) if c['status']=='accepted')
        tests=[s['judge'] for s in steps if s.get('judge')]
        current=steps[-1]['code']
        completed=any(s.get('judge',{}).get('status')=='accepted' and s['code']==current for s in steps)
        path={'learner_questions':len(asks),'raw_model_calls':sum(len(s['attempts']) for s in asks),
              'delivered':sum(s['status']=='done' for s in asks),'blocked':sum(s['status']=='failed' for s in asks),
              'workflow_seconds':round(sum(s['seconds'] for s in asks),2),
              'coding_completed':completed,'all_turns_at_least_4':all(score>=4 for score,_ in reviews),
              'reviews':[{'turn':i,'delivery_score':score,'reason':reason} for i,(score,reason) in enumerate(reviews,1)],
              'student_test_labels':[t['label'] for t in tests],
              'system_knowledge':[s.get('system_knowledge') for s in asks],
              'source_report':f'retest-v29-{name}.json'}
        if name=='hashmat':
            transfer=json.loads((REPORTS/'retest-v29-hashmat-transfer.json').read_text(encoding='utf-8'))
            assert transfer['code']==current and transfer['judge']['status']=='accepted'
            path['additional_numeric_cases_passed']=transfer['count']
            path['understanding_confirmed_after_rephrase']=True
        result['paths'][name]=path
    result['total_learner_questions']=sum(p['learner_questions'] for p in result['paths'].values())
    result['total_model_calls']=sum(p['raw_model_calls'] for p in result['paths'].values())
    result['coding_paths_completed']=sum(p['coding_completed'] for p in result['paths'].values())
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'questions':result['total_learner_questions'],'model_calls':result['total_model_calls'],
                      'coding_paths_completed':result['coding_paths_completed'],'teaching_qualified':False},ensure_ascii=True))


if __name__=='__main__':main()
