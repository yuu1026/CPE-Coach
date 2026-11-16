import json
from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Problem,Submission
import uuid
from .local_revision import apply_edits,RevisionError,check_candidate,generate_revision
from .services import HintText


TESTS=[{'name':str(i),'input':'','expected':''} for i in range(3)]
CODE='int main(){int x=1; return x;}'


def verdict(statuses):
    return {'status':'accepted' if all(x=='accepted' for x in statuses) else 'failed','label':'測試結果',
            'cases':[dict(name=str(i),status=x,input='',expected='',actual='') for i,x in enumerate(statuses)]}


class LocalRevisionTests(SimpleTestCase):
    def test_exact_unique_nonoverlapping_patches(self):
        self.assertEqual(apply_edits(CODE,[{'before':'int x=1;','after':'int x=0;'}]),CODE.replace('x=1','x=0'))
        bad=[[{'before':'not here','after':'x'}],[{'before':'x','after':'y'}],
             [{'before':'int x=1;','after':'int x=1;'}],
             [{'before':CODE,'after':'int main(){}'}],
             [{'before':'int x=1;','after':'int x=0;'}, {'before':'x=1','after':'x=2'}]]
        for edits in bad:
            with self.assertRaises(RevisionError):apply_edits(CODE,edits)

    def test_cosmetic_change_is_not_a_repair(self):
        with self.assertRaises(RevisionError):apply_edits(CODE,[{'before':'int x=1;','after':'int x = 1; /* already correct */'}])

    def test_server_line_ids_disambiguate_repeated_lines_and_reject_unknown_ids(self):
        code='int a=0;\nint a=0;\n'
        self.assertEqual(apply_edits(code,[{'line_id':'L2','after':'int b=1;'}]),'int a=0;\nint b=1;\n')
        for identifier in ['L0','L3','L-1','L1:L2','1']:
            with self.assertRaises(RevisionError):apply_edits(code,[{'line_id':identifier,'after':'int b=1;'}])

    def test_case_identity_not_just_total_prevents_regression(self):
        old=verdict(['accepted','accepted','wrong_answer'])
        new=verdict(['wrong_answer','accepted','accepted'])
        self.assertIn('退步',check_candidate(old,new,TESTS,False))
        self.assertIsNone(check_candidate(old,verdict(['accepted']*3),TESTS,False))

    def test_compile_failure_and_no_progress_are_rejected(self):
        old=verdict(['wrong_answer']*3)
        self.assertIsNotNone(check_candidate(old,{'status':'compile_error','compiler':'undeclared'},TESTS,False))
        self.assertIn('沒有增加',check_candidate(old,old,TESTS,False))
        self.assertIsNone(check_candidate(old,old,TESTS,True))

    def messages(self):
        return [{'role':'user','content':json.dumps({'code':CODE,'revision_tests':TESTS,'learning_mode':'code_review'})}]

    def plan(self):return HintText(json.dumps({'explanation':'將目前回傳值修正為零。','edits':[{'before':'int x=1;','after':'int x=0;'}]}))

    @patch('coach.local_revision.judge')
    def test_validated_candidate_preserves_original_and_records_both_verdicts(self,judge):
        old=verdict(['wrong_answer','wrong_answer','accepted']);new=verdict(['accepted']*3)
        judge.side_effect=[old,new]
        messages=self.messages()
        text,check=generate_revision(messages,3,lambda *_:self.plan(),str)
        self.assertEqual(check['base_code'],CODE)
        self.assertEqual(check['candidate_code'],CODE.replace('x=1','x=0'))
        self.assertEqual(json.loads(messages[-1]['content'])['code'],CODE)
        self.assertIn('1/3 → 3/3',text)
        self.assertNotEqual(check['base_sha256'],check['candidate_sha256'])

    @patch('coach.local_revision.judge')
    def test_failed_candidate_is_retried_with_feedback_without_rejudging_baseline(self,judge):
        old=verdict(['accepted','wrong_answer','wrong_answer'])
        judge.side_effect=[old,verdict(['wrong_answer']*3),verdict(['accepted']*3)]
        requests=[]
        def generate(messages,level):requests.append(json.loads(messages[-1]['content']));return self.plan()
        _,check=generate_revision(self.messages(),3,generate,str)
        self.assertEqual(judge.call_count,3)
        self.assertEqual(len(requests),2)
        self.assertIn('退步',requests[1]['revision_feedback'])
        self.assertEqual(requests[0]['execution_evidence']['status'],'failed')
        self.assertEqual(len(check['attempts']),2)

    @patch('coach.local_revision.judge')
    def test_no_environment_does_not_publish_or_call_model(self,judge):
        judge.return_value={'status':'unavailable'}
        generate=lambda *_:self.fail('Model must not run without validation infrastructure')
        with self.assertRaisesMessage(RevisionError,'未就緒'):generate_revision(self.messages(),3,generate,str)

    @patch('coach.local_revision.judge')
    def test_passing_student_program_is_preserved_without_model_rewrite(self,judge):
        judge.return_value=verdict(['accepted']*3)
        text,check=generate_revision(self.messages(),3,lambda *_:self.fail('Do not invent a repair'),str)
        self.assertIsNone(check)
        self.assertIn('未呼叫模型',text)

    @patch('coach.local_revision.judge')
    def test_two_bad_plans_are_blocked_without_executing_a_candidate(self,judge):
        judge.return_value=verdict(['wrong_answer']*3)
        with self.assertRaisesMessage(RevisionError,'兩次局部修改'):
            generate_revision(self.messages(),3,lambda *_:HintText('請搬到main開頭。'),str)
        self.assertEqual(judge.call_count,1)

    @patch('coach.local_revision.judge')
    def test_rejected_patch_is_audited_but_not_exposed_in_user_error(self,judge):
        judge.return_value=verdict(['wrong_answer']*3)
        reply=HintText(json.dumps({'explanation':'這是尚未驗證的修改。','edits':[{'before':'missing','after':'REJECTED_PATCH'}]}))
        with self.assertRaises(RevisionError) as caught:
            generate_revision(self.messages(),3,lambda *_:reply,str)
        self.assertNotIn('REJECTED_PATCH',str(caught.exception))
        self.assertEqual(len(caught.exception.audit['attempts']),2)

    def test_prompt_preserves_raw_anchor_and_drops_unverified_assistant_history(self):
        from .model_prompt import readable_messages
        payload=dict(json.loads(self.messages()[-1]['content']),revision_request=True,question='請修正')
        messages=[{'role':'assistant','content':'先前錯誤：搬到main開頭'},{'role':'user','content':json.dumps(payload)}]
        rendered=readable_messages(messages)
        data=json.loads(rendered[-1]['content'])
        self.assertEqual(data['目前學生完整原碼'],CODE)
        self.assertNotIn('先前錯誤',''.join(x['content'] for x in rendered))

    def test_conceptual_reply_cannot_smuggle_an_unverified_cpp_replacement(self):
        from .reply_quality import quality_issue
        messages=[{'role':'user','content':json.dumps({'code':CODE,'guard_local_edits':True})}]
        self.assertEqual(quality_issue('```cpp\nint x=0;\n```',messages),'unverified_edit')
        self.assertIsNone(quality_issue('目前原碼如下。\n```cpp\nint x=1;\n```',messages,check_grounding=False))


