import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Problem, Submission, ProblemCompletion
from .services import HintError, build_messages, generate_hint

class WorkflowTests(TestCase):
    def setUp(self):
        self.judge_patch = patch('coach.workflows.judge', return_value={'status': 'unavailable', 'label': '測試不啟動 Docker', 'cases': []})
        self.judge_patch.start()
        self.addCleanup(self.judge_patch.stop)
        self.owner = get_user_model().objects.create_user('student', password='test-only')
        self.other = get_user_model().objects.create_user('other', password='test-only')
        self.problem = Problem.objects.create(title='UVa 測試題', statement='計算輸入總和', sample_input='1', sample_output='1', category='CPE 一星選集')
        self.url = reverse('practice', args=[self.problem.pk])
        self.payload = {'submission_id': str(uuid.uuid4()), 'code': '<script>alert(1)</script>', 'question': '如何檢查', 'hint_level': '1'}

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    @override_settings(HINT_MODE='demo')
    def test_submit_replay_and_owner_isolation(self):
        self.client.force_login(self.owner)
        first = self.client.post(self.url, self.payload)
        second = self.client.post(self.url, self.payload)
        self.assertEqual(first.url, second.url)
        self.assertEqual(Submission.objects.count(), 1)
        record = Submission.objects.get()
        self.assertEqual(record.status, 'done')
        self.assertTrue(record.messages)
        self.assertContains(self.client.get(first.url), '&lt;script&gt;')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(first.url).status_code, 404)
        self.assertNotContains(self.client.get('/'), 'REVISION #')

    def test_failure_keeps_code_and_does_not_retry_on_refresh(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.services.generate_hint', side_effect=HintError('模型不可用')) as call:
            response = self.client.post(self.url, self.payload)
            self.client.get(response.url)
            self.client.post(self.url, self.payload)
        self.assertEqual(call.call_count, 1)
        record = Submission.objects.get()
        self.assertEqual(record.status, 'failed')
        self.assertEqual(record.code, self.payload['code'])

    def test_invalid_inputs(self):
        self.client.force_login(self.owner)
        for change in [{'hint_level': 4}, {'submission_id': 'invalid'}]:
            self.assertEqual(self.client.post(self.url, self.payload | change).status_code, 200)
        self.assertEqual(Submission.objects.count(), 0)

    @override_settings(HINT_MODE='demo')
    def test_empty_code_starts_guidance_without_judge(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge') as judge:
            response = self.client.post(self.url, self.payload | {'code': '  \n ', 'question': ''})
        judge.assert_not_called()
        record = Submission.objects.get()
        self.assertEqual(record.code, '')
        self.assertEqual(record.status, 'done')
        self.assertEqual(record.judge_result['status'], 'not_submitted')
        self.assertIn('getting_started', record.messages[1]['content'])
        self.assertIn('起步引導模式', record.messages[0]['content'])
        self.assertNotIn('你的程式', record.answer)
        self.assertContains(self.client.get(response.url), '尚未撰寫程式')

    @override_settings(HINT_MODE='demo')
    def test_starting_guidance_retains_followup_answer(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, self.payload | {'code': '', 'question': '我沒有想法'})
        import json
        next_payload = self.payload | {'submission_id': str(uuid.uuid4()), 'code': '', 'question': '輸入是兩個數，輸出是距離'}
        self.client.post(reverse('detail', args=[Submission.objects.first().pk]), next_payload)
        current = Submission.objects.first()
        payload = json.loads(current.messages[-1]['content'])
        self.assertEqual(payload['question'], next_payload['question'])
        self.assertEqual([m['role'] for m in current.messages], ['system', 'user', 'assistant', 'user'])

    @override_settings(CONTEXT_TOKENS=1600, MODEL_URL='http://127.0.0.1:11434')
    def test_context_rejected_without_truncation(self):
        with self.assertRaises(HintError):
            build_messages(self.problem, 'a' * 5000, '', 1, [])

    @override_settings(CONTEXT_TOKENS=4096, MODEL_URL='http://127.0.0.1:11436')
    def test_local_bridge_uses_server_token_budget(self):
        import json
        code = '// 中文程式註解\n' * 100
        history = [{'question': '問題' * 1000, 'hint': '舊提示' * 1000}] * 3
        evidence = {'status': 'accepted', 'label': '測資通過 4 / 4', 'cases': [{'name': '最大筆數', 'status': 'accepted', 'input': '1000 ' * 1000, 'expected': '1', 'actual': '1'}]}
        messages = build_messages(self.problem, code, '', 1, history, evidence)
        payload = json.loads(messages[-1]['content'])
        self.assertEqual(payload['code'], code)
        self.assertEqual(len(messages), 8)
        self.assertEqual(payload['execution_evidence']['failed_case_excerpts'], [])
        self.assertNotIn('1000 1000', messages[1]['content'])

    @override_settings(HINT_MODE='live', MODEL_URL='http://127.0.0.1:11436')
    def test_exact_token_rejection_is_explained(self):
        import httpx
        original = httpx.Client
        transport = httpx.MockTransport(lambda request: httpx.Response(400, json={'code': 'context_limit'}))
        with patch('coach.services.httpx.Client', side_effect=lambda **kw: original(transport=transport, **kw)):
            with self.assertRaisesMessage(HintError, '模型實際輸入長度'):
                generate_hint([], 1)

    @override_settings(HINT_MODE='live')
    def test_live_response_contract(self):
        import httpx
        def handler(request):
            return httpx.Response(200, json={'done': True, 'message': {'content': '請先追蹤邊界值'}})
        original_client = httpx.Client
        with patch('coach.services.httpx.Client', side_effect=lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw)):
            self.assertEqual(generate_hint([], 1), '請先追蹤邊界值')

    def test_pages_render(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/'), 'CPE Coach')
        self.assertContains(self.client.get(self.url), 'DEMO')

    def test_cpe_dropdown_and_legacy_problem_restriction(self):
        self.client.force_login(self.owner)
        legacy = Problem.objects.create(title='舊示範題', statement='demo', sample_input='1', sample_output='1', category='基礎')
        home = self.client.get('/')
        self.assertContains(home, 'id="problem-select"')
        self.assertContains(home, self.problem.title)
        self.assertNotContains(home, legacy.title)
        self.assertRedirects(self.client.get(reverse('choose_problem'), {'problem': self.problem.pk}), self.url)
        self.assertEqual(self.client.get(reverse('choose_problem'), {'problem': legacy.pk}).status_code, 404)
        self.assertEqual(self.client.get(reverse('practice', args=[legacy.pk])).status_code, 404)
        self.assertRedirects(self.client.get(reverse('choose_problem'), {'problem': 'invalid'}), '/')

    def test_truncated_hint_is_saved_and_labelled(self):
        from .services import HintText
        self.client.force_login(self.owner)
        with patch('coach.workflows.services.generate_hint', return_value=HintText('目前只有部分提示', truncated=True)):
            response = self.client.post(self.url, self.payload)
        record = Submission.objects.get()
        self.assertEqual(record.status, 'partial')
        self.assertEqual(record.answer, '目前只有部分提示')
        self.assertContains(self.client.get(response.url), '以下內容可能不完整')

    @override_settings(HINT_MODE='live')
    def test_length_response_is_not_discarded(self):
        import httpx
        original_client = httpx.Client
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'done': True, 'done_reason': 'length', 'message': {'content': '部分回覆'}}))
        with patch('coach.services.httpx.Client', side_effect=lambda **kw: original_client(transport=transport, **kw)):
            result = generate_hint([], 1)
        self.assertTrue(result.truncated)
        self.assertEqual(result, '部分回覆')

    def test_generation_stop_classification(self):
        from local_model_server import finish_reason
        self.assertEqual(finish_reason([1, 2], 5, [9]), 'stop')
        self.assertEqual(finish_reason([1, 9], 2, [9]), 'stop')
        self.assertEqual(finish_reason([1, 2], 2, [9]), 'length')

    def test_judge_evidence_survives_model_failure(self):
        self.client.force_login(self.owner)
        result = {'status': 'accepted', 'label': '測資通過 1 / 1', 'cases': [{'name': 'sample', 'status': 'accepted', 'label': '通過', 'input': '1', 'expected': '1', 'actual': '1', 'stderr': '', 'seconds': 0.01}]}
        with patch('coach.workflows.judge', return_value=result), patch('coach.workflows.services.generate_hint', side_effect=HintError('模型失敗')):
            data = self.payload | {'run_custom': 'on', 'custom_input': '2', 'custom_expected': '2', 'action': 'test'}
            response = self.client.post(self.url, data)
            response = self.client.post(response.url, data | {'submission_id': str(uuid.uuid4()), 'action': 'ask'})
        record = Submission.objects.first()
        self.assertEqual(record.judge_result['status'], 'accepted')
        self.assertEqual(record.status, 'failed')
        self.assertIn('execution_evidence', record.messages[1]['content'])
        self.assertContains(self.client.get(response.url), '測資通過 1 / 1')

    def test_custom_test_is_passed_to_judge(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge', return_value={'status': 'unavailable', 'label': '未執行', 'cases': []}) as call:
            self.client.post(self.url, self.payload | {'run_custom': 'on', 'custom_input': '2\n3 4', 'custom_expected': '7', 'action': 'test'})
        self.assertEqual(call.call_args.args[1][-1], {'name': '自訂測資', 'input': '2\n3 4', 'expected': '7'})

    @override_settings(HINT_MODE='demo')
    def test_inline_chat_follows_only_its_parent_and_is_idempotent(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, self.payload | {'code': '', 'question': '這段對話的起點'})
        root = Submission.objects.first()
        self.client.post(self.url, self.payload | {'submission_id': str(uuid.uuid4()), 'code': '', 'question': '不應混入的另一個練習'})
        url = reverse('detail', args=[root.pk])
        reply = self.payload | {'submission_id': str(uuid.uuid4()), 'parent_submission': root.pk, 'code': '', 'question': '我認為要讀入兩個數'}
        first = self.client.post(url, reply)
        repeated = self.client.post(url, reply)
        self.assertEqual(first.url, repeated.url)
        self.assertEqual(Submission.objects.count(), 3)
        current = Submission.objects.first()
        self.assertEqual(current.parent_id, root.pk)
        self.assertIn('這段對話的起點', str(current.messages))
        self.assertNotIn('不應混入', str(current.messages))
        page = self.client.get(first.url)
        self.assertContains(page, '我認為要讀入兩個數')
        self.assertContains(page, '詢問助理')
        self.assertNotContains(page, '繼續修改 →')

    def test_cannot_reply_to_another_users_chat(self):
        record = Submission.objects.create(owner=self.other, problem=self.problem, code='', hint_level=1, mode='demo', model='demo')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('detail', args=[record.pk]), self.payload).status_code, 404)

    def test_completion_is_idempotent_reversible_and_per_user(self):
        self.client.force_login(self.owner)
        url = reverse('mark_completion', args=[self.problem.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2):
            self.client.post(url, {'state': 'complete'})
        self.assertEqual(ProblemCompletion.objects.filter(owner=self.owner).count(), 1)
        self.assertContains(self.client.get('/'), '✓ 已完成 · UVa 測試題')
        self.assertEqual(self.client.get('/').context['completed_count'], 1)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/').context['completed_count'], 0)
        self.client.post(url, {'state': 'incomplete'})
        self.assertEqual(ProblemCompletion.objects.filter(owner=self.owner).count(), 1)
        self.client.force_login(self.owner)
        self.client.post(url, {'state': 'incomplete'})
        self.assertEqual(ProblemCompletion.objects.count(), 0)

    def test_completion_validates_state_and_return_record(self):
        self.client.force_login(self.owner)
        record = Submission.objects.create(owner=self.other, problem=self.problem, code='', hint_level=1, mode='demo', model='demo')
        url = reverse('mark_completion', args=[self.problem.pk])
        self.assertEqual(self.client.post(url, {'state': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'state': 'complete', 'return_submission': record.pk}).status_code, 404)
        self.assertFalse(ProblemCompletion.objects.exists())

    @override_settings(HINT_MODE='demo')
    def test_completion_returns_to_same_chat_without_running_services(self):
        self.client.force_login(self.owner)
        record = Submission.objects.create(owner=self.owner, problem=self.problem, code='', hint_level=1, mode='demo', model='demo')
        with patch('coach.workflows.judge') as judge, patch('coach.workflows.services.generate_hint') as model:
            response = self.client.post(reverse('mark_completion', args=[self.problem.pk]), {'state': 'complete', 'return_submission': record.pk})
        self.assertRedirects(response, reverse('detail', args=[record.pk]))
        judge.assert_not_called(); model.assert_not_called()
        self.assertContains(self.client.get(response.url), '取消完成標記')

    def test_workspace_structure_and_local_editor_assets(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        for marker in ['id="panel-problem"', 'id="panel-code"', 'id="panel-chat"', 'id="chat-history"', 'id="ask-assistant"', 'id="run-test"', '/assets/vendor/codemirror/codemirror.js', '/assets/coach/workbench.js']:
            self.assertContains(response, marker)
        asset = self.client.get('/assets/coach/workbench.js')
        self.assertEqual(asset.status_code, 200)
        self.assertIn(self.client.get('/assets/../db.sqlite3').status_code, (400, 404))

    def test_workspace_expands_failed_tests_first(self):
        self.client.force_login(self.owner)
        cases = [{'name': '成功案例', 'status': 'accepted', 'label': '通過', 'input': '1', 'expected': '1', 'actual': '1', 'seconds': .01}, {'name': '失敗案例', 'status': 'wrong_answer', 'label': '答案不符', 'input': '2', 'expected': '2', 'actual': '3', 'seconds': .01}]
        record = Submission.objects.create(owner=self.owner, problem=self.problem, code='', hint_level=1, mode='judge', model='未呼叫模型', action='test', status='tested', judge_result={'status': 'failed', 'label': '測資通過 1 / 2', 'cases': cases})
        page = self.client.get(reverse('detail', args=[record.pk]))
        self.assertEqual(page.context['ordered_cases'][0]['name'], '失敗案例')
        self.assertContains(page, 'test-case failed" open')
        self.assertContains(page, '需要檢查')

    def test_test_action_never_calls_model_and_replays_once(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge', return_value={'status': 'accepted', 'label': '測資通過', 'cases': []}) as judge, patch('coach.workflows.services.generate_hint') as model:
            data = self.payload | {'action': 'test'}
            first = self.client.post(self.url, data)
            self.client.post(self.url, data)
        model.assert_not_called()
        self.assertEqual(judge.call_count, 1)
        record = Submission.objects.get()
        self.assertEqual(record.action, 'test')
        self.assertEqual(record.status, 'tested')
        self.assertEqual(record.answer, '')
        self.assertContains(self.client.get(first.url), '本輪未呼叫模型')

    @override_settings(HINT_MODE='demo')
    def test_ask_does_not_execute_and_reuses_only_matching_snapshot(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge', return_value={'status': 'accepted', 'label': '測資通過', 'cases': []}) as judge:
            tested = self.client.post(self.url, self.payload | {'action': 'test'})
            original = Submission.objects.first()
            ask = self.payload | {'submission_id': str(uuid.uuid4()), 'action': 'ask'}
            response = self.client.post(tested.url, ask)
            cached = Submission.objects.first()
            self.assertEqual(cached.judge_result['reused_from'], original.pk)
            self.assertContains(self.client.get(response.url), '沿用上次測試')
            self.client.post(response.url, ask | {'submission_id': str(uuid.uuid4()), 'code': 'changed code'})
            self.assertEqual(Submission.objects.first().judge_result['status'], 'not_run')
            self.problem.sample_output = 'changed expected'
            self.problem.save()
            self.client.post(tested.url, ask | {'submission_id': str(uuid.uuid4())})
            self.assertEqual(Submission.objects.first().judge_result['status'], 'not_run')
        self.assertEqual(judge.call_count, 1)

    def test_empty_code_test_is_rejected_but_ask_is_allowed(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge') as judge, patch('coach.workflows.services.generate_hint') as model:
            response = self.client.post(self.url, self.payload | {'action': 'test', 'code': '  '})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '執行測試需要程式碼')
        self.assertFalse(Submission.objects.exists())
        judge.assert_not_called(); model.assert_not_called()

    @override_settings(HINT_MODE='demo')
    def test_compile_error_keeps_custom_test_configuration(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge', return_value={'status': 'compile_error', 'label': '編譯錯誤', 'cases': []}):
            data = self.payload | {'action': 'test', 'run_custom': 'on', 'custom_input': 'x', 'custom_expected': 'y'}
            response = self.client.post(self.url, data)
        page = self.client.get(response.url)
        self.assertTrue(page.context['form'].initial['run_custom'])
        with patch('coach.workflows.judge') as judge:
            self.client.post(response.url, data | {'action': 'ask', 'submission_id': str(uuid.uuid4())})
        judge.assert_not_called()
        self.assertEqual(Submission.objects.first().judge_result['status'], 'compile_error')

    @override_settings(HINT_MODE='demo')
    def test_custom_expected_change_invalidates_cache(self):
        self.client.force_login(self.owner)
        with patch('coach.workflows.judge', return_value={'status': 'accepted', 'label': '通過', 'cases': []}):
            tested = self.client.post(self.url, self.payload | {'action': 'test', 'run_custom': 'on', 'custom_input': 'x', 'custom_expected': 'y'})
        self.client.post(tested.url, self.payload | {'submission_id': str(uuid.uuid4()), 'action': 'ask', 'run_custom': 'on', 'custom_input': 'x', 'custom_expected': 'z'})
        self.assertEqual(Submission.objects.first().judge_result['status'], 'not_run')

    def test_history_pruning_keeps_current_question_and_code(self):
        from local_model_server import fit_history
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return {'input_ids': list(range(sum(len(m['content']) for m in messages)))}
        messages = [{'role': 'system', 'content': 'rules'}, {'role': 'user', 'content': 'old' * 20}, {'role': 'assistant', 'content': 'reply' * 20}, {'role': 'user', 'content': 'current full source'}]
        selected, omitted = fit_history(Tokenizer(), messages, maximum=10, context=50)
        self.assertEqual(omitted, 1)
        self.assertEqual(selected, [messages[0], messages[-1]])
        with self.assertRaises(ValueError):
            fit_history(Tokenizer(), [messages[0], messages[-1]], maximum=40, context=50)

class JudgeTests(TestCase):
    def run_result(self, stdout='', returncode=0, timeout=False, output_limit=False):
        return dict(stdout=stdout, stderr='', returncode=returncode, timeout=timeout, output_limit=output_limit, seconds=0.01)

    def test_comparison_statuses(self):
        from .judging import compare_results
        tests = [{'name': 'sample', 'input': '3\n', 'expected': '6\n'}]
        for run, expected in [(self.run_result('6\r\n'), 'accepted'), (self.run_result('7'), 'wrong_answer'), (self.run_result(returncode=1), 'runtime_error'), (self.run_result(timeout=True), 'time_limit'), (self.run_result(output_limit=True), 'output_limit')]:
            result = compare_results({'compile': self.run_result(), 'runs': [run]}, tests)
            self.assertEqual(result['cases'][0]['status'], expected)

    def test_compile_error(self):
        from .judging import compare_results
        result = compare_results({'compile': self.run_result(returncode=1), 'runs': []}, [])
        self.assertEqual(result['status'], 'compile_error')

    def test_missing_docker_does_not_execute_host_code(self):
        from .judging import judge
        with patch('coach.judging.shutil.which', return_value=None), patch('coach.judging.subprocess.run') as run:
            self.assertEqual(judge('any code', [])['status'], 'unavailable')
            run.assert_not_called()

    def test_sandbox_flags_and_cleanup(self):
        import json
        from subprocess import CompletedProcess
        from .judging import judge
        tests = [{'name': 'sample', 'input': '1', 'expected': '1'}]
        output = {'compile': self.run_result(), 'runs': [self.run_result('1')]}
        with patch('coach.judging.shutil.which', return_value='docker'), patch('coach.judging.subprocess.run', return_value=CompletedProcess([], 0, stdout=json.dumps(output))) as run:
            self.assertEqual(judge('code', tests)['status'], 'accepted')
        args = run.call_args_list[0].args[0]
        self.assertIn('--read-only', args)
        self.assertEqual(args[args.index('--network') + 1], 'none')
        self.assertEqual(run.call_args_list[-1].args[0][:3], ['docker', 'rm', '-f'])

class TrainingDataTests(TestCase):
    def test_ten_problem_dataset_split_and_executable_audit(self):
        import json
        from pathlib import Path
        from django.conf import settings
        folder = Path(settings.BASE_DIR) / 'training/data'
        train = [json.loads(x) for x in (folder / 'train.jsonl').read_text(encoding='utf-8').splitlines()]
        evaluation = [json.loads(x) for x in (folder / 'eval.jsonl').read_text(encoding='utf-8').splitlines()]
        audit = [json.loads(x) for x in (folder / 'judge_audit.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(train), 90)
        self.assertEqual(len(evaluation), 30)
        self.assertEqual(len({r['problem_id'] for r in train}), 10)
        self.assertFalse({r['id'] for r in train} & {r['id'] for r in evaluation})
        self.assertTrue(all(r['variant'] == 'bug3' for r in evaluation))
        self.assertTrue(all(r['variant'] != 'bug3' for r in train))
        self.assertEqual(len(audit), 40)
        for record in audit:
            self.assertEqual(record['judge']['status'], 'accepted' if record['variant'] == 'correct' else 'failed')
        self.assertTrue(all('int main' not in r['messages'][-1]['content'] for r in train + evaluation))


class Cpe49CatalogTests(TestCase):
    def catalog(self):
        import json
        from django.conf import settings
        return json.loads((settings.BASE_DIR / 'data/cpe49.json').read_text(encoding='utf-8'))

    def seed(self, command='seed_cpe49'):
        from io import StringIO
        from django.core.management import call_command
        call_command(command, stdout=StringIO())

    def test_catalog_is_complete_and_contains_no_reference_answers(self):
        expected = {100,118,272,299,490,948,10008,10019,10035,10038,10041,10050,10055,10056,10057,10062,10071,10093,10101,10170,10189,10190,10193,10221,10222,10226,10235,10242,10252,10268,10409,10415,10420,10642,10783,10812,10908,10922,10929,10931,11005,11063,11150,11321,11332,11349,11417,11461,12019}
        catalog = self.catalog()
        self.assertEqual(len(catalog), 49)
        self.assertEqual({p['uva'] for p in catalog}, expected)
        for p in catalog:
            self.assertNotIn('code', p)
            self.assertTrue(p['statement'] and p['source'].startswith('https://onlinejudge.org/'))
            self.assertGreaterEqual(len(p['tests']), 2)
            for case in p['tests']:
                self.assertIsInstance(case['input'], str)
                self.assertIsInstance(case['expected'], str)
                self.assertIn(case.get('comparison', 'exact'), ('exact', 'line_rstrip', 'float_1e-6'))

    def test_upgrade_from_ten_is_idempotent_and_keeps_student_records(self):
        self.seed('seed_cpe10')
        original = Problem.objects.order_by('pk').first()
        owner = get_user_model().objects.create_user('catalog-student')
        completion = ProblemCompletion.objects.create(owner=owner, problem=original)
        record = Submission.objects.create(owner=owner, problem=original, code='student code', hint_level=1, mode='demo', model='demo')
        original.statement = '教師自行調整的題意'
        original.save()
        self.seed()
        self.seed()
        self.assertEqual(Problem.objects.filter(category__startswith='CPE ').count(), 49)
        original.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(original.statement, '教師自行調整的題意')
        self.assertEqual(record.problem_id, original.pk)
        self.assertTrue(ProblemCompletion.objects.filter(pk=completion.pk).exists())
        self.client.force_login(owner)
        response = self.client.get('/')
        self.assertEqual(response.context['problem_count'], 49)
        self.assertEqual(response.context['completed_count'], 1)
        from django.utils.html import escape
        for problem in Problem.objects.all():
            self.assertContains(response, escape(problem.title))

    def test_special_comparison_survives_database_and_reaches_judge(self):
        from .workflows import test_inputs, test_fingerprint
        self.seed()
        for number, mode in [(490, 'line_rstrip'), (10221, 'float_1e-6')]:
            problem = Problem.objects.get(title__startswith=f'UVa {number} ·')
            self.assertEqual(problem.output_comparison, mode)
            tests = test_inputs(problem, {'run_custom': True, 'custom_input': 'custom', 'custom_expected': 'expected'})
            self.assertTrue(all(c['comparison'] == mode for c in tests))
            self.assertNotEqual(test_fingerprint('code', tests), test_fingerprint('code', [dict(c, comparison='exact') for c in tests]))

    def test_comparison_modes_accept_formatting_and_reject_real_errors(self):
        from .judging import matches
        self.assertTrue(matches('xa  \n b \n c\n', 'xa\n b\n c\n', 'line_rstrip'))
        self.assertFalse(matches('xa\nb\nc\n', 'xa\n b\n c\n', 'line_rstrip'))
        self.assertFalse(matches('a \nb', 'a\nb'))
        self.assertTrue(matches('7330.382857 7000', '7330.382858 7000.000000', 'float_1e-6'))
        for bad in ['7330.39 7000', '7330.382858', 'nan 7000', 'inf 7000', 'text 7000']:
            self.assertFalse(matches(bad, '7330.382858 7000', 'float_1e-6'))
