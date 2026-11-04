import json
import re
import uuid
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import Problem, Submission, ProblemCompletion
from .code_format import format_cpp
from .answer_policy import references


class WorkbenchActionsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('actions-owner')
        self.other = get_user_model().objects.create_user('actions-other')
        self.problem = Problem.objects.create(title='UVa 999 · Test',statement='test',sample_input='1',sample_output='1',category='CPE 一星')
        self.client.force_login(self.owner)
        self.payload = {'submission_id':str(uuid.uuid4()),'action':'test','code':'int main(){}','question':'尚未送出的文字'*200,'hint_level':'invalid'}
        self.result = {'status':'accepted','label':'測資通過 1 / 1','cases':[{'name':'範例測資','input':'1','expected':'1','actual':'1','status':'accepted','label':'通過','seconds':.01}]}

    def make_record(self, owner=None, action='ask', parent=None):
        return Submission.objects.create(owner=owner or self.owner,problem=self.problem,parent=parent,code='int main(){}',question='秘密對話',answer='舊提示',hint_level=1,mode='demo',model='demo',action=action,status='tested' if action=='test' else 'done')

    def test_test_endpoint_ignores_chat_draft_and_is_idempotent(self):
        with patch('coach.workflows.judge',return_value=self.result) as judge, patch('coach.workflows.services.generate_hint') as model:
            first = self.client.post(reverse('test_program',args=[self.problem.pk]),self.payload)
            second = self.client.post(reverse('test_program',args=[self.problem.pk]),self.payload)
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json()['record'],second.json()['record'])
        self.assertIn('test-drawer',first.json()['html'])
        record = Submission.objects.get()
        self.assertEqual(record.question,'')
        self.assertEqual(record.messages,[])
        self.assertEqual(judge.call_count,1); model.assert_not_called()
        page = self.client.get(first.json()['url'])
        self.assertNotContains(page,'class="test-event"')

    def test_test_endpoint_rejects_other_users_parent(self):
        other = self.make_record(self.other)
        with patch('coach.workflows.judge') as judge:
            response = self.client.post(reverse('test_program',args=[self.problem.pk]),self.payload | {'parent_submission':other.pk})
        self.assertEqual(response.status_code,404); judge.assert_not_called()

    def test_clear_removes_only_current_users_chat_and_keeps_tests_and_completion(self):
        chat = self.make_record()
        test = self.make_record(action='test',parent=chat)
        self.make_record(parent=test)
        other = self.make_record(self.other)
        ProblemCompletion.objects.create(owner=self.owner,problem=self.problem)
        response = self.client.post(reverse('clear_chat',args=[self.problem.pk]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['parent'],test.pk)
        self.assertTrue(Submission.objects.filter(pk=test.pk).exists())
        self.assertTrue(Submission.objects.filter(pk=other.pk).exists())
        self.assertEqual(Submission.objects.filter(owner=self.owner).count(),1)
        test.refresh_from_db(); self.assertIsNone(test.parent_id)
        self.assertTrue(ProblemCompletion.objects.filter(owner=self.owner,problem=self.problem).exists())

    def test_cleared_chat_does_not_reenter_model_history(self):
        self.make_record()
        self.client.post(reverse('clear_chat',args=[self.problem.pk]))
        with patch('coach.workflows.services.generate_hint',return_value='新的提示'):
            self.client.post(reverse('practice',args=[self.problem.pk]),{'action':'ask','submission_id':str(uuid.uuid4()),'code':'','question':'重新開始','hint_level':'1'})
        record = Submission.objects.get(owner=self.owner)
        self.assertEqual([m['role'] for m in record.messages],['system','user'])

    def test_clear_requires_post_and_csrf(self):
        record = self.make_record()
        self.assertEqual(self.client.get(reverse('clear_chat',args=[self.problem.pk])).status_code,405)
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(reverse('clear_chat',args=[self.problem.pk])).status_code,403)
        self.assertTrue(Submission.objects.filter(pk=record.pk).exists())

    def test_finishing_reply_does_not_recreate_cleared_chat(self):
        def finish_after_clear(*args):
            Submission.objects.filter(owner=self.owner,problem=self.problem).exclude(action='test').delete()
            return '已清除後才完成的回覆'
        with patch('coach.workflows.services.generate_hint',side_effect=finish_after_clear):
            self.client.post(reverse('practice',args=[self.problem.pk]),{'action':'ask','submission_id':str(uuid.uuid4()),'code':'','question':'開始','hint_level':'1'})
        self.assertFalse(Submission.objects.filter(owner=self.owner,problem=self.problem).exists())

    def test_all_reference_formatting_preserves_cpp_tokens(self):
        # Compare tokens while keeping whitespace within strings and chars intact.
        tokens = lambda code: re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s]',code)
        for number, item in references().items():
            pretty = format_cpp(item['code'])
            self.assertEqual(tokens(item['code']),tokens(pretty),number)
            self.assertIn('\n    ',pretty,number)
            self.assertGreater(pretty.count('\n'),item['code'].count('\n'),number)
