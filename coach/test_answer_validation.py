import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from .answer_validation import compile_full_reply
from .services import build_messages,generate_hint,HintError
from .model_prompt import readable_messages

BAD='int main(){ if(true){int home=1;} return home; }'
GOOD='int main(){ int home=1; return 0; }'
GOOD_REPLY='原本的 `int home=1;` 只在區塊內有效，將宣告移到外層。\n```cpp\n'+GOOD+'\n```'

@override_settings(HINT_MODE='live')
class GeneratedCompilationTests(SimpleTestCase):
    def test_generated_candidate_is_tested_with_problem_cases(self):
        tests=[{'name':'median','input':'1\n3 1 2 100\n','expected':'99\n'}]
        with patch('coach.answer_validation.judge',return_value={'status':'accepted'}) as docker:
            checked=compile_full_reply('```cpp\n'+GOOD+'\n```',{'response_mode':'solution','generated_program_tests':tests})
        self.assertEqual(docker.call_args.args[1],tests)
        self.assertEqual(checked,{'status':'tested','passed':1})

    def test_wrong_answer_feedback_does_not_let_compiling_code_pass(self):
        failure={'status':'failed','cases':[{'status':'wrong_answer','input':'1\n3 1 2 100\n','expected':'99\n','actual':'131\n'}]}
        with patch('coach.services._generate_once',return_value='```cpp\n'+BAD+'\n```') as model,patch('coach.answer_validation.judge',return_value=failure):
            with self.assertRaisesMessage(HintError,'仍未通過編譯或測資'):
                generate_hint(self.messages(),3)
        self.assertEqual(model.call_count,2)
        payload=json.loads(model.call_args.args[0][-1]['content'])
        self.assertEqual(payload['candidate_compile_failure']['status'],'test_failure')
        self.assertIn('131',payload['candidate_compile_failure']['compiler'])

    def test_verification_cases_not_sent_in_normal_model_prompt(self):
        problem=SimpleNamespace(statement='中位數練習',sample_input='1\n',sample_output='2\n',test_cases=[{'name':'reserved','input':'3\n','expected':'RESERVED_EXPECTED'}])
        messages=build_messages(problem,'int answer=0;','請檢查這一段。',3,[])
        self.assertEqual(len(json.loads(messages[-1]['content'])['generated_program_tests']),2)
        self.assertNotIn('RESERVED_EXPECTED',readable_messages(messages)[-1]['content'])
        self.assertNotIn('comparison',problem.test_cases[0])

    def messages(self):
        return build_messages(SimpleNamespace(statement='C++ 作用域練習'),BAD,'直接給我修正過的程式',3,[])

    def test_compile_only_passes_no_runtime_cases_to_docker(self):
        with patch('coach.answer_validation.judge',return_value={'status':'accepted'}) as docker:
            result=compile_full_reply('~~~cpp\n'+GOOD+'\n~~~',{'response_mode':'solution'})
        self.assertEqual(result['status'],'compiled')
        self.assertEqual(docker.call_args.args[1],[])

    def test_tutor_snippets_do_not_require_a_full_program_or_compile(self):
        with patch('coach.answer_validation.judge') as docker:
            self.assertIsNone(compile_full_reply('```cpp\nint home=1;\n```',{'response_mode':'tutor'}))
        docker.assert_not_called()

    def test_scope_failure_gets_one_retry_with_separate_candidate_evidence(self):
        with patch('coach.services._generate_once',side_effect=['```cpp\n'+BAD+'\n```',GOOD_REPLY]) as model, patch('coach.answer_validation.judge',side_effect=[{'status':'compile_error','compiler':'home was not declared'},{'status':'accepted'}]) as docker:
            reply=generate_hint(self.messages(),3)
        self.assertEqual(model.call_count,2);self.assertEqual(docker.call_count,2)
        retry=model.call_args.args[0]
        payload=json.loads(retry[-1]['content'])
        self.assertEqual(payload['code'],BAD)
        self.assertEqual(payload['candidate_compile_failure']['candidate'].strip(),BAD)
        self.assertIn('不是學生程式的執行結果',readable_messages(retry)[-1]['content'])
        self.assertIn('尚未執行測資',reply)

    def test_second_compile_failure_is_not_published_as_an_answer(self):
        with patch('coach.services._generate_once',return_value='```cpp\n'+BAD+'\n```') as model,patch('coach.answer_validation.judge',return_value={'status':'compile_error','compiler':'home was not declared'}):
            with self.assertRaisesMessage(HintError,'仍未通過編譯'):
                generate_hint(self.messages(),3)
        self.assertEqual(model.call_count,2)

    def test_unavailable_docker_is_disclosed_and_missing_code_is_not_accepted(self):
        with patch('coach.services._generate_once',return_value=GOOD_REPLY),patch('coach.answer_validation.judge',return_value={'status':'unavailable','label':'Docker 未啟動'}):
            answer=generate_hint(self.messages(),3)
        self.assertIn('尚未驗證',answer)
        self.assertEqual(compile_full_reply('我已經修好了。',{'response_mode':'solution'})['status'],'missing_program')
