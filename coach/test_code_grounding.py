import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .model_prompt import readable_messages
from .reply_quality import missing_code_anchor
from .services import build_messages, generate_hint, HintError


@override_settings(HINT_MODE='live')
class CodeGroundingTests(SimpleTestCase):
    code='int total = 0; for (int k=0; k<=count; ++k) { total += values[k]; }'

    def messages(self, question='我的迴圈為什麼會越界？', history=None):
        return build_messages(SimpleNamespace(title='C++ 練習',statement='累加 count 個元素。'),
                              self.code,question,3,history or [])

    def test_latest_code_is_near_question_and_old_code_is_not_resent(self):
        messages=self.messages(history=[{'question':'舊版如何？','hint':'之前的說法不一定正確。','code':'int old_sum = 0;'}])
        readable=readable_messages(messages)
        self.assertNotIn('old_sum','\n'.join(m['content'] for m in readable))
        self.assertIn('保留變數、函式和解題思路',readable[0]['content'])
        self.assertIn('total += values[k]',readable[-1]['content'])
        self.assertTrue(readable[-1]['content'].endswith('我的迴圈為什麼會越界？'))

    def test_full_solution_with_existing_code_does_not_shortcut_to_reference(self):
        with patch('coach.services.reference_for') as reference:
            messages=self.messages('直接給我修正過的程式')
        reference.assert_not_called()
        payload=json.loads(messages[-1]['content'])
        self.assertEqual(payload['response_mode'],'solution')
        self.assertNotIn('reference_solution',payload)
        with patch('coach.services._generate_once',return_value='你原本的 `k<=count` 會多走一次；保留寫法並改成 `k<count`。') as model, patch('coach.services.compile_full_reply',return_value=None):
            answer=generate_hint(messages,3)
        model.assert_called_once()
        self.assertEqual(answer.source,'model')

    def test_guard_requires_current_expression_not_generic_or_old_code(self):
        messages=self.messages()
        for answer in ['請先檢查迴圈和輸入格式。','請改正 `old_sum += x`。','先看 `int main() {`。']:
            self.assertTrue(missing_code_anchor(answer,messages))
        self.assertFalse(missing_code_anchor('目前的 `k <= count` 會使索引到達 count。',messages))
        self.assertFalse(missing_code_anchor('```cpp\ntotal += values[k];\n```\n這是目前的累加位置。',messages))
        self.assertFalse(missing_code_anchor('先理解輸入。',build_messages(SimpleNamespace(statement='練習'),'','怎麼開始？',1,[])))

    def test_generic_reply_is_retried_without_feeding_bad_answer(self):
        messages=self.messages()
        with patch('coach.services._generate_once',side_effect=[
            '請先確認讀入格式，並測試所有邊界。',
            '你的 `k<=count` 在 k 等於 count 時仍會執行；此時 `values[k]` 超出有效索引。局部改為 `k<count`，保留原本的 total 累加。'
        ]) as model:
            reply=generate_hint(messages,3)
        self.assertEqual(model.call_count,2)
        self.assertIn('k<=count',reply)
        retry=model.call_args.args[0]
        self.assertIn('沒有引用目前程式',readable_messages(retry)[0]['content'])
        self.assertNotIn('請先確認讀入格式','\n'.join(m['content'] for m in retry))
        self.assertNotIn('上一個候選回覆',messages[0]['content'])

    def test_persistent_ungrounded_answer_is_not_shown_as_valid_diagnosis(self):
        with patch('coach.services._generate_once',return_value='請先檢查輸入輸出，並自行追蹤迴圈內容。') as model:
            with self.assertRaisesMessage(HintError,'目前程式引用'):
                generate_hint(self.messages(),3)
        self.assertEqual(model.call_count,2)
