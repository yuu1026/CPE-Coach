import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from django.contrib.auth import get_user_model
from .conversation_policy import response_intent,explanation_only
from .forms import SubmissionForm
from .services import build_messages,generate_hint,HintError,HintText
from .model_prompt import readable_messages
from .answer_validation import compile_full_reply
from .reply_quality import quality_issue
from .models import Problem,Submission


SKELETON='#include <iostream>\nint main(){\n    // TODO: 自行完成核心邏輯\n    return 0;\n}\n'
REPLY='先搭好骨架，再完成TODO。\n```cpp\n'+SKELETON+'```'


@override_settings(HINT_MODE='live')
class AdaptiveConversationTests(SimpleTestCase):
    problem=SimpleNamespace(title='CPE 測試題',statement='練習輸入與計算')

    def test_scaffold_and_solution_requests_remain_distinct(self):
        for q in ['可以給我程式碼的雛型嗎','給我完整程式骨架','先不要完整答案，只要C++模板','程式雛形怎麼寫']:
            self.assertEqual(response_intent(q),'scaffold')
        self.assertEqual(response_intent('不要骨架，給我完整解答'),'solution')
        self.assertEqual(response_intent('不用給我骨架，只要解釋觀念'),'conversation')
        self.assertEqual(response_intent('請給我完整修正後的C++'),'solution')
        self.assertEqual(response_intent('什麼是程式骨架？'),'conversation')
        self.assertEqual(response_intent('C++ template 是什麼意思？'),'conversation')
        self.assertEqual(response_intent('我不想要骨架，只想理解題目'),'conversation')

    def test_retry_inherits_failed_request_without_reusing_failed_candidate(self):
        history=[{'question':'給我程式雛型','hint':'未交付','delivered':False}]
        self.assertEqual(response_intent('再試一次',history),'scaffold')

    def test_verified_next_step_does_not_turn_into_scaffold_request(self):
        problem=SimpleNamespace(title="UVa 10041 · Vito's family",statement='地址距離總和最小',sample_input='1\n1 7\n',sample_output='0\n',test_cases=[])
        with patch('coach.services.vito_next_step',return_value={'snippet':'sort(houses.begin(), houses.end());'}):
            messages=build_messages(problem,'int main(){return 0;}','接下來呢？')
        payload=json.loads(messages[-1]['content'])
        self.assertEqual(payload['response_mode'],'tutor')
        self.assertEqual(payload['learning_mode'],'next_step')
        self.assertTrue(payload['revision_request'])

    def test_old_levels_have_no_effect_on_model_input(self):
        first=build_messages(self.problem,'','解釋題目',1,[])
        third=build_messages(self.problem,'','解釋題目',3,[])
        self.assertEqual(first,third)
        self.assertNotIn('hint_level',json.loads(first[-1]['content']))
        text=''.join(m['content'] for m in readable_messages(first))
        self.assertNotIn('五行',text)
        self.assertNotIn('程度 1',text)

    def test_past_modification_does_not_block_current_arithmetic(self):
        question='我照你的修改測試通過了。2、9與9、2都應該是7，這樣對嗎？請手算確認，不要改程式。'
        self.assertTrue(explanation_only(question))
        messages=build_messages(self.problem,'int a=2,b=9;',question,history=[])
        payload=json.loads(messages[-1]['content'])
        self.assertEqual(payload['learning_mode'],'explanation')
        self.assertNotIn('revision_request',payload)
        self.assertIsNone(quality_issue('正確，|2-9|=7，|9-2|=7。',messages))
        self.assertFalse(explanation_only('請修改我的程式，再手算結果'))

    @patch('coach.answer_validation.judge',return_value={'status':'accepted'})
    def test_scaffold_with_main_only_compiles_and_does_not_run_topic_cases(self,judge):
        messages=build_messages(self.problem,'','可以給我程式碼的雛型嗎',history=[])
        self.assertEqual(json.loads(messages[-1]['content'])['response_mode'],'scaffold')
        with patch('coach.services._generate_once',return_value=REPLY):reply=generate_hint(messages)
        self.assertEqual(judge.call_args.args[1],[])
        self.assertIn('骨架通過',reply)
        self.assertIn('未執行題目測資',reply)
        self.assertIn('TODO',reply)

    def test_full_answer_disguised_as_scaffold_is_not_accepted_without_placeholder(self):
        result=compile_full_reply('```cpp\nint main(){return 0;}\n```',{'response_mode':'scaffold'})
        self.assertEqual(result['status'],'missing_program')

    @patch('coach.answer_validation.judge',return_value={'status':'accepted'})
    def test_function_template_is_checked_with_internal_main_not_published_wrapper(self,judge):
        result=compile_full_reply('```cpp\nvoid solve(){ /* TODO */ }\n```',{'response_mode':'scaffold'})
        self.assertEqual(result['status'],'compiled')
        self.assertIn('int main()',judge.call_args.args[0])

    @patch('coach.answer_validation.judge',return_value={'status':'unavailable','label':'Docker unavailable'})
    def test_unverified_scaffold_is_not_delivered(self,judge):
        messages=build_messages(self.problem,'','給我骨架',history=[])
        with patch('coach.services._generate_once',return_value=REPLY):
            with self.assertRaisesMessage(HintError,'未就緒'):generate_hint(messages)

    def test_scaffold_request_is_not_reference_answer_shortcut(self):
        with patch('coach.services.reference_for') as reference:
            messages=build_messages(self.problem,'','給我完整程式骨架',history=[])
        reference.assert_not_called()
        self.assertEqual(json.loads(messages[-1]['content'])['learning_mode'],'scaffold')


