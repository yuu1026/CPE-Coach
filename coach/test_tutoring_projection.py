import json
from unittest.mock import patch
from django.test import SimpleTestCase,override_settings
from .teaching_tools import vito_next_step
from .tutoring_projection import project_next_step
from .services import generate_hint

SOURCE='#include <iostream>\n#include <vector>\nusing namespace std;\nint main(){int people; cin >> people; vector<int> places(people); for(int i=0;i<people;++i)cin>>places[i];\n// next\n}'

class SingleStepProjectionTests(SimpleTestCase):
    def payload(self):return {'code':SOURCE,'question':'下一步怎麼寫？','response_mode':'tutor','learning_mode':'next_step','verified_next_step':vito_next_step(SOURCE)}
    def proposal(self,body):return '先排序已讀入的地址。\n```cpp\n'+body+'\n```'
    def added(self):return SOURCE.replace('#include <vector>','#include <vector>\n#include <algorithm>').replace('// next','std::sort(places.begin(), places.end());\n// next')

    def test_valid_single_addition_is_shown_without_student_boilerplate(self):
        result,changed=project_next_step(self.proposal(self.added()),self.payload())
        self.assertTrue(changed)
        self.assertNotIn('int main',result)
        self.assertIn('std::sort(places.begin(), places.end());',result)
        self.assertIn('#include <algorithm>',result)

    def test_existing_code_edits_unexpected_headers_and_wrong_algorithm_are_not_projected(self):
        for wrong in [self.added().replace('cin >> people','cin >> other'),self.added().replace('<algorithm>','<fstream>'),self.added().replace('std::sort','std::reverse')]:
            self.assertFalse(project_next_step(self.proposal(wrong),self.payload())[1])
        self.assertFalse(project_next_step(self.proposal(self.added())+'\n```cpp\nint unwanted=0;\n```',self.payload())[1])

    def test_lesson_does_not_use_home_before_the_selected_declaration_step(self):
        from .reply_quality import quality_issue
        payload=dict(self.payload(),verified_next_step={'step':'median','snippet':'int home=places[people/2];'})
        messages=[{'role':'user','content':json.dumps(payload)}]
        self.assertEqual(quality_issue('```cpp\ntotal += abs(address-home);\n```',messages),'lesson_order')

    def test_local_step_discards_conflicting_model_prose(self):
        payload=self.payload()
        result,changed=project_next_step('先算平均數。\n```cpp\n'+payload['verified_next_step']['snippet']+'\n```',payload)
        self.assertTrue(changed)
        self.assertNotIn('平均數',result)
        self.assertIn('非模型獨立判斷',result)

    @override_settings(HINT_MODE='live')
    def test_two_bad_candidates_recover_with_labelled_step_without_changing_code(self):
        payload=self.payload()
        messages=[{'role':'system','content':'提示模式'},{'role':'user','content':json.dumps(payload)}]
        with patch('coach.services._generate_once',return_value='```cpp\nint home=0;\n```') as model:
            result=generate_hint(messages,3)
        self.assertEqual(model.call_count,2)
        self.assertEqual(result.source,'verified_step')
        self.assertIn('std::sort(places.begin(), places.end());',result)
        self.assertNotIn('home=0',result)
        self.assertEqual(json.loads(messages[-1]['content'])['code'],SOURCE)

    def test_undeclared_home_is_repaired_before_distance_work(self):
        code=self.added().replace('// next','int total=0; for(int address:places)total+=abs(address-home);')
        self.assertEqual(vito_next_step(code)['step'],'median')
        self.assertIsNone(vito_next_step(code.replace('int total=0;','int home=0; int total=0;')))

    @override_settings(HINT_MODE='live')
    def test_pipeline_records_projection_and_does_not_retry_a_correct_small_step(self):
        messages=[{'role':'system','content':'提示模式'},{'role':'user','content':json.dumps(self.payload())}]
        with patch('coach.services._generate_once',return_value=self.proposal(self.added())) as model:
            answer=generate_hint(messages,3)
        model.assert_called_once();self.assertTrue(answer.tutoring_projection)
        self.assertEqual(json.loads(messages[-1]['content'])['code'],SOURCE)

    def test_curriculum_advances_one_step_and_declines_unknown_layout(self):
        code=SOURCE
        self.assertEqual(vito_next_step(code)['step'],'sort')
        code=code.replace('// next','std::sort(places.begin(), places.end());\n// next')
        self.assertEqual(vito_next_step(code)['step'],'median')
        code=code.replace('// next','int home=places[people/2];\n// next')
        self.assertEqual(vito_next_step(code)['step'],'distance')
        code=code.replace('// next',vito_next_step(code)['snippet']+'\n// next')
        self.assertEqual(vito_next_step(code)['step'],'output')
        code=code.replace('// next',vito_next_step(code)['snippet']+'\n// next')
        self.assertEqual(vito_next_step(code)['step'],'test')
        self.assertIsNone(vito_next_step('int main(){}'))
        self.assertIsNone(vito_next_step(SOURCE.replace('// next','vector<int> other(people);')))
