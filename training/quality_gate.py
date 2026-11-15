"""Fail-closed candidate decision. This never enables an adapter by itself."""
import argparse
import hashlib
import json
from pathlib import Path

def decide(dev, test, review):
    reasons=[]
    if dev.get('split')!='eval' or test.get('split')!='test': reasons.append('missing separate dev/test reports')
    if dev.get('adapter')!=test.get('adapter'): reasons.append('adapter mismatch')
    rows=dev.get('results',[])+test.get('results',[])
    indexed={row['id']:row for row in rows}
    reviewed={item['id']:item for item in review.get('cases',[])}
    if set(indexed)!=set(reviewed) or len(indexed)!=len(rows) or len(reviewed)!=len(review.get('cases',[])):
        reasons.append('review must cover each dev/test case exactly once')
    limitations=[]
    if review.get('independent_teacher_review') is not True:
        limitations.append('Review is GPT/Codex self-assessment, not independent teacher validation; do not report scores as independently verified accuracy.')
    for report in (dev,test):
        summary=report.get('summary',{}).get('adapter',{})
        if not summary.get('total') or summary.get('rule_passed',0)/summary['total']<.9:
            reasons.append(f"{report.get('split')}: fewer than 90% heuristic checks passed")
    gains=[]
    for identifier,item in reviewed.items():
        if identifier not in indexed: continue
        base=item.get('base_score',0); adapter=item.get('adapter_score',0)
        if type(base) not in (int,float) or type(adapter) not in (int,float) or not 0<=base<=5 or not 0<=adapter<=5:
            reasons.append(f'{identifier}: invalid score'); continue
        if adapter<4 or item.get('adapter_critical_errors'):
            reasons.append(f'{identifier}: semantic quality or critical error gate failed')
        gains.append(adapter-base)
    if not gains or sum(gains)/len(gains)<.25: reasons.append('mean semantic review gain is below 0.25/5')
    return {'eligible_for_manual_deployment':not reasons,'decision':'candidate eligible for manual deployment' if not reasons else 'keep current deployment',
        'reasons':reasons,'review_kind':review.get('review_kind','unspecified'),
        'limitations':limitations,
        'scope':'Small project-authored benchmark. Heuristic pass rate and GPT/Codex self-review are not independent semantic accuracy.'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dev',type=Path,required=True); parser.add_argument('--test',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=decide(*(json.loads(path.read_text(encoding='utf-8')) for path in (args.dev,args.test,args.review)))
    result['report_sha256']={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in [('dev',args.dev),('test',args.test),('review',args.review)]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
