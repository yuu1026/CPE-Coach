import copy
import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth import get_user_model
from . import services
from .lesson_catalog import CHECKS, SCAFFOLDS, statements, check_for
from .guided_learning import plan, vito_step, hashmat_step, answer_values
from .lesson_delivery import deliver, independent_tests, LessonError
from .local_revision import apply_edits
from .models import Problem, Submission
from .workflows import submit
import uuid


def payload(topic=10041,code='',question='我沒有想法，請引導我。',history=()):
    problem=SimpleNamespace(title=f'UVa {topic} · Lesson',statement=statements()[topic],sample_input='1\n3 1 2 100\n',sample_output='99\n',test_cases=[],output_comparison='exact')
    history=[dict(question='',hint='',**h) for h in history]
    return json.loads(services.build_messages(problem,code,question,history=history)[-1]['content'])


class LessonRoutingTests(SimpleTestCase):
    def test_catalog_statement_match_and_explicit_intent_are_required(self):
        self.assertIn('guided_lesson',payload())
        data=payload(question='你覺得呢？')
        self.assertNotIn('guided_lesson',data)
        self.assertIsNone(plan(dict(data,question='請引導',problem='changed statement'),[]))

    def test_explicit_solution_stays_available_and_does_not_start_a_check(self):
        self.assertNotIn('guided_lesson',payload(question='給我完整答案'))

    def test_i_understand_does_not_pass_a_pending_check(self):
        state=payload()['guided_lesson']['state']
        data=payload(question='我懂了，下一步',history=[{'lesson_record':state}])
        self.assertEqual(data['guided_lesson']['kind'],'check')
        self.assertEqual(data['guided_lesson']['state']['passed'],[])

    def test_wrong_answer_gets_new_question_and_is_not_marked_passed(self):
        state=payload()['guided_lesson']['state']
        first=payload(question='4',history=[{'lesson_record':state}])['guided_lesson']
        self.assertFalse(first['correct']);self.assertEqual(first['state']['passed'],[])
        self.assertEqual(first['state']['pending'],'vito_distance_retry')
        second=payload(question='3',history=[{'lesson_record':first['state']}])['guided_lesson']
        self.assertFalse(second['correct'])
        self.assertNotEqual(check_for(second['state'],'vito_distance_retry')['expected'],[7])

    def test_numeric_answer_is_not_taken_from_an_unrelated_test_question(self):
        self.assertIsNone(answer_values('測試只過1/3，該怎麼改？'))
        self.assertEqual(answer_values('0+1+2=3，下一步'),[3])
        self.assertEqual(answer_values('1、4、9，下一步'),[1,4,9])

    def test_specific_fact_question_preserves_pending_check(self):
        state=payload()['guided_lesson']['state']
        action=payload(question='為什麼不能用平均地址？',history=[{'lesson_record':state}])['guided_lesson']
        self.assertEqual(action['kind'],'fact');self.assertEqual(action['state']['pending'],'vito_start')

    def test_provided_scaffold_is_not_restarted_when_editor_is_still_blank(self):
        state=payload()['guided_lesson']['state'];state['pending']=None;state['scaffold_sha256']='provided'
        action=payload(question='下一步',history=[{'lesson_record':state}])['guided_lesson']
        self.assertEqual(action['kind'],'await_code')

    def test_vito_type_question_does_not_inherit_hashmat_input_bound(self):
        state=payload()['guided_lesson']['state']
        data=payload(question='為什麼用 long long？',history=[{'lesson_record':state}])
        self.assertNotIn('guided_lesson',data)

    def test_editing_after_completion_invalidates_completed_state(self):
        state=payload()['guided_lesson']['state']
        state.update(completion='tests_and_checks_complete',pending=None,validation={'code_sha256':'old-code'})
        action=payload(code=SCAFFOLDS[10041],question='下一步',history=[{'lesson_record':state}])['guided_lesson']
        self.assertNotIn('completion',action['state'])

    def test_reset_clears_checks_without_deleting_the_conversation(self):
        state=payload()['guided_lesson']['state'];state['passed']=['distance'];state['scaffold_sha256']='old'
        action=payload(question='重新開始',history=[{'lesson_record':state}])['guided_lesson']
        self.assertEqual(action['kind'],'start');self.assertEqual(action['state']['passed'],[])

    def test_exit_stays_in_effect_until_explicit_resume(self):
        state=payload()['guided_lesson']['state']
        stopped=payload(question='退出引導',history=[{'lesson_record':state}])['guided_lesson']
        self.assertTrue(stopped['state']['disabled'])
        normal=payload(question='請解釋 cin',history=[{'lesson_record':stopped['state']}])
        self.assertNotIn('guided_lesson',normal)
        resumed=payload(question='恢復引導',history=[{'lesson_record':stopped['state']}])
        self.assertEqual(resumed['guided_lesson']['kind'],'start')

    def test_signed_type_misconception_is_answered_by_fact_in_active_hashmat(self):
        state=payload(topic=10055)['guided_lesson']['state']
        action=payload(topic=10055,question='long long不能表示負數嗎？',history=[{'lesson_record':state}])['guided_lesson']
        self.assertEqual(action['kind'],'fact');self.assertEqual(action['fact'],'width')


