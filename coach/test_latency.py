import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import uuid
import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from . import performance, services, jobs
from .models import Problem, Submission
from .model_prompt import readable_messages
from .workflows import test_fingerprint
from .local_revision import generate_revision


class MeasurementTests(SimpleTestCase):
    def test_nested_calls_share_measurement_but_requests_are_isolated(self):
        snapshots=[]
        with performance.measure(lambda value:snapshots.append(value)) as outer:
            with performance.measure() as inner:
                self.assertIs(outer,inner)
                with performance.span('candidate'): pass
                performance.model_call({'seconds':1})
        self.assertEqual(len(snapshots[-1]['model_calls']),1)
        with performance.measure() as fresh:
            self.assertEqual(fresh.data['model_calls'],[])


@override_settings(HINT_MODE='live', MODEL_URL='http://127.0.0.1:11436')
class StreamTransportTests(SimpleTestCase):
    def run_response(self, response):
        original=httpx.Client
        with patch('coach.services.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(lambda request:response),**kw)):
            with performance.measure() as measurement:
                reply=services._generate_once([{'role':'system','content':'繁體中文'},{'role':'user','content':'{}'}])
            return reply,measurement.snapshot()

    def test_stream_is_accumulated_but_progress_contains_no_candidate_text(self):
        lines=[{'done':False,'message':{'content':'絕對值是'}},
               {'done':False,'message':{'content':'到零的距離。'}},
               {'done':True,'done_reason':'stop','eval_count':12,'prompt_eval_count':20}]
        response=httpx.Response(200,headers={'Content-Type':'application/x-ndjson'},text='\n'.join(map(json.dumps,lines)))
        reply,metrics=self.run_response(response)
        self.assertEqual(reply,'絕對值是到零的距離。')
        self.assertEqual(metrics['generated_chars'],len(reply))
        self.assertEqual(metrics['model_calls'][0]['eval_count'],12)
        self.assertNotIn('絕對值',json.dumps(metrics,ensure_ascii=False))

    def test_stream_without_final_marker_never_delivers_partial_answer(self):
        with self.assertRaisesMessage(services.HintError,'串流中斷'):
            self.run_response(httpx.Response(200,headers={'Content-Type':'application/x-ndjson'},text=json.dumps({'message':{'content':'部分回覆'}})))

    def test_old_json_gateway_remains_compatible(self):
        reply,_=self.run_response(httpx.Response(200,json={'done':True,'message':{'content':'這是完整的繁體中文說明。'}}))
        self.assertIn('完整',reply)

    def test_busy_model_has_actionable_error_without_retry(self):
        with self.assertRaisesMessage(services.HintError,'處理其他問題'):
            self.run_response(httpx.Response(429,json={'error':'busy'}))

    def test_two_truncated_candidates_are_not_delivered_as_an_answer(self):
        messages=[{'role':'system','content':'規則'}, {'role':'user','content':json.dumps({'response_mode':'tutor','code':'','question':'請解釋'})}]
        with patch('coach.services._generate_once',return_value=services.HintText('沒有結束的提示',truncated=True)) as generate:
            with self.assertRaises(services.HintError): services.generate_hint(messages)
        self.assertEqual(generate.call_count,2)

    def test_good_first_reply_does_not_trigger_an_extra_generation(self):
        messages=[{'role':'system','content':'規則'}, {'role':'user','content':json.dumps({'response_mode':'tutor','code':'','question':'請解釋'})}]
        with patch('coach.services._generate_once',return_value=services.HintText('絕對值是到零的距離，所以不會是負數。')) as generate:
            reply=services.generate_hint(messages)
        generate.assert_called_once(); self.assertFalse(reply.truncated)


class PromptBudgetTests(SimpleTestCase):
    def test_transport_keeps_recent_dialogue_and_full_current_code_not_old_copies(self):
        problem=SimpleNamespace(title='C++ 練習',statement='計算差值')
        history=[{'question':f'舊問題{i}','hint':f'舊回答{i}','code':'int old;'} for i in range(6)]
        code='int current = 1;\n'*300
        messages=services.build_messages(problem,code,'請解釋目前宣告的意思',history=history)
        transport=readable_messages(messages)
        text='\n'.join(m['content'] for m in transport)
        self.assertIn('舊問題5',text);self.assertIn('舊問題4',text)
        self.assertNotIn('舊問題0',text)
        self.assertEqual(text.count('int current = 1;'),300)
        self.assertEqual(len(messages),14)  # audit history remains intact


@override_settings(HINT_MODE='live')
class BaselineReuseTests(SimpleTestCase):
    def fixture(self, matching=True):
        code='int main(){int x=1;return x;}'
        tests=[{'name':'one','input':'','expected':'','comparison':'exact'}]
        old={'status':'failed','label':'0/1','cases':[{'name':'one','status':'wrong_answer','input':'','expected':'','actual':'wrong'}],
             'fingerprint':test_fingerprint(code if matching else 'changed',tests)}
        payload={'code':code,'question':'請修正','revision_tests':tests,'verified_baseline':old}
        messages=[{'role':'system','content':'rules'},{'role':'user','content':json.dumps(payload)}]
        result={'status':'accepted','label':'1/1','cases':[{'name':'one','status':'accepted'}]}
        plan=json.dumps({'explanation':'只更正目前的回傳值。','edits':[{'before':'return x;','after':'return 0;'}]})
        return messages,result,plan,old

    def test_matching_baseline_is_reused_but_candidate_is_still_judged(self):
        messages,result,plan,_=self.fixture()
        with patch('coach.local_revision.judge',return_value=result) as judge:
            text,check=generate_revision(messages,None,lambda *a:plan,lambda x:x)
        judge.assert_called_once()
        self.assertIn('return 0;',judge.call_args.args[0])
        self.assertEqual(check['baseline']['status'],'failed')

    def test_changed_fingerprint_requires_real_baseline_judge(self):
        messages,result,plan,old=self.fixture(False)
        with patch('coach.local_revision.judge',side_effect=[old,result]) as judge:
            generate_revision(messages,None,lambda *a:plan,lambda x:x)
        self.assertEqual(judge.call_count,2)


class AsyncReplyTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user('latency-owner')
        self.other=get_user_model().objects.create_user('latency-other')
        self.problem=Problem.objects.create(title='UVa 999 · Test',statement='test',sample_input='',sample_output='',category='CPE 一星')
        self.client.force_login(self.owner)
        self.payload={'submission_id':str(uuid.uuid4()),'code':'','question':'怎麼開始'}

    def record(self,owner=None,**fields):
        return Submission.objects.create(owner=owner or self.owner,problem=self.problem,code='',mode='live',model='gemma',**fields)

    def test_ack_is_fast_and_duplicate_token_does_not_start_second_job(self):
        with patch('coach.jobs._slot') as gate, patch('coach.jobs.threading.Thread') as worker:
            gate.acquire.return_value=True
            first=self.client.post(reverse('ask_program',args=[self.problem.pk]),self.payload)
            second=self.client.post(reverse('ask_program',args=[self.problem.pk]),self.payload)
        self.assertEqual(first.status_code,202);self.assertEqual(second.status_code,202)
        self.assertEqual(first.json()['record'],second.json()['record'])
        worker.return_value.start.assert_called_once()
        self.assertEqual(Submission.objects.count(),1)

    def test_busy_worker_rejects_without_creating_record(self):
        with patch('coach.jobs._slot') as gate:
            gate.acquire.return_value=False
            response=self.client.post(reverse('ask_program',args=[self.problem.pk]),self.payload)
        self.assertEqual(response.status_code,429)
        self.assertEqual(Submission.objects.count(),0)

    def test_other_users_parent_or_progress_is_never_exposed(self):
        record=self.record(self.other)
        response=self.client.post(reverse('ask_program',args=[self.problem.pk]),self.payload|{'parent_submission':record.pk})
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get(reverse('reply_progress',args=[record.pk])).status_code,404)

    def test_progress_exposes_counts_not_unverified_code_or_prose(self):
        record=self.record(performance={'phase':'generation','generated_chars':12,'candidate':'secret code'})
        data=self.client.get(reverse('reply_progress',args=[record.pk])).json()
        self.assertEqual(data['generated_chars'],12)
        self.assertNotIn('secret',json.dumps(data))

    def test_async_post_requires_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('ask_program',args=[self.problem.pk]),self.payload).status_code,403)

    def test_removed_chat_is_not_recreated_by_background_completion(self):
        record=self.record()
        data=dict(code='',question='開始',run_custom=False,custom_input='',custom_expected='')
        from .workflows import complete
        with patch('coach.workflows.services.generate_hint',side_effect=lambda *a:(Submission.objects.filter(pk=record.pk).delete() and '回覆')):
            complete(record,data)
        self.assertFalse(Submission.objects.filter(pk=record.pk).exists())