@override_settings(HINT_MODE='live')
class RevisionWorkflowTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user('revision-student')
        self.other=get_user_model().objects.create_user('revision-other')
        self.problem=Problem.objects.create(title='UVa 變更驗證測試',category='CPE 一星選集',statement='輸出零',sample_input='0',sample_output='0',test_cases=[{'name':'另一組','input':'1','expected':'0'}])
        self.client.force_login(self.owner)
        self.data={'submission_id':str(uuid.uuid4()),'action':'ask','code':CODE,'question':'請修正我的程式','hint_level':3,
                   'run_custom':'on','custom_input':'2','custom_expected':'0'}

    @patch('coach.services._generate_once')
    @patch('coach.local_revision.judge')
    def test_custom_suite_audit_and_explicit_apply_preserve_student_record(self,judge,model):
        judge.side_effect=[verdict(['wrong_answer','wrong_answer','accepted']),verdict(['accepted']*3)]
        model.return_value=HintText(json.dumps({'explanation':'局部修改回傳變數的值。','edits':[{'before':'int x=1;','after':'int x=0;'}]}))
        response=self.client.post(f'/problem/{self.problem.pk}/',self.data)
        record=Submission.objects.get()
        self.assertEqual(record.code,CODE)
        self.assertEqual(record.status,'done')
        self.assertEqual(record.judge_result['status'],'not_run')
        self.assertEqual(judge.call_args.args[1][-1]['input'],'2')
        self.assertIn('verified_revision',record.messages[-1])
        page=self.client.get(response.url)
        self.assertContains(page,'id="apply-revision"')
        self.assertContains(page,'id="undo-revision"')
        self.assertNotIn('attempts',page.context['verified_revision'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(response.url).status_code,404)

    @patch('coach.services._generate_once',return_value=HintText('搬到main開頭。'))
    @patch('coach.local_revision.judge')
    def test_rejected_plans_have_no_apply_control_and_keep_original(self,judge,model):
        judge.return_value=verdict(['wrong_answer']*3)
        response=self.client.post(f'/problem/{self.problem.pk}/',self.data)
        record=Submission.objects.get()
        self.assertEqual(record.code,CODE)
        self.assertEqual(record.status,'failed')
        self.assertNotContains(self.client.get(response.url),'id="apply-revision"')
        self.assertEqual(model.call_count,2)
