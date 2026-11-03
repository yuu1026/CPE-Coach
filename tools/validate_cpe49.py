"""Compile project-authored reference programs inside the existing Docker judge.

These are maintainer fixtures, never returned by the student UI or model payload.
The fixed expected outputs in cpe49.json were written separately from these programs.
Run: python tools/validate_cpe49.py (requires docker and cpe-judge:local).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from coach.judging import judge

HEAD = '#include <bits/stdc++.h>\nusing namespace std;\n'
REFERENCES = {
100: r'''int main(){long long i,j;while(cin>>i>>j){int best=0;for(long long x=min(i,j);x<=max(i,j);x++){long long v=x;int n=1;while(v!=1){v=v%2?3*v+1:v/2;n++;}best=max(best,n);}cout<<i<<" "<<j<<" "<<best<<"\n";}}''',
118: r'''int main(){int X,Y,x,y;cin>>X>>Y;char d;string cmd,dirs="NESW";set<pair<int,int>> scent;int dx[]={0,1,0,-1},dy[]={1,0,-1,0};while(cin>>x>>y>>d>>cmd){int k=dirs.find(d);bool lost=false;for(char c:cmd){if(c=='L')k=(k+3)%4;else if(c=='R')k=(k+1)%4;else{int a=x+dx[k],b=y+dy[k];if(a<0||a>X||b<0||b>Y){if(!scent.count({x,y})){scent.insert({x,y});lost=true;break;}}else{x=a;y=b;}}}cout<<x<<" "<<y<<" "<<dirs[k]<<(lost?" LOST":"")<<"\n";}}''',
299: r'''int main(){int T,n;cin>>T;while(T--){cin>>n;vector<int>a(n);for(int&v:a)cin>>v;int s=0;for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)s+=a[i]>a[j];cout<<"Optimal train swapping takes "<<s<<" swaps.\n";}}''',
490: r'''int main(){vector<string>a;string s;size_t w=0;while(getline(cin,s)){a.push_back(s);w=max(w,s.size());}for(size_t j=0;j<w;j++){for(int i=(int)a.size()-1;i>=0;i--)cout<<(j<a[i].size()?a[i][j]:' ');cout<<"\n";}}''',
948: r'''int main(){vector<int>f={1,2};while(f.back()<100000000)f.push_back(f.back()+f[f.size()-2]);int T,n;cin>>T;while(T--){cin>>n;cout<<n<<" = ";bool start=false;for(int i=f.size()-1;i>=0;i--){if(f[i]<=n){cout<<1;n-=f[i];start=true;}else if(start)cout<<0;}cout<<" (fib)\n";}}''',
10008: r'''int main(){int n;cin>>n;string s;getline(cin,s);int a[26]={};while(n--&&getline(cin,s))for(unsigned char c:s){if(c>='a'&&c<='z')c-=32;if(c>='A'&&c<='Z')a[c-'A']++;}vector<int>v(26);iota(v.begin(),v.end(),0);sort(v.begin(),v.end(),[&](int x,int y){return a[x]!=a[y]?a[x]>a[y]:x<y;});for(int i:v)if(a[i])cout<<char('A'+i)<<" "<<a[i]<<"\n";}''',
10019: r'''int main(){int T;cin>>T;string s;while(T--){cin>>s;cout<<__builtin_popcount(stoul(s,0,10))<<" "<<__builtin_popcount(stoul(s,0,16))<<"\n";}}''',
10050: r'''int main(){int T,N,P,h;cin>>T;while(T--){cin>>N>>P;vector<bool>d(N+1);while(P--){cin>>h;for(int i=h;i<=N;i+=h)if(i%7!=6&&i%7!=0)d[i]=true;}cout<<count(d.begin(),d.end(),true)<<"\n";}}''',
10056: r'''int main(){int T,N,I;double p;cin>>T;cout<<fixed<<setprecision(4);while(T--){cin>>N>>p>>I;cout<<(p==0?0:p*pow(1-p,I-1)/(1-pow(1-p,N)))<<"\n";}}''',
10057: r'''int main(){int n;while(cin>>n){vector<int>a(n);for(int&x:a)cin>>x;sort(a.begin(),a.end());int lo=a[(n-1)/2],hi=a[n/2];cout<<lo<<" "<<count_if(a.begin(),a.end(),[&](int x){return lo<=x&&x<=hi;})<<" "<<hi-lo+1<<"\n";}}''',
10062: r'''int main(){string s;bool first=true;while(getline(cin,s)){if(!first)cout<<"\n";first=false;map<int,int>m;for(unsigned char c:s)if(c!='\r')m[c]++;vector<pair<int,int>>v(m.begin(),m.end());sort(v.begin(),v.end(),[](auto a,auto b){return a.second!=b.second?a.second<b.second:a.first>b.first;});for(auto [c,n]:v)cout<<c<<" "<<n<<"\n";}}''',
10093: r'''int main(){string s,d="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";while(cin>>s){int mx=0,sum=0;for(char c:s){auto k=d.find(c);if(k!=string::npos){sum+=k;mx=max(mx,(int)k);}}int ans=0;for(int b=max(2,mx+1);b<=62;b++)if(sum%(b-1)==0){ans=b;break;}if(ans)cout<<ans<<"\n";else cout<<"such number is impossible!\n";}}''',
10101: r'''void say(long long n){if(n>=10000000){say(n/10000000);cout<<" kuti";n%=10000000;}for(auto [unit,name]:vector<pair<long long,string>>{{100000,"lakh"},{1000,"hajar"},{100,"shata"}})if(n>=unit){cout<<" "<<n/unit<<" "<<name;n%=unit;}if(n)cout<<" "<<n;}int main(){long long n;int k=0;while(cin>>n){cout<<setw(4)<<++k<<".";if(!n)cout<<" 0";else say(n);cout<<"\n";}}''',
10170: r'''int main(){long long s,d;while(cin>>s>>d){long long l=s,r=2000000000LL;while(l<r){long long m=(l+r)/2;__int128 total=(__int128)(s+m)*(m-s+1)/2;if(total>=d)r=m;else l=m+1;}cout<<l<<"\n";}}''',
10189: r'''int main(){int n,m,k=0;while(cin>>n>>m&&(n||m)){vector<string>a(n);for(auto&s:a)cin>>s;if(k)cout<<"\n";cout<<"Field #"<<++k<<":\n";for(int i=0;i<n;i++){for(int j=0;j<m;j++){if(a[i][j]=='*'){cout<<'*';continue;}int z=0;for(int x=max(0,i-1);x<=min(n-1,i+1);x++)for(int y=max(0,j-1);y<=min(m-1,j+1);y++)z+=a[x][y]=='*';cout<<z;}cout<<"\n";}}}''',
10190: r'''int main(){long long n,m;while(cin>>n>>m){vector<long long>a;bool ok=n>1&&m>1;while(ok&&n>1){a.push_back(n);if(n%m){ok=false;break;}n/=m;}if(!ok)cout<<"Boring!\n";else{a.push_back(1);for(int i=0;i<(int)a.size();i++)cout<<(i?" ":"")<<a[i];cout<<"\n";}}}''',
10193: r'''int main(){int T;cin>>T;string a,b;for(int k=1;k<=T;k++){cin>>a>>b;cout<<"Pair #"<<k<<": "<<(gcd(stoll(a,0,2),stoll(b,0,2))>1?"All you need is love!":"Love is not all you need!")<<"\n";}}''',
10221: r'''int main(){double s,a;string u;cout<<fixed<<setprecision(6);while(cin>>s>>a>>u){if(u=="min")a/=60;a=fmod(a,360);a=min(a,360-a);double r=s+6440,t=a*acos(-1.0)/180;cout<<r*t<<" "<<2*r*sin(t/2)<<"\n";}}''',
10222: r'''int main(){vector<string>rows={"`1234567890-=","qwertyuiop[]\\","asdfghjkl;'","zxcvbnm,./"};string s;while(getline(cin,s)){for(unsigned char c:s){if(c==' '){cout<<' ';continue;}c=tolower(c);for(auto&r:rows){auto i=r.find(c);if(i!=string::npos&&i>=2){cout<<r[i-2];break;}}}cout<<"\n";}}''',
10226: r'''int main(){int T;cin>>T;string s;getline(cin,s);cout<<fixed<<setprecision(4);for(int k=0;k<T;k++){map<string,int>m;int n=0;while(getline(cin,s)&&s.empty()){}if(cin||!s.empty()){if(!s.empty()){m[s]++;n++;}while(getline(cin,s)&&!s.empty()){m[s]++;n++;}}if(k)cout<<"\n";for(auto [name,v]:m)cout<<name<<" "<<v*100.0/n<<"\n";}}''',
10235: r'''bool prime(int n){if(n<2)return false;for(int i=2;i<=n/i;i++)if(n%i==0)return false;return true;}int main(){int n;while(cin>>n){string s=to_string(n);reverse(s.begin(),s.end());int r=stoi(s);cout<<n<<" is "<<(!prime(n)?"not prime.":r!=n&&prime(r)?"emirp.":"prime.")<<"\n";}}''',
10242: r'''int main(){double a[8];cout<<fixed<<setprecision(3);while(cin>>a[0]){for(int i=1;i<8;i++)cin>>a[i];for(int i=0;i<2;i++)for(int j=2;j<4;j++)if(a[2*i]==a[2*j]&&a[2*i+1]==a[2*j+1]){double x=a[2*(1-i)]+a[2*(5-j)]-a[2*i],y=a[2*(1-i)+1]+a[2*(5-j)+1]-a[2*i+1];cout<<x<<" "<<y<<"\n";}}}''',
10252: r'''int main(){string a,b;while(getline(cin,a)&&getline(cin,b)){int x[26]={},y[26]={};for(char c:a)x[c-'a']++;for(char c:b)y[c-'a']++;for(int i=0;i<26;i++)cout<<string(min(x[i],y[i]),'a'+i);cout<<"\n";}}''',
10268: r'''int main(){long long x;string s;while(cin>>x){getline(cin,s);getline(cin,s);istringstream in(s);vector<long long>a;long long v;while(in>>v)a.push_back(v);long long ans=0;int n=a.size()-1;for(int i=0;i<n;i++)ans=ans*x+a[i]*(n-i);cout<<ans<<"\n";}}''',
10409: r'''int main(){int n;string s;while(cin>>n&&n){int t=1,b=6,N=2,S=5,W=3,E=4;while(n--){cin>>s;int v=t;if(s=="north"){t=S;S=b;b=N;N=v;}if(s=="south"){t=N;N=b;b=S;S=v;}if(s=="east"){t=W;W=b;b=E;E=v;}if(s=="west"){t=E;E=b;b=W;W=v;}}cout<<t<<"\n";}}''',
10415: r'''int main(){map<char,vector<int>>m={{'c',{2,3,4,7,8,9,10}},{'d',{2,3,4,7,8,9}},{'e',{2,3,4,7,8}},{'f',{2,3,4,7}},{'g',{2,3,4}},{'a',{2,3}},{'b',{2}},{'C',{3}},{'D',{1,2,3,4,7,8,9}},{'E',{1,2,3,4,7,8}},{'F',{1,2,3,4,7}},{'G',{1,2,3,4}},{'A',{1,2,3}},{'B',{1,2}}};int T;cin>>T;string s;getline(cin,s);while(T--){getline(cin,s);vector<int>cnt(11),prev(11);for(char c:s){vector<int>now(11);for(int i:m[c]){now[i]=1;if(!prev[i])cnt[i]++;}prev=now;}for(int i=1;i<=10;i++)cout<<(i>1?" ":"")<<cnt[i];cout<<"\n";}}''',
10420: r'''int main(){int n;cin>>n;string s;getline(cin,s);map<string,int>m;while(n--){getline(cin,s);istringstream in(s);string c;in>>c;m[c]++;}for(auto[c,k]:m)cout<<c<<" "<<k<<"\n";}''',
10642: r'''long long indexof(long long x,long long y){return (x+y)*(x+y+1)/2+x;}int main(){int T;cin>>T;for(int k=1;k<=T;k++){long long a,b,c,d;cin>>a>>b>>c>>d;cout<<"Case "<<k<<": "<<indexof(c,d)-indexof(a,b)<<"\n";}}''',
10908: r'''int main(){int T;cin>>T;while(T--){int m,n,q;cin>>m>>n>>q;cout<<m<<" "<<n<<" "<<q<<"\n";vector<string>a(m);for(auto&s:a)cin>>s;while(q--){int r,c;cin>>r>>c;int best=1;for(int d=1;r-d>=0&&r+d<m&&c-d>=0&&c+d<n;d++){bool ok=true;for(int i=r-d;i<=r+d;i++)for(int j=c-d;j<=c+d;j++)if(a[i][j]!=a[r][c])ok=false;if(!ok)break;best=2*d+1;}cout<<best<<"\n";}}}''',
10922: r'''int main(){string s;while(cin>>s&&s!="0"){string v=s;int sum=0;for(char c:v)sum+=c-'0';if(sum%9){cout<<s<<" is not a multiple of 9.\n";continue;}int d=1;while(sum>9){int x=0;while(sum){x+=sum%10;sum/=10;}sum=x;d++;}cout<<s<<" is a multiple of 9 and has 9-degree "<<d<<".\n";}}''',
10929: r'''int main(){string s;while(cin>>s&&s!="0"){int r=0;for(char c:s)r=(r*10+c-'0')%11;cout<<s<<(r?" is not a multiple of 11.":" is a multiple of 11.")<<"\n";}}''',
11005: r'''int main(){int T;cin>>T;for(int k=1;k<=T;k++){vector<int>cost(36);for(int&c:cost)cin>>c;int q;cin>>q;if(k>1)cout<<"\n";cout<<"Case "<<k<<":\n";while(q--){long long n;cin>>n;int best=INT_MAX;vector<int>bases;for(int b=2;b<=36;b++){long long x=n;int total=0;do{total+=cost[x%b];x/=b;}while(x);if(total<best){best=total;bases.clear();}if(total==best)bases.push_back(b);}cout<<"Cheapest base(s) for number "<<n<<":";for(int b:bases)cout<<" "<<b;cout<<"\n";}}}''',
11063: r'''int main(){int n,k=0;while(cin>>n){vector<int>a(n);bool ok=true;for(int i=0;i<n;i++){cin>>a[i];if(a[i]<1||(i&&a[i]<=a[i-1]))ok=false;}set<int>s;for(int i=0;i<n;i++)for(int j=i;j<n;j++)if(!s.insert(a[i]+a[j]).second)ok=false;cout<<"Case #"<<++k<<": It is "<<(ok?"":"not ")<<"a B2-Sequence.\n\n";}}''',
11150: r'''int main(){int n;while(cin>>n){int best=n;for(int loan=0;loan<=2;loan++){int empty=n+loan,drank=n;while(empty>=3){int more=empty/3;drank+=more;empty=empty%3+more;}if(empty>=loan)best=max(best,drank);}cout<<best<<"\n";}}''',
11321: r'''int main(){int n,m;while(cin>>n>>m){cout<<n<<" "<<m<<"\n";if(!n&&!m)break;vector<int>a(n);for(int&x:a)cin>>x;sort(a.begin(),a.end(),[&](int x,int y){if(x%m!=y%m)return x%m<y%m;bool a=x%2!=0,b=y%2!=0;if(a!=b)return a;return a?x>y:x<y;});for(int x:a)cout<<x<<"\n";}}''',
11349: r'''int main(){int T;cin>>T;for(int k=1;k<=T;k++){string s,e;int n;cin>>s>>e>>n;vector<long long>a(n*n);bool ok=true;for(auto&x:a){cin>>x;if(x<0)ok=false;}for(int i=0;i<n*n;i++)if(a[i]!=a[n*n-1-i])ok=false;cout<<"Test #"<<k<<": "<<(ok?"Symmetric.":"Non-symmetric.")<<"\n";}}''',
11417: r'''int main(){int n;while(cin>>n&&n){long long s=0;for(int i=1;i<n;i++)for(int j=i+1;j<=n;j++)s+=gcd(i,j);cout<<s<<"\n";}}''',
11461: r'''int main(){int a,b;while(cin>>a>>b&&(a||b)){int ans=0;for(int i=1;i*i<=b;i++)ans+=i*i>=a;cout<<ans<<"\n";}}''',
12019: r'''int main(){int T,m,d;cin>>T;int days[]={31,28,31,30,31,30,31,31,30,31,30,31};string names[]={"Saturday","Sunday","Monday","Tuesday","Wednesday","Thursday","Friday"};while(T--){cin>>m>>d;int n=d-1;for(int i=0;i<m-1;i++)n+=days[i];cout<<names[n%7]<<"\n";}}''',
}


def main():
    catalog = json.loads((ROOT / 'data/cpe49.json').read_text(encoding='utf-8'))
    originals = {p['uva']: p['code'] for p in json.loads((ROOT / 'training/data/problems.json').read_text(encoding='utf-8'))}
    report = []
    failures = []
    for item in catalog:
        number = item['uva']
        code = originals[number] if number in originals else HEAD + REFERENCES[number]
        result = judge(code, item['tests'])
        entry = {'uva': number, 'status': result['status'], 'cases': len(result.get('cases', []))}
        report.append(entry)
        print(entry, flush=True)
        if result['status'] != 'accepted':
            print(json.dumps(result, ensure_ascii=False), flush=True)
            failures.append(number)
    if failures:
        raise SystemExit(f'Validation failed for {failures}; no success report written.')
    target = ROOT / 'data/cpe49-validation.json'
    target.write_text(json.dumps({'method': 'project-authored C++17 reference programs, Docker cpe-judge:local', 'note': 'Validates these authored test cases only; not official judge coverage or model evaluation.', 'topics': len(report), 'test_cases': sum(p['cases'] for p in report), 'results': report}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
