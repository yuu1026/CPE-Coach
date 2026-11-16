"""Exercise project-authored safe C++ probes in Docker; do not execute UB."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from coach.judging import judge


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refuse to overwrite evidence')
    probes=[
        ('integer_division','int total=5,count=2;double average=total/count;std::cout<<average;','2','accepted'),
        ('floating_division','int total=5,count=2;double average=static_cast<double>(total)/count;std::cout<<average;','2.5','accepted'),
        ('safe_copy','int saved=0;if(true){int home=7;saved=home;}std::cout<<saved;','7','accepted'),
        ('promote_before_multiply','int x=100000,y=100000;long long area=1LL*x*y;std::cout<<area;','10000000000','accepted'),
        ('out_of_scope','if(true){int home=7;}std::cout<<home;','7','compile_error'),
        ('negative_integer_division','int a=-7,b=2;double result=a/b;std::cout<<result;','-3','accepted'),
    ]
    results=[]
    for name,body,expected,status in probes:
        code='#include <iostream>\nint main(){'+body+'}\n'
        result=judge(code,[{'name':name,'input':'','expected':expected}])
        results.append({'name':name,'code':code,'expected':expected,'expected_status':status,'judge':result,'passed':result['status']==status})
        print(name,result['status'],flush=True)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if all(r['passed'] for r in results) else 1


if __name__=='__main__':raise SystemExit(main())
