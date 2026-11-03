"""Runs only inside the disposable, restricted Linux container."""
import json
import os
import resource
import subprocess
import tempfile
import time

LIMIT = 65536

def limits(file_limit=LIMIT):
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def execute(args, stdin, timeout, file_limit=LIMIT):
    started = time.monotonic()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=out, stderr=err, preexec_fn=lambda: limits(file_limit), start_new_session=True)
        timed_out = False
        try:
            process.communicate(stdin.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            try:
                os.killpg(process.pid, 9)
            except ProcessLookupError:
                pass
            process.wait()
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(LIMIT).decode('utf-8', errors='replace'), err.read(LIMIT).decode('utf-8', errors='replace')
        return {'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr, 'timeout': timed_out, 'output_limit': len(stdout.encode()) >= LIMIT or len(stderr.encode()) >= LIMIT, 'seconds': round(time.monotonic() - started, 3)}

def main():
    payload = json.loads(input())
    with open('main.cpp', 'w', encoding='utf-8') as stream:
        stream.write(payload['code'])
    # Template-heavy STL programs can produce object files much larger than stdout.
    # Keep runtime files capped at 64 KiB; permit compiler artifacts up to 16 MiB.
    compilation = execute(['g++', '-std=c++17', '-O0', '-pipe', 'main.cpp', '-o', 'program'], '', 15, file_limit=16 * 1024 * 1024)
    if compilation['returncode'] != 0 or compilation['timeout']:
        return {'compile': compilation, 'runs': []}
    runs = []
    for index, case in enumerate(payload['tests']):
        # Each execution gets a separate working directory.
        with tempfile.TemporaryDirectory(dir='/work') as folder:
            original = os.getcwd()
            os.chdir(folder)
            try:
                runs.append(execute(['/work/program'], case['input'], 2))
            finally:
                os.chdir(original)
    return {'compile': compilation, 'runs': runs}

if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False))
