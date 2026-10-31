"""Local development judge. Student code is never executed on the Windows host."""
import json
import shutil
import subprocess
import uuid

def normalize(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').rstrip()

def compare_results(payload, tests):
    compilation = payload['compile']
    if compilation['timeout']:
        return {'status': 'compile_timeout', 'label': '編譯超時', 'compiler': compilation['stderr'], 'cases': []}
    if compilation['returncode'] != 0:
        return {'status': 'compile_error', 'label': '編譯錯誤', 'compiler': compilation['stderr'], 'cases': []}
    runs = payload['runs']
    if len(runs) != len(tests):
        raise ValueError('incomplete runs')
    cases = []
    labels = {'accepted': '通過', 'wrong_answer': '答案不符', 'time_limit': '執行超時', 'output_limit': '輸出超限', 'runtime_error': '執行錯誤'}
    for case, run in zip(tests, runs):
        status = 'time_limit' if run['timeout'] else 'output_limit' if run['output_limit'] else 'runtime_error' if run['returncode'] != 0 else 'accepted' if normalize(run['stdout']) == normalize(case['expected']) else 'wrong_answer'
        cases.append({'name': case['name'], 'input': case['input'], 'expected': case['expected'], 'actual': run['stdout'], 'stderr': run['stderr'], 'status': status, 'label': labels[status], 'seconds': run['seconds']})
    passed = sum(c['status'] == 'accepted' for c in cases)
    return {'status': 'accepted' if passed == len(cases) else 'failed', 'label': f'測資通過 {passed} / {len(cases)}', 'compiler': compilation['stderr'], 'cases': cases, 'note': '只代表通過本次提供的測資，不保證所有輸入皆正確。忽略輸出結尾空白，其他內容逐字比較。'}

def judge(code, tests):
    if not shutil.which('docker'):
        return {'status': 'unavailable', 'label': '尚未執行：未找到 Docker', 'note': '請先安裝並啟動 Docker Desktop（Linux containers），再建立 cpe-judge:local 映像。', 'cases': []}
    name = 'cpe-judge-' + uuid.uuid4().hex
    args = ['docker', 'run', '--rm', '-i', '--name', name, '--network', 'none', '--memory', '256m', '--memory-swap', '256m', '--cpus', '1', '--pids-limit', '32', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/work:rw,exec,nosuid,size=64m,mode=1777', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,mode=1777', '--log-driver', 'none', '--pull', 'never', 'cpe-judge:local']
    try:
        result = subprocess.run(args, input=json.dumps({'code': code, 'tests': tests}), text=True, encoding='utf-8', capture_output=True, timeout=45)
        if result.returncode != 0:
            return {'status': 'system_error', 'label': '判題環境未就緒或程序異常', 'note': '確認 Docker Desktop 已啟動、映像已建置。若已就緒，程式也可能超出記憶體或容器資源限制。', 'cases': []}
        return compare_results(json.loads(result.stdout), tests)
    except subprocess.TimeoutExpired:
        return {'status': 'system_timeout', 'label': '判題工作總時限已到', 'cases': []}
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'system_error', 'label': '判題回應無法解析或服務不可用', 'cases': []}
    finally:
        try:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
