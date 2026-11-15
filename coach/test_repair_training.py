import hashlib
import json
import re
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from training.build_repair_data import fixtures


class RepairCurriculumTests(SimpleTestCase):
    def test_v7_fences_close_on_own_lines_and_sampling_is_disclosed(self):
        root=Path(settings.BASE_DIR)/'training/data/quality-v7'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['counts']['train'],136)
        self.assertEqual(manifest['distinct_examples']['train'],96)
        for split in ['train','eval','test']:
            raw=(root/f'{split}.jsonl').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['sha256'][split])
            for row in map(json.loads,raw.decode().splitlines()):
                if not row['rubric']['full_solution']:continue
                block=re.search(r'^```cpp\n(.*?)^```\s*$',row['messages'][-1]['content'],re.M|re.S)
                self.assertIsNotNone(block)
                self.assertEqual(block[1],row['gold_code'])

    def test_non_applicable_checks_are_not_counted_as_passes(self):
        from training.evaluate_quality import summarize
        result=summarize([{'base':{'rule_pass':True,'checks':{'generated_code_passes_tests':True}},'adapter':{'rule_pass':True,'checks':{'generated_code_passes_tests':True}}},
                          {'base':{'rule_pass':True,'checks':{'complete':True}},'adapter':{'rule_pass':True,'checks':{'complete':True}}}])
        self.assertEqual(result['adapter']['by_check']['generated_code_passes_tests'],1)
        self.assertEqual(result['adapter']['by_check_totals']['generated_code_passes_tests'],1)

    def test_frozen_hashes_and_no_full_target_in_repair_prompt(self):
        root=Path(settings.BASE_DIR)/'training/data/quality-v6'
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        for split in ['train','eval','test']:
            raw=(root/f'{split}.jsonl').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['sha256'][split])
            rows=[json.loads(s) for s in raw.decode().splitlines()]
            self.assertEqual(len(rows),manifest['counts'][split])
            for row in rows:
                if row['rubric']['full_solution']:
                    self.assertNotIn(row['gold_code'],row['messages'][-2]['content'])
                    self.assertIn(row['gold_code'],row['messages'][-1]['content'])
                self.assertNotIn('verified_diagnostic','\n'.join(m['content'] for m in row['messages'][:-1]))

    def test_audits_are_real_passing_targets_with_failing_controls(self):
        path=Path(settings.BASE_DIR)/'training/data/quality-v6/program_audits.json'
        audits=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(audits),28)
        for audit in audits:
            fixture=fixtures(audit['family'],audit['name'])
            digest=hashlib.sha256(json.dumps(fixture,sort_keys=True).encode()).hexdigest()
            self.assertEqual(digest,audit['sha256'])
            self.assertEqual(audit['good']['status'],'accepted')
            self.assertTrue(audit['good']['cases'])
            self.assertTrue(all(c['status']=='accepted' for c in audit['good']['cases']))
            self.assertIn(audit['bad']['status'],['failed','compile_error'])

    def test_full_targets_keep_the_requested_variable(self):
        root=Path(settings.BASE_DIR)/'training/data/quality-v6'
        for split in ['train','eval','test']:
            for row in map(json.loads,(root/f'{split}.jsonl').read_text(encoding='utf-8').splitlines()):
                if not row['rubric']['full_solution']:continue
                # The corrected program must actually be the audited target,
                # not just a response containing any C++ fence.
                blocks=re.findall(r'```cpp\n(.*?)```',row['messages'][-1]['content'],re.S)
                self.assertIn(row['gold_code'],blocks)
