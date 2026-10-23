"""Explicit, bounded staging-only live-disable check. Never installs a module."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--stage-dir', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--disable-after', type=int, default=75)
    parser.add_argument('--allow-staging-enable', action='store_true', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'/data/local/tmp/gxr-window-curvature-stage-[A-Za-z0-9_-]+', args.stage_dir):
        parser.error('Only an explicitly named temporary staging directory is permitted')
    if not 30 <= args.disable_after <= 120:
        parser.error('--disable-after must be 30..120')
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    adb = ['adb', '-s', args.serial]

    def run(*command, timeout=30):
        return subprocess.run(adb + list(command), capture_output=True, text=True,
            timeout=timeout, check=True).stdout

    def shell(command, timeout=30):
        return run('shell', command, timeout=timeout)

    stage = args.stage_dir
    for marker in ('injected-identity', 'session-open', 'failure'):
        shell(f'su 0 test ! -e {stage}/{marker}')
    before = {name: shell('pidof ' + name).strip()
        for name in ('com.android.systemui', 'com.android.spaceflinger')}
    baseline = run('shell', 'su', '0', 'dumpsys', 'spf_cpm')
    if any(float(value) != 0 for value in re.findall(r'cylinderCurvature=([-\d.]+)', baseline)):
        raise RuntimeError('Smoke fixture must start flat; no staging activation performed')
    shell(f'su 0 rm {stage}/disable')
    result = {'serial': args.serial, 'stage': stage, 'beforePids': before, 'disableAfter': args.disable_after}
    stop_result = {}

    def disable():
        try:
            stop_result['output'] = shell(f'su 0 sh {stage}/action.sh off', timeout=35)
        except Exception as error:
            stop_result['error'] = str(error)

    timer = threading.Timer(args.disable_after, disable)
    timer.start()
    process = subprocess.Popen(adb + ['shell', f'su 0 sh {stage}/control.sh run 180'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    started = time.monotonic()
    try:
        stdout, stderr = process.communicate(timeout=args.disable_after + 55)
        result.update({'returnCode': process.returncode, 'stdout': stdout, 'stderr': stderr})
    finally:
        timer.cancel()
        timer.join()
        if process.poll() is None:
            disable()
            process.terminate()
        # Even an early loader failure leaves this staging copy disabled.
        shell(f'su 0 touch {stage}/disable')
    result['elapsedSeconds'] = time.monotonic() - started
    result['liveDisable'] = stop_result
    result['log'] = shell(f'su 0 cat {stage}/runtime.log')
    result['status'] = shell(f'su 0 sh {stage}/action.sh status')
    result['afterPids'] = {name: shell('pidof ' + name).strip() for name in before}
    after = run('shell', 'su', '0', 'dumpsys', 'spf_cpm')
    result['nonzeroAfter'] = [float(value) for value in re.findall(r'cylinderCurvature=([-\d.]+)', after) if float(value) != 0]
    states = [json.loads(line.split(' ', 1)[1]) for line in result['log'].splitlines()
        if line.startswith('GXR_CURVATURE_STATE ')]
    result['curvedTaskIds'] = sorted({task['taskId'] for state in states for task in state['tasks'] if task['curvature'] > 0})
    path = args.output / (stamp + '-module-live-disable.json')
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (args.output / (stamp + '-module-live-disable-after-spf.txt')).write_text(after, encoding='utf-8')
    assert result['returnCode'] == 0 and before == result['afterPids'], 'Process failure/restart; inspect evidence'
    assert not result['nonzeroAfter'], 'Final compositor is not flat'
    assert 'GXR_UPDATE_STATE=STOCK' in result['status'], 'GXR lifecycle restoration protocol not satisfied'
    assert 'GXR_UPDATE_STATE=STOCK' in stop_result.get('output', ''), 'Live disable was not verified'
    assert result['curvedTaskIds'], 'No user-applied curve was observed; not a functional smoke pass'
    print('PASS: live disable, flat compositor, GXR restoration status, unchanged PIDs')
    print('Curved tasks:', result['curvedTaskIds'])
    print('Evidence:', path)


if __name__ == '__main__':
    main()
