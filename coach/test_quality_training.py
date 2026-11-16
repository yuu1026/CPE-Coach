import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from unittest.mock import patch
from types import SimpleNamespace
from training.quality_gate import decide

class QualityTrainingTests(SimpleTestCase):
    def test_readable_transport_keeps_question_last_and_repair_instruction(self):
        from coach.model_prompt import readable_messages
        from coach.services import build_messages
        problem=SimpleNamespace(statement='C++17 concepts')
        messages=build_messages(problem,'','為什麼乘法前要轉型？',1,[])
        messages[0]['content']+='\n上一個候選回覆使用了非 C++ 程式碼，請改用 C++17。'
        readable=readable_messages(messages)
        self.assertTrue(readable[-1]['content'].endswith('為什麼乘法前要轉型？'))
        self.assertIn('上一個候選回覆',readable[0]['content'])
        self.assertEqual(json.loads(messages[-1]['content'])['question'],'為什麼乘法前要轉型？')

    def test_blank_code_concept_question_is_not_beginner_mode(self):
        from coach.services import build_messages
        problem=SimpleNamespace(statement='C++17 concepts')
        for question in ['請給一行型別提升再相乘的程式','EOF 是什麼意思？','我已了解輸入格式，接下來呢？']:
            messages=build_messages(problem,'',question,1,[])
            self.assertEqual(json.loads(messages[-1]['content'])['learning_mode'],'discussion' if '接下來' in question else 'explanation')
            self.assertNotIn('進入起步引導模式',messages[0]['content'])
        messages=build_messages(problem,'','我完全沒有想法，怎麼開始？',1,[])
        self.assertEqual(json.loads(messages[-1]['content'])['learning_mode'],'getting_started')

    def test_notes_are_problem_bound_and_do_not_include_solution_code(self):
        from coach.answer_policy import learning_notes_for
        from coach.services import build_messages
        catalog=json.loads((Path(settings.BASE_DIR)/'data/cpe49.json').read_text(encoding='utf-8'))
        robot=next(item for item in catalog if item['uva']==118)
        problem=SimpleNamespace(title='UVa 118 · Robot',statement=robot['statement'])
        notes=learning_notes_for(problem)
        self.assertIn('R 是右轉',notes)
        self.assertNotIn('int main',notes)
        messages=build_messages(problem,'','R 是哪個方向？',1,[])
        self.assertIn('verified_topic_notes',json.loads(messages[-1]['content']))
        problem.statement='a different task'
        self.assertIsNone(learning_notes_for(problem))

    def test_v4_data_has_no_full_solution_in_prompt(self):
        root=Path(settings.BASE_DIR)/'training/data/quality-v4'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        groups=[]
        for split in ['train','eval','test']:
            data=(root/f'{split}.jsonl').read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['sha256'][split])
            rows=[json.loads(line) for line in data.decode().splitlines()]
            groups.append({r['problem_id'] for r in rows if r['problem_id']>0})
            for row in rows:
                self.assertNotIn('reference_solution',row['messages'][-2]['content'])
                self.assertNotIn('verified_diagnostic',json.loads(row['messages'][-2]['content']))
                if row['problem_id']>0:
                    self.assertIn('verified_topic_notes',json.loads(row['messages'][-2]['content']))
        self.assertFalse(groups[0]&groups[1]);self.assertFalse(groups[0]&groups[2]);self.assertFalse(groups[1]&groups[2])

    def test_raw_evaluator_rejects_false_execution_claims(self):
        from training.evaluate_quality import score
        row={'messages':[{'role':'user','content':'尚未測試'},{'role':'assistant','content':'gold'}],
            'rubric':{'concept_any':[],'evidence_status':'not_run','full_solution':False}}
        flags,_=score(row,'目前已經通過全部測試。','stop')
        self.assertFalse(flags['no_unsupported_execution'])
        flags,_=score(row,'尚未執行測試，不能保證通過。','stop')
        self.assertTrue(flags['no_unsupported_execution'])

    def test_code_evaluation_uses_judge_result_not_code_appearance(self):
        from training.evaluate_quality import score
        row={'messages':[{'role':'user','content':'完整解答'},{'role':'assistant','content':'gold'}],
            'rubric':{'concept_any':[],'evidence_status':'not_submitted','full_solution':True},'tests':[{'input':'','expected':'1'}]}
        with patch('training.evaluate_quality.judge',return_value={'status':'failed'}) as judge:
            flags,_=score(row,'以下是程式：\n```cpp\nint main(){}\n```','stop')
        self.assertFalse(flags['generated_code_passes_tests'])
        self.assertEqual(judge.call_args.args[1],row['tests'])

    def test_quality_splits_are_topic_disjoint_and_no_reference_is_in_prompt(self):
        root=Path(settings.BASE_DIR)/'training/data/quality-v3'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        topics=[]; prompt_hashes=[]; identifiers=[]
        for split in ('train','eval','test'):
            data=(root/f'{split}.jsonl').read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),manifest['sha256'][split])
            rows=[json.loads(line) for line in data.decode().splitlines()]
            topics.append({row['problem_id'] for row in rows if row['problem_id']>0})
            prompts=set()
            for row in rows:
                self.assertEqual(row['messages'][-1]['role'],'assistant')
                for message in row['messages'][:-1]:
                    self.assertNotIn('reference_solution',message['content'])
                prompts.add(hashlib.sha256(json.dumps(row['messages'][:-1],sort_keys=True).encode()).hexdigest())
                identifiers.append(row['id'])
            prompt_hashes.append(prompts)
        for i in range(3):
            for j in range(i):
                self.assertFalse(topics[i]&topics[j]); self.assertFalse(prompt_hashes[i]&prompt_hashes[j])
        self.assertEqual(len(identifiers),len(set(identifiers)))
        self.assertEqual(len(set.union(*topics)),49)

    def test_missing_reviews_and_critical_errors_cannot_promote(self):
        dev={'split':'eval','adapter':'v3','summary':{'adapter':{'total':1,'rule_passed':1}},'results':[{'id':'dev'}]}
        test={'split':'test','adapter':'v3','summary':{'adapter':{'total':1,'rule_passed':1}},'results':[{'id':'test'}]}
        review={'review_kind':'GPT/Codex self-review','independent_teacher_review':False,
            'cases':[{'id':key,'base_score':3,'adapter_score':5,'adapter_critical_errors':[]} for key in ['dev','test']]}
        self.assertFalse(decide(dev,test,{'cases':[]})['eligible_for_manual_deployment'])
        self.assertTrue(decide(dev,test,review)['limitations'])
        review['independent_teacher_review']=True
        self.assertTrue(decide(dev,test,review)['eligible_for_manual_deployment'])
        review['cases'][0]['adapter_critical_errors']=['wrong algorithm']
        self.assertFalse(decide(dev,test,review)['eligible_for_manual_deployment'])
