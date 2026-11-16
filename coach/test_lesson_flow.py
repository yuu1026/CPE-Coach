import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from .conversation_policy import response_intent,explanation_only,wants_edit
from .learning_context import cpp_concept
from .code_units import units
from .local_revision import apply_edits,RevisionError,header_setup_only,generate_revision
from .scaffold_policy import scaffold_issue
from .services import build_messages
from .model_prompt import readable_messages
from .lesson_progress import progress


class CurrentIntentTests(SimpleTestCase):
    def test_adopted_scaffold_is_not_new_scaffold_request(self):
        for q in ['我已貼上骨架，下一步只教一個局部修改。','骨架我已採用，接下來呢？','我已原樣貼上你給的骨架，請修改輸出部分。']:
            self.assertEqual(response_intent(q),'conversation')
            self.assertFalse(explanation_only(q))

    def test_new_scaffold_requests_still_work(self):
        for q in ['請給我C++骨架，只寫輸入。','我已貼上骨架，請重新給一個骨架。','給我完整程式骨架']:
            self.assertEqual(response_intent(q),'scaffold')

    def test_restricting_whole_rewrite_permits_local_edit(self):
        for q in ['請修改輸出，不要改寫整份程式。','請給一個局部修正，不要整份重寫。','請保留main及大括號，只修改輸出，給可套用的局部修改。']:
            self.assertTrue(wants_edit(q))
            self.assertFalse(explanation_only(q))
            self.assertFalse(cpp_concept(q,'tutor'))

    def test_true_no_edit_request_remains_explanation(self):
        self.assertTrue(explanation_only('請解釋作用域，不要修改程式。'))
        self.assertTrue(explanation_only('請手算，不需要改程式。'))

    def test_failed_candidate_is_not_student_scope_question(self):
        q='你剛才把while放到函式外面了。請保留原本main和大括號，給一個局部修正。'
        self.assertFalse(cpp_concept(q,'tutor'))
        self.assertFalse(explanation_only(q))

    def test_header_only_request_has_an_explicit_edit_contract(self):
        p=SimpleNamespace(title='UVa 10055 test',statement='差距',sample_input='1',sample_output='1',test_cases=[])
        data=json.loads(build_messages(p,'int main(){return 0;}','先只教新增排序標頭，其他程式先不改，請給可套用修改。')[-1]['content'])
        self.assertEqual(data['edit_scope'],'dependency_only')

    def test_next_step_can_explicitly_request_a_local_modification(self):
        problem=SimpleNamespace(title='test',statement='輸入與計算',sample_input='1',sample_output='1',test_cases=[])
        for q in ['請先教下一步，提供局部修改。','我已讀完資料，教我下一個可套用的局部修改。','先只教新增排序需要的標頭，其他程式先不改，給可套用的這一步。']:
            payload=json.loads(build_messages(problem,'int main(){return 0;}',q)[-1]['content'])
            self.assertEqual(payload['learning_mode'],'next_step')
            self.assertTrue(payload['revision_request'])


