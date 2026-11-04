import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from django.conf import settings
from django.test import TestCase, override_settings
from .answer_policy import requests_solution, reference_for, references
from .reply_quality import traditional_reply
from .services import build_messages, generate_hint, HintError


class ReplyQualityTests(TestCase):
    def problem(self, item):
        return SimpleNamespace(title=f"UVa {item['uva']} · {item['title']}", statement=item['statement'],
            sample_input=item['tests'][0]['input'], sample_output=item['tests'][0]['expected'],
            test_cases=item['tests'][1:], output_comparison=item['tests'][0].get('comparison','exact'))

    def catalog(self):
        return json.loads((Path(settings.BASE_DIR) / 'data/cpe49.json').read_text(encoding='utf-8'))

    def test_explicit_answers_and_negations_are_distinct(self):
        for question in ['給我正確答案', '請提供完整程式碼', '正確答案是什麼？', '不要繞圈，直接給我答案', 'Show me the complete solution']:
            self.assertTrue(requests_solution(question), question)
        for question in ['不要直接給我答案', '不需要完整解答', '我的答案為什麼不對？', '請幫我找錯誤', "Do not give me the complete solution"]:
            self.assertFalse(requests_solution(question), question)

    def test_traditional_prose_does_not_change_code_or_literal_outputs(self):
        answer = '请检查变量与数组。`变量`\n```cpp\ncout << "变量"; //变量\n```\n请重试。'
        result = traditional_reply(answer)
        self.assertIn('請檢查', result)
        self.assertIn('`变量`', result)
        self.assertIn('cout << "变量"; //变量', result)
        self.assertIn('請重試', result)
        self.assertEqual(traditional_reply('請檢查。\n```cpp\n变量'), '請檢查。\n```cpp\n变量')

    def test_all_reference_programs_match_existing_audits(self):
        audit = {r['uva']:r for r in map(json.loads, (Path(settings.BASE_DIR)/'training/data/cpe49/verified_programs.jsonl').read_text(encoding='utf-8').splitlines()) if r['variant']=='correct'}
        for item in self.catalog():
            reference = reference_for(self.problem(item))
            self.assertIsNotNone(reference, item['uva'])
            self.assertEqual(reference['audit_sha256'], audit[item['uva']]['sha256'])
            self.assertEqual(audit[item['uva']]['judge']['status'], 'accepted')
        self.assertEqual(len(references()),49)

    def test_reference_requires_matching_statement_tests_and_code(self):
        problem = self.problem(self.catalog()[0])
        problem.statement += ' changed'
        self.assertIsNone(reference_for(problem))
        problem = self.problem(self.catalog()[0]); problem.sample_output += 'wrong'
        self.assertIsNone(reference_for(problem))
        bad = dict(references()['100'],code='bad code')
        with patch('coach.answer_policy.references',return_value={'100':bad}):
            self.assertIsNone(reference_for(self.problem(self.catalog()[0])))

    def test_tutoring_does_not_expose_solution_but_explicit_request_does(self):
        problem = self.problem(self.catalog()[0])
        tutoring = build_messages(problem,'','請幫我理解題目',1,[])
        self.assertNotIn('reference_solution',json.loads(tutoring[-1]['content']))
        solution = build_messages(problem,'','給我完整解答',1,[])
        with patch('coach.services.httpx.Client') as client:
            reply = generate_hint(solution,1)
        client.assert_not_called()
        self.assertEqual(reply.source,'reference')
        self.assertIn('```cpp',reply)
        self.assertIn('不代表你的程式已通過',reply)

    def test_full_answer_is_saved_as_reference_without_calling_judge_or_model(self):
        import uuid
        from django.contrib.auth import get_user_model
        from .models import Problem, Submission
        from django.urls import reverse
        item = self.catalog()[0]
        fields = vars(self.problem(item))
        problem = Problem.objects.create(**fields, category='CPE 一星選集')
        owner = get_user_model().objects.create_user('solution-reader')
        self.client.force_login(owner)
        with patch('coach.workflows.judge') as judge, patch('coach.services.httpx.Client') as model:
            response = self.client.post(reverse('practice',args=[problem.pk]), {'submission_id':str(uuid.uuid4()),'action':'ask','code':'','question':'給我完整解答','hint_level':'1'})
        self.assertEqual(response.status_code,302)
        record = Submission.objects.get()
        self.assertEqual(record.mode,'reference')
        self.assertEqual(record.status,'done')
        self.assertContains(self.client.get(response.url),'題庫參考解答')
        judge.assert_not_called(); model.assert_not_called()

    @override_settings(HINT_MODE='live')
    def test_english_reply_gets_only_one_retry(self):
        answers = iter(['Here is a detailed answer in English that does not follow the requested language.', '請逐一確認輸入資料的格式。'])
        calls = []
        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={'done':True,'message':{'content':next(answers)}})
        original = httpx.Client
        with patch('coach.services.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            result = generate_hint([{'role':'system','content':'繁體中文'},{'role':'user','content':'{}'}],1)
        self.assertEqual(len(calls),2)
        self.assertEqual(result,'請逐一確認輸入資料的格式。')

    @override_settings(HINT_MODE='live')
    def test_persistent_repetition_stops_after_one_retry(self):
        repeated = '請先確認輸入資料的格式與題目規定是否一致，再用紙筆記錄每一次迴圈中的變數內容，最後比較輸出的結果。'
        messages = [{'role':'system','content':'rules'},{'role':'user','content':'old question'},{'role':'assistant','content':repeated},{'role':'user','content':'我已經做過了'}]
        original = httpx.Client
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'done':True,'message':{'content':repeated}})
        with patch('coach.services.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            with self.assertRaisesMessage(HintError,'已停止重複回答'):
                generate_hint(messages,1)
        self.assertEqual(len(calls),2)
