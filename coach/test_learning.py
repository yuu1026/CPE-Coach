import json
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from .learning import TRACKS, learning_context
from .models import Problem, ProblemCompletion, Submission


class LearningTests(TestCase):
    def test_asset_version_changes_with_contents_and_revalidates_cache(self):
        from tempfile import TemporaryDirectory
        from .templatetags.coach_ui import versioned_static
        with TemporaryDirectory(dir=settings.BASE_DIR) as directory:
            root = Path(directory)
            (root / 'static').mkdir()
            asset = root / 'static' / 'style.css'
            asset.write_text('old', encoding='utf-8')
            with override_settings(BASE_DIR=root):
                first = versioned_static('style.css')
                self.assertEqual(first, versioned_static('style.css'))
                asset.write_text('new', encoding='utf-8')
                self.assertNotEqual(first, versioned_static('style.css'))
        response = self.client.get('/assets/coach/app.css')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])

    def test_all_49_topics_have_exactly_one_learning_group(self):
        catalog = json.loads((Path(settings.BASE_DIR) / 'data/cpe49.json').read_text(encoding='utf-8'))
        numbers = [number for *_, group in TRACKS for number in group]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(set(numbers), {item['uva'] for item in catalog})

    def test_learning_order_skips_completed_and_handles_empty_catalog(self):
        topics = [SimpleNamespace(pk=n, title=f'UVa {n} · Test') for n in [10071, 10055]]
        result = learning_context(topics, {10055}, topics[0])
        self.assertEqual(result['recommended_problem'].pk, 10071)
        self.assertEqual(result['current_track']['done'], 1)
        self.assertEqual(result['learning_tracks'][0]['next'].pk, 10071)
        self.assertIsNone(learning_context(topics, {10055,10071})['recommended_problem'])
        self.assertEqual(learning_context([], set())['learning_tracks'], [])

    def test_resume_counts_and_completion_are_owned_by_current_user(self):
        owner = get_user_model().objects.create_user('learning-owner')
        other = get_user_model().objects.create_user('learning-other')
        problem = Problem.objects.create(title='UVa 10055 · Hashmat', statement='test', sample_input='1', sample_output='1', category='CPE 一星')
        def record(user):
            return Submission.objects.create(owner=user, problem=problem, code='', hint_level=1, mode='demo', model='demo', status='done')
        mine = record(owner)
        record(owner)  # Two submissions still count as one practiced problem.
        record(other)
        ProblemCompletion.objects.create(owner=other, problem=problem)
        self.client.force_login(owner)
        response = self.client.get('/?track=basics')
        self.assertEqual(response.context['resume_record'].owner, owner)
        self.assertEqual(response.context['practiced_count'], 1)
        self.assertEqual(response.context['completed_count'], 0)
        self.assertEqual(response.context['selected_track'], 'basics')
        self.assertContains(response, 'data-track="basics"')
        self.assertEqual(self.client.get('/?track=unknown').context['selected_track'], '')
        page = self.client.get(reverse('detail', args=[mine.pk]))
        self.assertContains(page, 'id="thinking-notes"')
        self.assertContains(page, '/assets/coach/learning-tools.js')
        self.assertContains(page, '目前學習路線')

    def test_empty_dashboard_is_usable(self):
        owner = get_user_model().objects.create_user('new-learner')
        self.client.force_login(owner)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['resume_record'])
        self.assertEqual(response.context['practiced_count'], 0)
        self.assertContains(response, '題庫準備中')
