"""Verify each distinct formatted v7 full target in the existing Docker judge."""
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from coach.judging import judge

def main():
    path=ROOT/'training/reports/gemma3-quality-v7/formatted_target_audits.json'
    if path.exists():raise RuntimeError('Audit already exists; do not overwrite.')
    done={}
    for split in ['train','eval','test']:
        for row in map(json.loads,(ROOT/f'training/data/quality-v7/{split}.jsonl').read_text(encoding='utf-8').splitlines()):
            if not row['rubric']['full_solution']:continue
            key=hashlib.sha256(json.dumps({'code':row['gold_code'],'tests':row['tests']},sort_keys=True).encode()).hexdigest()
            if key in done:continue
            result=judge(row['gold_code'],row['tests'])
            done[key]=dict(id=row['id'],split=split,code_sha256=hashlib.sha256(row['gold_code'].encode()).hexdigest(),judge=result)
            print(row['id'],result['status'],flush=True)
            if result['status']!='accepted':raise RuntimeError('Formatted target failed audit; stop training/evaluation.')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(done,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('All',len(done),'distinct formatted full targets passed.')

if __name__=='__main__':main()