class SourceUnitTests(SimpleTestCase):
    code='#include <iostream>\nint main(){long long first,second;while(std::cin>>first>>second){std::cout<<first-second<<std::endl;}return 0;}'

    def test_minified_expression_replacement_preserves_main_and_loop(self):
        target=next(u for u in units(self.code) if u['kind']=='expression' and u['code']=='first-second')
        result=apply_edits(self.code,[{'unit_id':target['unit_id'],'after':'(first>second?first-second:second-first)'}])
        self.assertIn('int main()',result)
        self.assertIn('while(std::cin>>first>>second)',result)
        self.assertIn('std::cout<<(first>second?first-second:second-first)<<std::endl;',result)

    def test_parent_statement_can_resolve_unique_wrapped_operand(self):
        target=next(u for u in units(self.code) if u['kind']=='statement' and 'cout' in u['code'])
        result=apply_edits(self.code,[{'unit_id':target['unit_id'],'after':'abs(first-second)'}])
        self.assertIn('std::cout<<abs(first-second)<<std::endl;',result)
        self.assertIn('int main()',result)

    def test_ambiguous_wrapper_does_not_choose_between_equal_operands(self):
        code='int main(){int x=0;std::cout<<x<<x;}'
        target=next(u for u in units(code) if u['kind']=='statement' and 'cout' in u['code'])
        with self.assertRaises(RevisionError):apply_edits(code,[{'unit_id':target['unit_id'],'after':'abs(x)'}])

    def test_projection_never_discards_trailing_generated_words(self):
        from .local_revision import wrapped_operand
        target=next(u for u in units(self.code) if u['kind']=='statement' and 'cout' in u['code'])
        self.assertIsNone(wrapped_operand(self.code,target,'abs(first-second) instead of first-second'))

    def test_same_expression_has_independent_source_positions(self):
        code='int main(){int a=5,b=2;int x=a-b;int y=a-b;}'
        targets=[u for u in units(code) if u['kind']=='expression' and u['code']=='a-b']
        self.assertEqual(len(targets),2)
        result=apply_edits(code,[{'unit_id':targets[1]['unit_id'],'after':'b-a'}])
        self.assertIn('int x=a-b;int y=b-a;',result)

    def test_braces_in_literals_and_comments_are_not_structure(self):
        code='int main(){/* } ; */ const char* text="{ ; }";int x=1;}'
        target=next(u for u in units(code) if u['code']=='1')
        self.assertIn('int x=2;',apply_edits(code,[{'unit_id':target['unit_id'],'after':'2'}]))

    def test_unknown_id_and_overlapping_units_rejected(self):
        with self.assertRaises(RevisionError):apply_edits(self.code,[{'unit_id':'U999','after':'1'}])
        ts=units(self.code)
        statement=next(u for u in ts if u['kind']=='statement' and 'cout' in u['code'])
        expression=next(u for u in ts if u['code']=='first-second')
        with self.assertRaises(RevisionError):apply_edits(self.code,[{'unit_id':statement['unit_id'],'after':'return 0;'}, {'unit_id':expression['unit_id'],'after':'0'}])

    def test_raw_strings_do_not_get_guessed_units(self):
        self.assertEqual(units('int main(){auto x=R"(a;b)";}'),[])

    def test_insert_after_input_loop_without_guessing_a_physical_line(self):
        code='int main(){int a[2];for(int i=0;i<2;i++){std::cin>>a[i];}return 0;}'
        target=next(u for u in units(code) if u['kind']=='block_end' and u['context'].startswith('for('))
        result=apply_edits(code,[{'unit_id':target['unit_id'],'after':'} int marker=1;'}])
        self.assertIn('std::cin>>a[i];} int marker=1;return 0;',result)

    def test_necessary_include_can_be_added_outside_function(self):
        target=next(u for u in units(self.code) if u['kind']=='include')
        result=apply_edits(self.code,[{'unit_id':target['unit_id'],'after':target['code']+'#include <cstdlib>\n'}])
        self.assertIn('#include <iostream>\n#include <cstdlib>\nint main()',result)

    def test_dependency_step_cannot_hide_runtime_changes(self):
        self.assertTrue(header_setup_only(self.code,'#include <algorithm>\n'+self.code))
        self.assertFalse(header_setup_only(self.code,'#include <algorithm>\n'+self.code.replace('first-second','0')))
        self.assertFalse(header_setup_only(self.code,'#include "private.h"\n'+self.code))

    def test_header_operation_never_inserts_into_main(self):
        result=apply_edits(self.code,[{'header':'algorithm'}])
        self.assertTrue(result.startswith('#include <algorithm>\n#include <iostream>'))
        self.assertEqual(result.count('int main()'),1)
        with self.assertRaises(RevisionError):apply_edits(result,[{'header':'algorithm'}])

    def test_header_operation_cannot_read_arbitrary_paths(self):
        with self.assertRaises(RevisionError):apply_edits(self.code,[{'header':'../../private.h'}])

    def test_equivalent_redundant_header_representation_is_safe(self):
        result=apply_edits(self.code,[{'header':'<algorithm>','after':'\\n#include <algorithm>\\n'}])
        self.assertTrue(result.startswith('#include <algorithm>\n'))
        self.assertTrue(header_setup_only(self.code,result))

    def test_redundant_header_cannot_smuggle_other_cpp(self):
        with self.assertRaises(RevisionError):apply_edits(self.code,[{'header':'algorithm','after':'#include <algorithm>\nint evil=1;'}])
        with self.assertRaises(RevisionError):apply_edits(self.code,[{'header':'algorithm','after':'#include <vector>'}])


