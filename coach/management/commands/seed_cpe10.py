import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from coach.models import Problem

class Command(BaseCommand):
    help = '匯入本次十題自寫摘要及自編測資，不覆寫既有題目'

    def handle(self, **options):
        catalog = json.loads((Path(settings.BASE_DIR) / 'training/data/problems.json').read_text(encoding='utf-8'))
        for item in catalog:
            first, *others = item['tests']
            problem, created = Problem.objects.get_or_create(title=f"UVa {item['uva']} · {item['title']}", defaults={'statement': item['statement'], 'sample_input': first['input'], 'sample_output': first['expected'], 'category': 'CPE 一星選集', 'source': item['source'], 'test_cases': others})
            self.stdout.write(f'{"新增" if created else "保留"} {problem.title}')
