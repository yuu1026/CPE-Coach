"""Export only diagnoses whose exact raw programs match successful bug audits."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from coach.diagnostics import code_signature
from training.build_data import CATALOG
from training.cpe49_mutations import MUTATIONS

def main():
    catalog=json.loads((ROOT/'data/cpe49.json').read_text(encoding='utf-8'))
    refs=json.loads((ROOT/'data/cpe49-solutions.json').read_text(encoding='utf-8'))
    originals={p['uva']:p for p in CATALOG}
    audits={(r['uva'],r['variant']):r for r in map(json.loads,(ROOT/'training/data/cpe49/verified_programs.jsonl').read_text(encoding='utf-8').splitlines())}
    result={}
    for item in catalog:
        n=item['uva'];correct=refs[str(n)]['code']
        mutations=[(m[0],m[1],*m[3:]) for m in originals[n]['mutations'][:2]] if n in originals else MUTATIONS[n]
        for variant,(old,new,*hints) in zip(('bug_train','bug_eval'),mutations):
            if correct.count(old)!=1:raise ValueError(n)
            code=correct.replace(old,new)
            digest=hashlib.sha256(json.dumps({'code':code,'tests':item['tests'],'policy':'cpp17-docker-v2'},sort_keys=True).encode()).hexdigest()
            if audits[n,variant]['sha256']!=digest or audits[n,variant]['judge']['status']!='failed':raise ValueError(n)
            signature=code_signature(code)
            if signature in result:raise ValueError('Ambiguous signature')
            result[signature]={'problem_id':n,'statement_sha256':hashlib.sha256(item['statement'].encode()).hexdigest(),
                'audit_sha256':digest,'hints':hints,'source':'project-authored isolated mutation with existing Docker audit'}
    (ROOT/'data/cpe-diagnostic-profiles.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Exported {len(result)} audited diagnostic profiles; no new executions claimed.')

if __name__=='__main__':main()
