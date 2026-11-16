"""Additional numeric cases for the exact recorded learner program, no edits."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from coach.judging import judge


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refuse to overwrite evidence.')
    report=json.loads(args.report.read_text(encoding='utf-8'));last=report['steps'][-1]
    code=last['code'];topic=last.get('topic',10041)
    if not any(s.get('judge',{}).get('status')=='accepted' and s['code']==code for s in report['steps']):
        raise SystemExit('The current learner program has not passed topic tests; no silent repairs.')
    rng=random.Random(291116)
    if topic==10055:
        data=[(0,0),(1,0),(0,1),(2**32,0),(0,2**32),(2**32,2**32)]+[(rng.randint(0,2**32),rng.randint(0,2**32)) for _ in range(64)]
        inputs=''.join(f'{a} {b}\n' for a,b in data);values=[abs(a-b) for a,b in data]
        oracle='Python integer absolute difference; all data within the project statement.'
    elif topic==10041:
        data=[[1],[29999],[1,29999],[9,1,4],[7]*499,[2,2,2,2]]+[[rng.randint(1,90) for _ in range(rng.randint(1,30))] for _ in range(64)]
        inputs=str(len(data))+'\n'+''.join(str(len(xs))+' '+' '.join(map(str,xs))+'\n' for xs in data)
        values=[min(sum(abs(x-home) for x in xs) for home in range(min(xs),max(xs)+1)) for xs in data]
        oracle='Exhaustive enumeration of candidate homes, not the median rule.'
    else:raise SystemExit('No independent oracle for this topic.')
    test={'name':'70組額外數值案例','input':inputs,'expected':'\n'.join(map(str,values))+'\n'}
    result=judge(code,[test])
    output={'scope':'Seen-topic numerical generalization only; exact current learner code. No code edits or learner cognitive outcome measurement.',
            'topic':topic,'code':code,'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'count':len(data),
            'data':data,'expected_values':values,'oracle':oracle,'judge':result}
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'topic':topic,'count':len(data),'status':result['status']},ensure_ascii=True))
    return 0 if result['status']=='accepted' else 1


if __name__=='__main__':raise SystemExit(main())