@override_settings(HINT_MODE='demo')
class AdaptiveFormTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('adaptive-student')
        self.problem=Problem.objects.create(title='UVa 自然問答測試',category='CPE 一星',statement='練習',sample_input='1',sample_output='1')
        self.client.force_login(self.user)

    def test_submission_without_level_and_legacy_draft_are_supported(self):
        self.assertNotIn('hint_level',SubmissionForm().fields)
        for extras in [{},{'hint_level':'invalid-old-value'}]:
            response=self.client.post(f'/problem/{self.problem.pk}/',dict(submission_id=str(uuid.uuid4()),code='',question='我沒有想法',**extras))
            self.assertEqual(response.status_code,302)
            page=self.client.get(response.url)
            self.assertNotContains(page,'id_hint_level')
            self.assertNotContains(page,'層提示')
        self.assertEqual(Submission.objects.count(),2)
        self.assertTrue(all(s.hint_level==1 for s in Submission.objects.all()))

    def test_old_records_remain_readable_without_grades(self):
        record=Submission.objects.create(owner=self.user,problem=self.problem,code='',question='舊問題',hint_level=3,mode='demo',model='demo',status='done',answer='舊回覆')
        self.assertContains(self.client.get(f'/submission/{record.pk}/'),'舊回覆')
        self.assertNotContains(self.client.get('/'),'第 3 層')

    def test_failed_user_question_stays_in_context_for_retry(self):
        data={'submission_id':str(uuid.uuid4()),'code':'','question':'給我骨架'}
        with patch('coach.workflows.services.generate_hint',side_effect=HintError('暫時失敗')):
            self.client.post(f'/problem/{self.problem.pk}/',data)
        previous=Submission.objects.get()
        with patch('coach.workflows.services.generate_hint',return_value=HintText('DEMO')):
            self.client.post(f'/submission/{previous.pk}/',dict(submission_id=str(uuid.uuid4()),parent_submission=previous.pk,code='',question='再試一次'))
        latest=Submission.objects.order_by('-pk').first()
        payload=json.loads(latest.messages[-1]['content'])
        self.assertEqual(payload['response_mode'],'scaffold')
