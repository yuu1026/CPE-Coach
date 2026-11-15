from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from .services import build_messages,generate_hint,HintError
from .reply_quality import quality_issue
from .model_prompt import readable_messages

@override_settings(HINT_MODE='live')
class TutoringPolicyTests(SimpleTestCase):
    def test_incomplete_draft_and_result_confirmation_have_different_tasks(self):
        problem=SimpleNamespace(statement='一維地址練習')
        next_step=build_messages(problem,'vector<int> addresses(relatives);','已讀好，下一步如何寫？',3,[])
        self.assertIn('任務是教學生新增一小段',readable_messages(next_step)[0]['content'])
        history=[{'question':'舊版有錯嗎？','hint':'舊版 home 存在問題。','code':'int home=0;'}]
        review=build_messages(problem,'int home=2;','現在有已確認的錯誤嗎？',2,history,{'status':'accepted','label':'測資通過','cases':[]})
        rendered=readable_messages(review)
        self.assertEqual(len(rendered),2)
        self.assertNotIn('舊版 home 存在問題','\n'.join(m['content'] for m in rendered))
        self.assertIn('只確認目前測試結果',rendered[0]['content'])

    def test_vito_calculator_separates_right_arithmetic_from_wrong_strategy(self):
        from .teaching_tools import vito_calculation
        calculation=vito_calculation('地址 1、2、100，我算 home 是 34、距離總和 131，對嗎？')
        self.assertTrue(calculation['claimed_sum_correct'])
        self.assertEqual(calculation['minimum_sum'],99)
        self.assertEqual(calculation['optimal_interval'],[2,2])
        self.assertEqual(vito_calculation('地址改成 1、2、1000，home=2，總距離應是多少？')['distance_sum'],999)
        self.assertEqual(vito_calculation('4 個地址 1、2、100、101，要怎麼選？')['optimal_interval'],[2,100])
        self.assertIsNone(vito_calculation('地址 1、2、-3，住在 2。'))
        self.assertIsNone(vito_calculation('地址 1、2、100，home=2 或 home=34？'))
        from .reply_quality import grounded_conflict
        self.assertEqual(grounded_conflict({'verified_calculation':calculation},'你計算的距離總和是錯誤的。'),'calculation_conflict')
        self.assertIsNone(grounded_conflict({'verified_calculation':calculation},'你計算的距離總和沒有錯，但這個住處不一定最佳。'))
        self.assertEqual(grounded_conflict({'verified_calculation':calculation},'平均數 (1+2+100)/3 = 33.666...'),'calculation_conflict')
        self.assertIsNone(grounded_conflict({'verified_calculation':calculation},'平均數 (1+2+100)/3 = 34.333...'))

    def test_manual_math_and_genuine_new_step_are_not_rejected_for_missing_old_expression(self):
        from .reply_quality import missing_code_anchor
        problem=SimpleNamespace(statement='一維地址練習')
        math=build_messages(problem,'int home=2;','請手算地址 1、2、1000 的總距離。',2,[])
        self.assertFalse(missing_code_anchor('1+0+998=999。',math))
        next_step=build_messages(problem,'vector<int> addresses(relatives);','下一步如何排序？',3,[])
        self.assertFalse(missing_code_anchor('```cpp\nsort(addresses.begin(), addresses.end());\n```',next_step))
        diagnosis=build_messages(problem,'vector<int> addresses(relatives);','請定位我目前的程式錯誤。',3,[])
        self.assertTrue(missing_code_anchor('```cpp\nint unrelated=0;\n```',diagnosis))

    def messages(self):
        return build_messages(SimpleNamespace(statement='找一個住處讓到各地址距離總和最小。'),'','完全沒有想法，請一步步引導，不要給完整答案。',1,[])

    def test_beginner_prompt_teaches_one_step_instead_of_a_questionnaire(self):
        system=readable_messages(self.messages())[0]['content']
        self.assertIn('最多問一個具體問題',system)
        self.assertIn('學生自己把片段放回原程式',system)

    def test_full_program_leak_is_retried_as_small_hint(self):
        with patch('coach.services._generate_once',side_effect=['```cpp\nint main(){return 0;}\n```','先比較地址 1、2、100：若住在 2，到三個地址的距離總和是多少？']) as model:
            answer=generate_hint(self.messages(),1)
        self.assertEqual(model.call_count,2)
        self.assertNotIn('main',answer)

    def test_multiple_intro_questions_are_retried_but_main_name_discussion_is_allowed(self):
        messages=self.messages()
        self.assertEqual(quality_issue('輸入是什麼？目標是什麼？限制又有哪些？',messages),'too_many_questions')
        self.assertIsNone(quality_issue('先從 `int main()` 這個名稱理解程式進入點。',messages))
        with patch('coach.services._generate_once',return_value='輸入是什麼？目標又是什麼？') as model:
            with self.assertRaises(HintError):generate_hint(messages,1)
        self.assertEqual(model.call_count,2)

    def test_explicit_solution_does_not_get_tutor_full_program_restriction(self):
        messages=build_messages(SimpleNamespace(statement='C++ 練習'),'','給我完整程式碼',3,[])
        self.assertIsNone(quality_issue('```cpp\nint main(){return 0;}\n```',messages))

    def test_known_domain_conflicts_and_stale_verdicts_trigger_repair(self):
        from .reply_quality import grounded_conflict
        payload={'problem_title':"UVa 10041 · Vito's family",'verified_topic_notes':'一維地址，距離為絕對值差，中位數最小。'}
        self.assertEqual(grounded_conflict(payload,'假設位置是 (x, y)，計算二維距離。'),'topic_conflict')
        self.assertEqual(grounded_conflict(payload,'中位數本身並不能保證最小化距離總和。'),'topic_conflict')
        self.assertIsNone(grounded_conflict(payload,'地址不是二維座標。中位數能最小化距離總和，但不保證程式已通過官方評測。'))
        payload.update(question='現在有已確認的錯誤嗎？',execution_evidence={'status':'accepted'})
        self.assertEqual(grounded_conflict(payload,'目前 home 的設定方式存在問題。'),'verdict_conflict')
        self.assertIsNone(grounded_conflict(payload,'目前沒有已確認的錯誤。通過測資不代表所有輸入都正確。'))
