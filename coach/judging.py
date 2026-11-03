"""Local development judge. Student code is never executed on the Windows host."""
import json
import shutil
import subprocess
import uuid
import math
import os
from pathlib import Path


def docker_candidates():
    """Docker Desktop installs may not be in an already-running server's PATH."""
    if os.name != 'nt':
        return []
    candidates = []
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA']) / 'Programs/DockerDesktop/resources/bin/docker.exe')
    candidates.append(Path.home() / 'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe')
    if os.environ.get('ProgramFiles'):
        candidates.append(Path(os.environ['ProgramFiles']) / 'Docker/Docker/resources/bin/docker.exe')
    return candidates


def find_docker():
    override = os.environ.get('DOCKER_EXE')
    if override:
        return str(Path(override)) if Path(override).is_file() else None
    executable = shutil.which('docker')
    if executable:
        return executable
    return next((str(path) for path in docker_candidates() if path.is_file()), None)

def normalize(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').rstrip()

def matches(actual, expected, comparison='exact'):
    if comparison == 'line_rstrip':
        return normalize('\n'.join(line.rstrip(' \t') for line in actual.replace('\r\n', '\n').replace('\r', '\n').split('\n'))) == normalize('\n'.join(line.rstrip(' \t') for line in expected.replace('\r\n', '\n').replace('\r', '\n').split('\n')))
    if comparison == 'float_1e-6':
        try:
            left, right = [float(x) for x in actual.split()], [float(x) for x in expected.split()]
            return len(left) == len(right) and all(math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=0, abs_tol=1.000001e-6) for a, b in zip(left, right))
        except ValueError:
            return False
    return normalize(actual) == normalize(expected)

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
        status = 'time_limit' if run['timeout'] else 'output_limit' if run['output_limit'] else 'runtime_error' if run['returncode'] != 0 else 'accepted' if matches(run['stdout'], case['expected'], case.get('comparison', 'exact')) else 'wrong_answer'
        cases.append({'name': case['name'], 'input': case['input'], 'expected': case['expected'], 'actual': run['stdout'], 'stderr': run['stderr'], 'status': status, 'label': labels[status], 'seconds': run['seconds']})
    passed = sum(c['status'] == 'accepted' for c in cases)
    modes = {c.get('comparison', 'exact') for c in tests}
    policy = '忽略各行結尾空白，其餘內容逐字比較。' if modes == {'line_rstrip'} else '逐個數值比較，絕對誤差須不超過 0.000001。' if modes == {'float_1e-6'} else '忽略輸出結尾空白，其他內容逐字比較。'
    return {'status': 'accepted' if passed == len(cases) else 'failed', 'label': f'測資通過 {passed} / {len(cases)}', 'compiler': compilation['stderr'], 'cases': cases, 'note': '只代表通過本次提供的測資，不保證所有輸入皆正確。' + policy}

def judge(code, tests):
    executable = find_docker()
    if not executable:
        return {'status': 'unavailable', 'label': '尚未執行：未找到 Docker', 'note': '找不到 docker.exe。請安裝 Docker Desktop，或用 DOCKER_EXE 指定其完整路徑，再重新啟動網站。', 'cases': []}
    name = 'cpe-judge-' + uuid.uuid4().hex
    args = [executable, 'run', '--rm', '-i', '--name', name, '--network', 'none', '--memory', '256m', '--memory-swap', '256m', '--cpus', '1', '--pids-limit', '32', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/work:rw,exec,nosuid,size=64m,mode=1777', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,mode=1777', '--log-driver', 'none', '--pull', 'never', 'cpe-judge:local']
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
            subprocess.run([executable, 'rm', '-f', name], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
