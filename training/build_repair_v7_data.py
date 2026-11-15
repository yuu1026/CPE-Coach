"""Correct v6 target fences/format and explicitly weight full-program repairs."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from coach.code_format import format_cpp

def main():
    source=ROOT/'training/data/quality-v6';dest=ROOT/'training/data/quality-v7'
    if dest.exists():raise RuntimeError('Refuse to overwrite frozen data.')
    dest.mkdir(parents=True)
    counts={};hashes={};unique={}
    for split in ['train','eval','test']:
        rows=[]
        for old in map(json.loads,(source/f'{split}.jsonl').read_text(encoding='utf-8').splitlines()):
            row=dict(old,id=old['id'].replace('v6-','v7-',1))
            if old['rubric']['full_solution']:
                target=old['messages'][-1]['content']
                assert target.count('```cpp\n'+old['gold_code']+'```')==1
                # Preserve exact prompt bytes; only repair assistant formatting.
                formatted=format_cpp(old['gold_code'])
                target=target.replace('```cpp\n'+old['gold_code']+'```','```cpp\n'+formatted+'```')
                row['messages']=old['messages'][:-1]+[{'role':'assistant','content':target}]
                row['gold_code']=formatted
                row['original_gold_sha256']=hashlib.sha256(old['gold_code'].encode()).hexdigest()
            rows.append(row)
        unique[split]=len(rows)
        if split=='train':
            # Deliberate sampling weight, not additional independent examples.
            full=[r for r in rows if r['rubric']['full_solution']]
            rows.extend(dict(r,id=r['id']+f'-weight-{weight}',sampling_weight_copy=True) for weight in [2,3] for r in full)
        path=dest/f'{split}.jsonl'
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
        counts[split]=len(rows);hashes[split]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest=dict(version='quality-v7',source_manifest_sha256=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
        counts=counts,distinct_examples=unique,sha256=hashes,
        provenance='GPT/Codex-authored v6 revision; no API or independent teacher review',
        evaluation_scope='Dev-informed v6 revision. Same concepts and named dev/test instances; only assistant targets reformatted. Full training repairs sampled three times; counts are not independent data. No general accuracy claim.',
        changes=['All complete assistant C++ targets formatted and closing fences on separate lines.','Full-program training targets sampled three times; prompt and label duplicates are intentional.','No dev/test output added to training.','Original v6 files and reports retained.'])
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(manifest))

if __name__=='__main__':main()
