import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.conf import settings
from django.test import SimpleTestCase
from .diagnostics import code_signature,lookup,profiles
from .code_format import format_cpp
from .services import build_messages,generate_hint

class AuditedDiagnosticTests(SimpleTestCase):
    def sample(self,number=490):
        rows=[json.loads(x) for x in (Path(settings.BASE_DIR)/'training/data/quality-v3/eval.jsonl').read_text(encoding='utf-8').splitlines()]
        row=next(r for r in rows if r['problem_id']==number)
        payload=json.loads(row['messages'][-2]['content'])
        problem=SimpleNamespace(title=payload['problem_title'],statement=payload['problem'])
        return problem,payload['code']

    def test_signature_is_whitespace_tolerant_but_preserves_cpp_tokens(self):
        self.assertEqual(code_signature('int x=1; // comment\nx++;'),code_signature('int x = 1;\nx ++ ;'))
        self.assertNotEqual(code_signature('x++;'),code_signature('x + +;'))
        self.assertNotEqual(code_signature('double x=1e-6;'),code_signature('double x=1 e - 6;'))
        self.assertNotEqual(code_signature('#include <iostream>\nint main(){}'),code_signature('#include <iostream> int main(){}'))
        self.assertNotEqual(code_signature('puts("a b");'),code_signature('puts("ab");'))
        self.assertNotEqual(code_signature('#define X "a b"\n'),code_signature('#define X "ab"\n'))
        self.assertNotEqual(code_signature('#define X(a) a\n'),code_signature('#define X (a) a\n'))

    def test_profile_matches_formatted_fixture_but_not_unknown_or_changed_task(self):
        problem,code=self.sample()
        profile=lookup(problem,code)
        self.assertIsNotNone(profile)
        self.assertEqual(lookup(problem,format_cpp(code))['audit_sha256'],profile['audit_sha256'])
        self.assertIsNone(lookup(problem,'int main(){}'))
        problem.statement+=' changed'
        self.assertIsNone(lookup(problem,code))
        self.assertEqual(len(profiles()),98)

    def test_known_diagnosis_is_labeled_and_not_repeated_on_followup(self):
        problem,code=self.sample()
        messages=build_messages(problem,code,'請定位目前程式的錯誤',2,[])
        with patch('coach.services._generate_once') as model:
            answer=generate_hint(messages,2)
        model.assert_not_called()
        self.assertEqual(answer.source,'verified_hint')
        self.assertIn('未呼叫模型',answer)
        self.assertIn('缺字',answer)
        history=[{'question':'請定位目前程式的錯誤','hint':str(answer),'code':code}]
        followup=build_messages(problem,code,'這個缺字位置為什麼要補空格？',2,history)
        with patch('coach.services._generate_once',return_value='因為缺少的格子必須保持欄位對齊，不能插入底線。') as model:
            generate_hint(followup,2)
        model.assert_called_once()

    def test_raw_training_prompt_can_explicitly_disable_diagnosis(self):
        problem,code=self.sample()
        messages=build_messages(problem,code,'請定位錯誤',2,[],include_diagnostics=False)
        self.assertNotIn('verified_diagnostic',json.loads(messages[-1]['content']))