class ScaffoldContractTests(SimpleTestCase):
    def test_input_setup_with_real_placeholder_is_allowed(self):
        self.assertIsNone(scaffold_issue('int main(){int t;while(t--){int n;/* TODO 核心 */}return 0;}'))

    def test_todo_does_not_hide_complete_calculation(self):
        for code in ['int main(){/*TODO*/int answer=3;std::cout<<answer;}',
                     'int main(){/*TODO*/sort(a.begin(),a.end());}',
                     'int main(){/*TODO*/int sum=0;sum+=x;}',
                     'int main(){/*TODO*/int home=a[n/2];}']:
            self.assertIsNotNone(scaffold_issue(code))

    def test_solution_inside_comment_is_not_empty_core(self):
        self.assertIsNotNone(scaffold_issue('int main(){/*TODO for(int x:a){sum+=abs(x-home);}*/return 0;}'))

    def test_todo_only_in_string_is_not_placeholder(self):
        self.assertIsNotNone(scaffold_issue('int main(){const char* s="TODO";return 0;}'))

    def test_return_inside_cases_loop_is_rejected(self):
        self.assertIsNotNone(scaffold_issue('int main(){int t;while(t--){/*TODO*/return 0;}return 0;}'))


class DependencyStepTests(SimpleTestCase):
    code='#include <iostream>\nint main(){int x=0;std::cout<<x;}'

    def result(self):
        return {'status':'failed','label':'2/3','cases':[{'name':str(i),'status':'accepted' if i<2 else 'wrong_answer','input':'','expected':'0' if i<2 else '1','actual':'0'} for i in range(3)]}

    def messages(self):
        return [{'role':'user','content':json.dumps({'code':self.code,'revision_tests':[{'name':str(i),'input':'','expected':'0' if i<2 else '1'} for i in range(3)],'learning_mode':'next_step'})}]

    def test_header_step_is_labelled_as_dependency_not_algorithm_repair(self):
        target=next(u for u in units(self.code) if u['kind']=='include')
        plan=json.dumps({'explanation':'先新增必要的標頭，後續才使用函式。','edits':[{'unit_id':target['unit_id'],'after':target['code']+'#include <algorithm>\n'}]})
        with patch('coach.local_revision.judge',side_effect=[self.result(),self.result()]):
            text,check=generate_revision(self.messages(),None,lambda *args:plan,str)
        self.assertEqual(check['verification_scope'],'dependency_only')
        self.assertIn('尚未修正運算',text)

    def test_next_step_does_not_allow_no_progress_runtime_edit_in_complete_output(self):
        target=next(u for u in units(self.code) if u['kind']=='expression' and u['code']=='x')
        plan=json.dumps({'explanation':'修改輸出運算式，嘗試另一個方法。','edits':[{'unit_id':target['unit_id'],'after':'x+0'}]})
        with patch('coach.local_revision.judge',side_effect=[self.result(),self.result(),self.result()]):
            with self.assertRaises(RevisionError):generate_revision(self.messages(),None,lambda *args:plan,str)

    def test_header_only_request_cannot_be_overridden_by_a_runtime_patch(self):
        target=next(u for u in units(self.code) if u['kind']=='expression' and u['code']=='x')
        plan=json.dumps({'explanation':'順便修改輸出來完成題目。','edits':[{'unit_id':target['unit_id'],'after':'x+1'}]})
        messages=self.messages();payload=json.loads(messages[-1]['content']);payload['edit_scope']='dependency_only';messages[-1]['content']=json.dumps(payload)
        with patch('coach.local_revision.judge',return_value=self.result()) as judge:
            with self.assertRaises(RevisionError):generate_revision(messages,None,lambda *args:plan,str)
        self.assertEqual(judge.call_count,1)


@override_settings(HINT_MODE='live')
class LessonTransportTests(SimpleTestCase):
    problem=SimpleNamespace(title='UVa 10055 · Hashmat',statement='輸出兩數絕對差',sample_input='2 9',sample_output='7',test_cases=[])

    def test_local_request_not_misrouted_and_units_are_transported(self):
        code=SourceUnitTests.code
        messages=build_messages(self.problem,code,'請修改輸出，不要改寫整份程式。')
        payload=json.loads(messages[-1]['content'])
        self.assertTrue(payload['revision_request'])
        self.assertNotEqual(payload['question_kind'],'cpp_concept')
        transport=readable_messages(messages)
        self.assertIn('unit_id',transport[0]['content'])
        self.assertIn('first-second',transport[-1]['content'])
        self.assertNotIn('系統標定行',transport[-1]['content'])

    def test_progress_does_not_invent_mastery_or_parse_commented_code(self):
        state=progress('/*std::sort(a.begin(),a.end());*/int main(){}','接下來呢？',
            [{'question':'我理解輸入了','hint':'你什麼都會了','delivered':True},{'question':'重試','hint':'錯誤','delivered':False}],None)
        self.assertNotIn('含排序呼叫',state['observed_features'])
        self.assertEqual(state['student_reported_understanding'],['我理解輸入了'])
        self.assertEqual(state['recent_blocked_turns'],1)
        self.assertEqual(state['test_status'],'not_run')
