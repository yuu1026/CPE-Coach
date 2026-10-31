from django.core.management.base import BaseCommand
from coach.models import Problem

class Command(BaseCommand):
    help = '建立三道自編示範題，不覆寫既有題目'

    def handle(self, **options):
        examples = [
            ('區間加總', '讀入整數 n，接著讀入 n 個整數，輸出總和。\n限制：1 ≤ n ≤ 1000，每個數介於 -1000 與 1000。', '3\n2 -1 5', '6', '迴圈與邊界'),
            ('鏡像字串', '讀入一行非空字串，判斷是否與反轉後相同。相同輸出 YES，否則 NO。\n限制：長度 1 至 1000，只含小寫英文字母。', 'level', 'YES', '字串與索引'),
            ('第二個不同的數', '讀入 n 與 n 個整數，輸出第二小的相異整數；不足兩種數值時輸出 NONE。\n限制：1 ≤ n ≤ 1000，每個數介於 -10000 與 10000。', '5\n3 1 1 5 2', '2', '排序與重複值'),
        ]
        for title, statement, sample_input, sample_output, category in examples:
            Problem.objects.get_or_create(title=title, defaults=dict(statement=statement, sample_input=sample_input, sample_output=sample_output, category=category))
        extra = {
            '區間加總': [
                {'name': '單一負數', 'input': '1\n-1000\n', 'expected': '-1000\n'},
                {'name': '正負抵消', 'input': '4\n-3 3 -5 5\n', 'expected': '0\n'},
                {'name': '最大筆數', 'input': '1000\n' + ' '.join(['1000'] * 1000) + '\n', 'expected': '1000000\n'},
            ],
            '鏡像字串': [
                {'name': '單一字元', 'input': 'a\n', 'expected': 'YES\n'},
                {'name': '偶數長回文', 'input': 'abba\n', 'expected': 'YES\n'},
                {'name': '非回文', 'input': 'abca\n', 'expected': 'NO\n'},
            ],
            '第二個不同的數': [
                {'name': '單一數值', 'input': '1\n5\n', 'expected': 'NONE\n'},
                {'name': '全部相同', 'input': '3\n2 2 2\n', 'expected': 'NONE\n'},
                {'name': '負數與重複', 'input': '5\n0 -3 -3 -1 2\n', 'expected': '-1\n'},
            ],
        }
        for title, cases in extra.items():
            Problem.objects.filter(title=title, test_cases=[]).update(test_cases=cases)
        self.stdout.write(self.style.SUCCESS('三道自編教學題已準備完成。'))
