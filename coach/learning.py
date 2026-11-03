"""Project-authored learning groups, rather than an official CPE ranking."""
import re

TRACKS = (
    ('basics', '輸入與基礎運算', '先熟悉讀取、迴圈與輸出格式。', (10055, 10071, 10783, 10812, 11150, 11332)),
    ('strings', '字串與字元處理', '練習逐字觀察、統計與格式轉換。', (272, 10222, 10008, 10062, 10252, 10420, 10226, 490, 10415)),
    ('simulation', '流程模擬', '把題意拆成狀態與每一步的變化。', (10035, 10038, 100, 10409, 10050, 118, 12019)),
    ('sorting', '排序與序列', '觀察順序、比較規則與數列性質。', (299, 10041, 10057, 11063, 11321)),
    ('numbers', '數論與進位', '練習整數性質、進位與數學推理。', (10931, 10019, 10922, 10929, 948, 10190, 10193, 10235, 11417, 11461, 10093, 10101, 10170, 10268, 11005, 10056)),
    ('matrix', '陣列與矩陣', '練習索引、鄰近位置與邊界檢查。', (10189, 11349, 10908)),
    ('geometry', '幾何與座標', '把座標與幾何關係轉成可驗證的計算。', (10242, 10642, 10221)),
)

def uva_number(problem):
    match = re.match(r'UVa\s+(\d+)\b', problem.title, re.IGNORECASE)
    return int(match.group(1)) if match else None

def learning_context(problems, completed, current=None):
    lookup = {uva_number(problem): problem for problem in problems}
    groups = []
    for slug, name, description, numbers in TRACKS:
        items = [lookup[number] for number in numbers if number in lookup]
        for problem in items:
            problem.track_slug, problem.track_name = slug, name
        if items:
            groups.append({'slug': slug, 'name': name, 'description': description,
                'total': len(items), 'done': sum(p.pk in completed for p in items),
                'next': next((p for p in items if p.pk not in completed), None)})
    for problem in problems:
        if not hasattr(problem, 'track_slug'):
            problem.track_slug, problem.track_name = 'other', '其他練習'
    ordered = [lookup[n] for *_, numbers in TRACKS for n in numbers if n in lookup]
    ordered += [p for p in problems if p not in ordered]
    return {'problems': problems, 'learning_tracks': groups,
        'recommended_problem': next((p for p in ordered if p.pk not in completed), None),
        'current_track': next((g for g in groups if current and any(
            p.pk == current.pk and p.track_slug == g['slug'] for p in problems)), None)}
