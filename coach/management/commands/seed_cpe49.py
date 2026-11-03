import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from coach.models import Problem


class Command(BaseCommand):
    help = '匯入 CPE 一星選集 49 題自寫摘要與自編測資，保留既有題目與學習紀錄'

    def handle(self, **options):
        catalog = json.loads((Path(settings.BASE_DIR) / 'data/cpe49.json').read_text(encoding='utf-8'))
        if len(catalog) != 49 or len({p['uva'] for p in catalog}) != 49:
            raise CommandError('題庫必須包含 49 個不重複的 UVa 題號。')
        added = 0
        with transaction.atomic():
            for item in catalog:
                first, *others = item['tests']
                _, created = Problem.objects.get_or_create(
                    title=f"UVa {item['uva']} · {item['title']}",
                    defaults={'statement': item['statement'], 'sample_input': first['input'],
                              'sample_output': first['expected'], 'category': 'CPE 一星選集',
                              'source': item['source'], 'test_cases': others,
                              'output_comparison': first.get('comparison', 'exact')})
                added += created
                self.stdout.write(f'{"新增" if created else "保留"} UVa {item["uva"]} · {item["title"]}')
        self.stdout.write(self.style.SUCCESS(f'本次新增 {added} 題，保留 {49 - added} 題。'))
