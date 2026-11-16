import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, override_settings
from .learning_context import vito_context
from .cpp_knowledge import retrieve,conflict
from .services import build_messages,generate_hint
from .model_prompt import readable_messages
from .reply_quality import quality_issue


@override_settings(HINT_MODE='live')
class LearningContextTests(SimpleTestCase):
    problem=SimpleNamespace(title="UVa 10041 · Vito's family",statement='找出親戚距離總和最小的住址',sample_input='1\n3 1 2 100\n',sample_output='99\n',test_cases=[])

    def test_concept_transport_excludes_unrelated_problem_and_stale_history(self):
        messages=build_messages(self.problem,'int a=5,b=2;double result=a/b;',
            '請解釋整數除法為什麼沒有小數，不要改程式。',
            history=[{'question':'之前那題呢','hint':'錯誤的二維地址說法','code':''}])
        payload=json.loads(messages[-1]['content'])
        transport='\n'.join(m['content'] for m in readable_messages(messages))
        self.assertEqual(payload['question_kind'],'cpp_concept')
        self.assertNotIn('verified_topic_notes',payload)
        self.assertNotIn('親戚',transport)
        self.assertNotIn('二維',transport)
        self.assertIn('int a=5,b=2;',transport)
        self.assertFalse(payload['guard_local_edits'])

    def test_actual_edit_still_uses_revision_and_does_not_become_concept(self):
        payload=json.loads(build_messages(self.problem,'int main(){return 0;}','請修改程式，解決整數除法問題。')[-1]['content'])
        self.assertEqual(payload['question_kind'],'problem')
        self.assertTrue(payload['revision_request'])

    def test_follow_up_recomputes_cost_using_student_address_list(self):
        history=[{'question':'地址是1、2、100，住在34的總距離是多少？','hint':'錯誤：地址是34、9、7'}]
        state,calculation=vito_context('那住在2的總和是多少？',history)
        self.assertEqual(state['addresses'],[1,2,100])
        self.assertEqual(calculation['home'],2)
        self.assertEqual(calculation['distance_sum'],99)
        self.assertEqual(calculation['address_source'],'previous_user_message')
        messages=build_messages(self.problem,'','那住在2的總和是多少？',history=history)
        self.assertEqual(quality_issue('住在2的總和是131。',messages),'calculation_conflict')
        self.assertIsNone(quality_issue('住在2的總和是1+0+98=99。',messages))

    def test_state_survives_model_history_limit_without_using_assistant_numbers(self):
        history=[{'question':'地址是1、2、100','hint':'住在34'}]+[{'question':'了解了','hint':'例子888'}]*8
        payload=json.loads(build_messages(self.problem,'','住在2的總和是多少？',history=history)[-1]['content'])
        self.assertEqual(payload['verified_calculation']['distance_sum'],99)

    def test_new_list_and_reset_do_not_reuse_old_addresses(self):
        history=[{'question':'地址是1、2、100','hint':'之前答案'}]
        self.assertEqual(vito_context('地址改成3、8、20，住在8呢？',history)[1]['distance_sum'],17)
        for q in ['地址是0、2、100，住在2呢？','地址改成7，住在2呢？','換一個例子，住在2呢？']:
            self.assertEqual(vito_context(q,history),(None,None))
        self.assertEqual(vito_context('住在2呢？',[*history,{'question':'重新開始','hint':''}]),(None,None))

    def test_topic_boundary_has_no_inherited_calculation(self):
        other=SimpleNamespace(title='UVa 10055',statement='差值')
        payload=json.loads(build_messages(other,'','住在2呢？',history=[{'question':'地址是1、2、100','hint':''}])[-1]['content'])
        self.assertNotIn('verified_calculation',payload)

    def test_ablation_does_not_silently_add_calculation_tools(self):
        payload=json.loads(build_messages(self.problem,'','地址是1、2、100，住在2的總和是多少？',include_topic_notes=False)[-1]['content'])
        self.assertNotIn('verified_calculation',payload)

    def test_selected_cards_do_not_follow_irrelevant_code_names(self):
        cards=retrieve('解釋區塊內外的作用域','double average;long long area;')
        self.assertEqual([c['id'] for c in cards],['scope_lifetime'])

    def test_average_question_without_literal_type_name_is_a_concept(self):
        messages=build_messages(self.problem,'int total=5,count=2;double average=total/count;',
            '請解釋 average 為什麼是 2 而不是 2.5，並提供必要的 C++ 局部示範。不要修改我的程式。')
        payload=json.loads(messages[-1]['content'])
        self.assertEqual(payload['question_kind'],'cpp_concept')
        self.assertEqual([c['id'] for c in payload['cpp_knowledge']],['integer_division'])

    def test_truncated_concept_is_not_delivered_as_complete(self):
        from .services import HintText
        messages=build_messages(self.problem,'','整數除法5/2是什麼？')
        with patch('coach.services._generate_once',return_value=HintText('先做整數除法，5/2=2，然後',truncated=True)):
            reply=generate_hint(messages)
        self.assertEqual(reply.source,'knowledge')

    def test_known_semantic_failures_are_detected(self):
        self.assertTrue(conflict('整數5/2=2.5，因為左側是double。',retrieve('整數除法5/2')))
        self.assertFalse(conflict('先做整數除法，5/2=2，然後轉型為double。',retrieve('整數除法5/2')))
        self.assertTrue(conflict('(long long)(x*y)可以避免溢位。',retrieve('乘法溢位')))
        self.assertFalse(conflict('必須在乘法前提升型別，例如1LL*x*y。',retrieve('乘法溢位')))
        self.assertTrue(conflict('生命週期結束，複製到外部也不能安全使用。',retrieve('區塊內外的生命週期')))
        self.assertTrue(conflict('生命週期僅在區塊內，即使大括號外也能使用。',retrieve('區塊內外的生命週期')))
        self.assertTrue(conflict('參考不延長生命週期；把這個參考傳給外部函式，因此是安全的。',retrieve('區塊內外的生命週期')))
        self.assertFalse(conflict('在物件生命週期內，使用這個參考是安全的。',retrieve('區塊內外的生命週期')))
        self.assertTrue(conflict('乘法前轉型才對。但(long long)(x*y)可以解決溢位。',retrieve('乘法溢位')))

    def test_transfer_failures_do_not_pass_on_a_correct_number_alone(self):
        cards=retrieve('解釋整數除法-7/2')
        self.assertTrue(conflict('整數除法向下取整，也就是向零截斷，結果為-3。',cards))
        self.assertTrue(conflict('先整數除法得到-3，double型別本身沒有儲存小數部分。',cards))
        self.assertFalse(conflict('整數除法向零截斷，不是向下取整，-7/2得到-3。',cards))
        cards=retrieve('區塊生命週期','int saved=0;if(true){int local=7;saved=local;}')
        self.assertTrue(conflict('local生命週期結束，saved也會失去local的值，變成0。',cards))
        self.assertFalse(conflict('local生命週期結束，saved不會失去複製的值。',cards))

    def test_failed_concept_retries_once_then_labels_project_knowledge(self):
        messages=build_messages(self.problem,'','整數除法5/2是什麼？')
        with patch('coach.services._generate_once',return_value='5/2=2.5，因為是double。') as generate:
            reply=generate_hint(messages)
        self.assertEqual(generate.call_count,2)
        self.assertEqual(reply.source,'knowledge')
        self.assertIn('系統 C++ 知識核對',reply)
        self.assertEqual(len(reply.quality_audit['candidates']),2)


@override_settings(HINT_MODE='live')
class KnowledgeDeliveryTests(TestCase):
    def test_knowledge_source_and_rejected_candidates_are_visible_and_persisted(self):
        import uuid
        from django.contrib.auth import get_user_model
        from .models import Problem
        from .workflows import submit
        user=get_user_model().objects.create_user('knowledge-learner')
        problem=Problem.objects.create(title='UVa 知識來源測試',category='CPE 一星',statement='測試',sample_input='1',sample_output='1')
        with patch('coach.services._generate_once',return_value='5/2=2.5，因為是double。'):
            record=submit(user,problem,{'submission_id':uuid.uuid4(),'code':'','question':'整數除法5/2是什麼？','run_custom':False,'custom_input':'','custom_expected':''})
        self.assertEqual(record.mode,'knowledge')
        self.assertEqual(record.status,'done')
        self.assertEqual(len(record.messages[-1]['quality_fallback']['candidates']),2)
        self.client.force_login(user)
        self.assertContains(self.client.get(f'/submission/{record.pk}/'),'C++ 知識核對')
