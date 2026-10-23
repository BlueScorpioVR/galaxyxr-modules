"""Build a disabled, firmware-pinned KernelSU window-curvature module."""
import argparse
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/window-curvature'
INJECT_SHA = 'fa27b0478fbe1909978388d606236008c40e19ffddcea3bca69a6ed54fde02dc'
BINARY_SHA = 'bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122'
BRIDGE_SHA512 = 'YSyKjxbxKnSi3KSUy9vciOvTOuq0RRh9dkxzkQVEdfIIZlw20zE8D3Cq9eL2FDqUVj4YKas6Wf09kCjL5zbffg=='


def fetch(cache, name, url):
    path = cache / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=90) as response:
            data = response.read()
        path.write_bytes(data)
    return path.read_bytes()


def build():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('java', 'ecj', 'r8', 'android-jar', 'cache'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    import frida
    if frida.__version__ != '17.23.3':
        parser.error('Build using Python with frida==17.23.3')
    args.cache.mkdir(parents=True, exist_ok=True)
    archive = fetch(args.cache, 'frida-inject-17.23.3-android-arm64.xz',
        'https://github.com/frida/frida/releases/download/17.23.3/frida-inject-17.23.3-android-arm64.xz')
    if hashlib.sha256(archive).hexdigest() != INJECT_SHA:
        raise ValueError('Injector archive integrity mismatch')
    binary = lzma.decompress(archive)
    if hashlib.sha256(binary).hexdigest() != BINARY_SHA:
        raise ValueError('Injector ELF integrity mismatch')
    if binary[:4] != b'\x7fELF' or int.from_bytes(binary[18:20], 'little') != 183:
        raise ValueError('Expected Android arm64 ELF')
    bridge = fetch(args.cache, 'frida-java-bridge-7.0.13.tgz',
        'https://registry.npmjs.org/frida-java-bridge/-/frida-java-bridge-7.0.13.tgz')
    if base64.b64encode(hashlib.sha512(bridge).digest()).decode() != BRIDGE_SHA512:
        raise ValueError('Java bridge npm integrity mismatch')
    payload = {name: (MODULE / name).read_bytes() for name in (
        'module.prop', 'disable', 'skip_mount', 'customize.sh', 'service.sh',
        'action.sh', 'auto.sh', 'uninstall.sh', 'control.sh', 'firmware.sha256',
        'install-info.txt', 'README.md', 'THIRD_PARTY.md')}
    assert payload['disable'] == payload['skip_mount'] == b''
    for name, data in payload.items():
        if b'\r' in data:
            raise ValueError('CRLF in ' + name)
    payload['bin/frida-inject'] = binary
    payload['bin/third-party/frida-java-bridge-7.0.13.tgz'] = bridge
    payload['bin/licenses/frida-COPYING'] = fetch(args.cache, 'frida-17.23.3-COPYING',
        'https://raw.githubusercontent.com/frida/frida-core/17.23.3/COPYING')
    payload['bin/licenses/LGPL-2.0-or-later.txt'] = fetch(args.cache, 'LGPL-2.0-or-later.txt',
        'https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/LGPL-2.0-or-later.txt')
    temp_root = Path.home() / 'AppData/Local/Temp/opencode'
    with tempfile.TemporaryDirectory(prefix='gxr-module-', dir=temp_root) as temporary:
        work = Path(temporary)
        dex_dir = work / 'dex'
        subprocess.run([
            sys.executable, str(ROOT / 'tools/build_window_curvature_helper.py'),
            '--java', str(args.java), '--ecj', str(args.ecj), '--r8', str(args.r8),
            '--android-jar', str(args.android_jar), '--output', str(dex_dir),
        ], check=True)
        dex = (dex_dir / 'classes.dex').read_bytes()
        payload['bin/classes.dex'] = dex
        helper_receipt = json.loads((dex_dir / 'build-receipt.json').read_text(encoding='utf-8'))
        # Public build receipts need hashes and tool names, not workstation paths.
        for dependency in helper_receipt['dependencies'].values():
            dependency['path'] = Path(dependency['path']).name
        payload['bin/source/helper-build.json'] = (json.dumps(helper_receipt, indent=2) + '\n').encode()
        agent = work / 'agent'
        agent.mkdir()
        for path in sorted((MODULE / 'agent').iterdir()):
            if path.is_file():
                shutil.copyfile(path, agent / path.name)
        (agent / 'helper-dex.js').write_text('export const DEX_BASE64 = ' +
            json.dumps(base64.b64encode(dex).decode()) + ';\n', encoding='utf-8')
        bridge_dir = agent / 'node_modules/frida-java-bridge'
        bridge_dir.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(bridge), mode='r:gz') as source:
            for member in source.getmembers():
                if not member.isfile():
                    continue
                relative = Path(member.name).relative_to('package')
                if '..' in relative.parts or relative.is_absolute():
                    raise ValueError('Unsafe npm archive member')
                destination = bridge_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.extractfile(member).read())
        diagnostics = []
        compiler = frida.Compiler()
        compiler.on('diagnostics', diagnostics.append)
        bundle = compiler.build('main.js', project_root=str(agent))
        if diagnostics:
            raise ValueError('Agent compiler diagnostics: ' + repr(diagnostics))
        payload['bin/agent.js'] = bundle.encode('utf-8')
    for directory in ('java', 'android', 'agent'):
        for path in sorted((MODULE / directory).rglob('*')):
            if path.is_file():
                payload['bin/source/' + path.relative_to(MODULE).as_posix()] = path.read_bytes()
    payload['bin/source/build_window_curvature.py'] = Path(__file__).read_bytes()
    payload['bin/source/build_window_curvature_helper.py'] = (ROOT / 'tools/build_window_curvature_helper.py').read_bytes()
    payload['build.json'] = (json.dumps({
        'kind': 'disabled-experimental-kernelsu-module', 'frida': frida.__version__,
        'injectorArchiveSha256': INJECT_SHA, 'injectorSha256': BINARY_SHA,
        'bridgeVersion': '7.0.13', 'bridgeSha512': BRIDGE_SHA512,
        'payloadSha256': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())},
    }, indent=2) + '\n').encode()
    payload['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
        for name, data in sorted(payload.items()) if name != 'disable').encode()
    props = dict(line.split('=', 1) for line in payload['module.prop'].decode().splitlines())
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / ('gxr-window-curvature-' + props['version'] + '-disabled.zip')
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as zip_file:
        for name, data in sorted(payload.items()):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            mode = 0o100755 if name.endswith('.sh') or name == 'bin/frida-inject' else 0o100644
            info.external_attr = mode << 16
            zip_file.writestr(info, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    updates = ROOT / 'updates'
    updates.mkdir(exist_ok=True)
    release_version = props['version'].removesuffix('-experimental')
    feed = {
        'version': props['version'], 'versionCode': int(props['versionCode']),
        'zipUrl': 'https://github.com/BlueScorpioVR/galaxyxr-modules/releases/download/'
                  f'window-curvature/v{release_version}/{output.name}',
        'changelog': 'https://raw.githubusercontent.com/BlueScorpioVR/galaxyxr-modules/main/changelogs/window-curvature.md',
        'sha256': digest,
    }
    (updates / 'window-curvature.json').write_text(json.dumps(feed, indent=2) + '\n', encoding='utf-8')
    print(output)
    print(digest)
    return output


if __name__ == '__main__':
    build()