class SourceStepTests(SimpleTestCase):
    def apply(self,code,step):
        return apply_edits(code,[e for e in step['edits'] if not ('header' in e and '#include <'+e['header']+'>' in code)])

    def test_blank_vito_path_advances_without_replacing_the_program(self):
        code=SCAFFOLDS[10041]
        kinds=[]
        for expected in ['sort','median','distance','output']:
            step=vito_step(code);self.assertEqual(step['step'],expected)
            if expected=='sort':self.assertNotIn('修正平均',step['reason'])
            kinds.append(step['step']);code=self.apply(code,step)
        self.assertEqual(vito_step(code)['step'],'test')
        self.assertEqual(code.count('int main'),1)
        self.assertIn('cin >> houses[i]',code)

    def test_renamed_average_program_gets_sort_then_local_median_replacement(self):
        source=SCAFFOLDS[10041].replace('houses','places').replace('count','people')
        source=source.replace('// TODO: 在讀完這組地址後，逐步完成核心運算與輸出。','int sum=0;for(int x:places)sum+=x;int spot=sum/people;int total=0;for(int x:places)total+=abs(x-spot);cout<<total<<"\\n";')
        step=vito_step(source);self.assertEqual(step['step'],'sort')
        candidate=self.apply(source,step)
        step=vito_step(candidate);self.assertEqual(step['step'],'median')
        candidate=self.apply(candidate,step)
        self.assertIn('spot=places[people / 2]',candidate)
        self.assertNotIn('int home',candidate)
        self.assertEqual(vito_step(candidate)['step'],'test')

    def test_raw_strings_multiple_vectors_and_unusual_control_flow_are_not_guessed(self):
        for source in [SCAFFOLDS[10041]+'\nauto raw=R"(text)";',
                       SCAFFOLDS[10041].replace('vector<int> houses(count);','vector<int> houses(count);vector<int> other(count);'),
                       SCAFFOLDS[10041].replace('cin >> houses[i];','if(i)break;cin >> houses[i];')]:
            self.assertIsNone(vito_step(source))

    def test_hashmat_preserves_names_and_uses_portable_header(self):
        code='#include <iostream>\nusing namespace std;int main(){long long left,right;while(cin>>left>>right){cout<<left-right<<endl;}}'
        step=hashmat_step(code)
        self.assertEqual(step['step'],'difference')
        candidate=self.apply(code,step)
        self.assertIn('std::abs(left - right)',candidate)
        self.assertIn('#include <cstdlib>',candidate)
        self.assertEqual(hashmat_step(candidate)['step'],'test')


