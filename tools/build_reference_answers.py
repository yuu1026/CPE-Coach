"""Export only C++ fixtures with matching successful audit hashes.

Run from the project root: python tools/build_reference_answers.py
This reuses existing audits; it does not run or claim new judge executions.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from tools.validate_cpe49 import REFERENCES, HEAD

def main():
    catalog = json.loads((ROOT/'data/cpe49.json').read_text(encoding='utf-8'))
    originals = {p['uva']:p['code'] for p in json.loads((ROOT/'training/data/problems.json').read_text(encoding='utf-8'))}
    audits = {r['uva']:r for r in map(json.loads,(ROOT/'training/data/cpe49/verified_programs.jsonl').read_text(encoding='utf-8').splitlines()) if r['variant']=='correct'}
    output = {}
    for item in catalog:
        number = item['uva']
        code = originals[number] if number in originals else HEAD + REFERENCES[number]
        digest = hashlib.sha256(json.dumps({'code':code,'tests':item['tests'],'policy':'cpp17-docker-v2'},sort_keys=True).encode()).hexdigest()
        if audits[number]['sha256'] != digest or audits[number]['judge']['status'] != 'accepted':
            raise RuntimeError(f'UVa {number}: reference or tests changed; re-run the judge audit first.')
        output[str(number)] = {'code':code,'statement':item['statement'],'tests':item['tests'],'audit_sha256':digest}
    (ROOT/'data/cpe49-solutions.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Exported {len(output)} audited references.')

if __name__ == '__main__':
    main()