class DeliveryContractTests(SimpleTestCase):
    def result(self,status='accepted'):
        return {'status':status,'label':status,'cases':[{'name':'test','input':'','expected':'','actual':'','status':'accepted' if status=='accepted' else 'wrong_answer'}]}

    def test_fallback_is_disclosed_verified_and_does_not_claim_model_success(self):
        data=payload(code=SCAFFOLDS[10041],question='下一步請教我')
        with patch('coach.lesson_delivery.judge',side_effect=[self.result('failed'),self.result('failed'),self.result()]) as judge:
            reply=deliver(data['guided_lesson'],data,lambda *a:'invalid JSON')
        self.assertEqual(reply['source'],'lesson_fallback')
        self.assertIn('不是模型獨立',reply['text'])
        self.assertEqual(judge.call_count,3)
        self.assertIn('std::sort',reply['revision_check']['candidate_code'])
        self.assertEqual(reply['state']['pending'],'vito_order')

    def test_candidate_regression_never_yields_applyable_code(self):
        data=payload(code=SCAFFOLDS[10041],question='下一步')
        with patch('coach.lesson_delivery.judge',side_effect=[self.result(),self.result('failed')]):
            with self.assertRaises(LessonError):deliver(data['guided_lesson'],data,lambda *a:'invalid')

    def test_incorrect_model_explanation_is_replaced_by_authored_fact_not_published(self):
        data=payload(code=SCAFFOLDS[10041],question='下一步')
        step=data['guided_lesson']['step']
        edits=[e for e in step['edits'] if 'header' not in e]
        proposal=json.dumps({'explanation':'long long不能表示負數。','edits':edits})
        with patch('coach.lesson_delivery.judge',side_effect=[self.result('failed'),self.result('failed'),self.result()]):
            reply=deliver(data['guided_lesson'],data,lambda *a:proposal)
        self.assertEqual(reply['source'],'lesson_model')
        self.assertNotIn('不能表示負數',reply['text'])
        self.assertIn('不能表示負數',json.loads(reply['state']['proposal_audit']['raw_candidate'])['explanation'])

    def test_model_comments_cannot_smuggle_unverified_teaching_into_applyable_code(self):
        data=payload(code=SCAFFOLDS[10041],question='下一步')
        edit=copy.deepcopy(next(e for e in data['guided_lesson']['step']['edits'] if 'header' not in e))
        edit['after']+='\n// long long不能表示負數。'
        proposal=json.dumps({'explanation':'這是錯誤的註解測試。','edits':[edit]})
        with patch('coach.lesson_delivery.judge',side_effect=[self.result('failed'),self.result('failed'),self.result()]):
            reply=deliver(data['guided_lesson'],data,lambda *a:proposal)
        self.assertEqual(reply['source'],'lesson_fallback')
        self.assertNotIn('不能表示負數',reply['revision_check']['candidate_code'])

    def test_unavailable_docker_cannot_become_a_successful_lesson(self):
        data=payload(question='給我骨架')
        with patch('coach.lesson_delivery.judge',return_value={'status':'unavailable'}):
            with self.assertRaises(LessonError):deliver(data['guided_lesson'],data,lambda *a:None)

    def test_scaffold_needs_compile_and_keeps_core_blank(self):
        data=payload(question='給我輸入骨架')
        with patch('coach.lesson_delivery.judge',return_value=self.result()) as judge:
            reply=deliver(data['guided_lesson'],data,lambda *a:None)
        self.assertEqual(judge.call_args.args[1],[])
        self.assertIn('TODO',reply['scaffold_code'])
        self.assertNotIn('cout',reply['scaffold_code'])

    def test_final_completion_requires_actual_tests_and_checks_not_just_correct_code(self):
        code=SCAFFOLDS[10041]
        for _ in range(4):
            step=vito_step(code)
            code=apply_edits(code,[e for e in step['edits'] if not ('header' in e and '#include <'+e['header']+'>' in code)])
        data=payload(code=code,question='下一步')
        with patch('coach.lesson_delivery.judge',return_value=self.result()):
            reply=deliver(data['guided_lesson'],data,lambda *a:None)
        self.assertNotIn('completion',reply['state'])
        self.assertEqual(reply['state']['pending'],'vito_order')


@override_settings(HINT_MODE='live')
class LessonPersistenceTests(TestCase):
    def test_graded_state_survives_a_real_submission_branch(self):
        owner=get_user_model().objects.create_user('guided-student')
        problem=Problem.objects.create(title='UVa 10041 · Vito',statement=statements()[10041],sample_input='1\n3 1 2 100\n',sample_output='99\n',category='CPE 一星')
        def data(question):return dict(action='ask',submission_id=uuid.uuid4(),code='',question=question,run_custom=False,custom_input='',custom_expected='')
        first=submit(owner,problem,data('我沒有想法，請引導我'))
        self.assertEqual(first.mode,'guided')
        second=submit(owner,problem,data('4'),first)
        record=second.messages[-1]['lesson_record']
        self.assertEqual(record['pending'],'vito_distance_retry')
        self.assertFalse(record['checks'][-1]['correct'])
        self.assertEqual(record['passed'],[])
