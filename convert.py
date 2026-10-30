#!/usr/bin/env python3
"""Convert a user-supplied, unencrypted Null's Royale ARM64 IPA to Mac Catalyst."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
MAGICS = (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca')
MINIMUM = '17.0'


def run(*args):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]}\n{result.stdout.strip()}")
    return result.stdout.strip()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def commands(data):
    if len(data) < 32 or data[:4] != MAGICS[0]:
        raise ValueError('Expected a thin little-endian 64-bit Mach-O')
    count, size = struct.unpack_from('<II', data, 16)
    end = 32 + size
    if end > len(data):
        raise ValueError('Truncated Mach-O load commands')
    offset = 32
    for _ in range(count):
        if offset + 8 > end:
            raise ValueError('Truncated load command')
        kind, length = struct.unpack_from('<II', data, offset)
        if length < 8 or offset + length > end:
            raise ValueError('Invalid load command size')
        yield kind, offset, length
        offset += length
    if offset != end:
        raise ValueError('Inconsistent load command size')


def sections(data):
    """Capture all file-backed sections; conversion must leave them unchanged."""
    result = {}
    for kind, offset, length in commands(data):
        if kind != 0x19:
            continue
        count = struct.unpack_from('<I', data, offset + 64)[0]
        if 72 + count * 80 > length:
            raise ValueError('Truncated section table')
        for i in range(count):
            p = offset + 72 + i * 80
            section = data[p:p + 16].split(b'\0')[0].decode()
            segment = data[p + 16:p + 32].split(b'\0')[0].decode()
            address, size, start = struct.unpack_from('<QQI', data, p + 32)
            flags = struct.unpack_from('<I', data, p + 64)[0]
            if flags & 0xff in (1, 12, 18):  # zero-fill sections have no file bytes
                continue
            if start + size > len(data):
                raise ValueError('Section extends past end of file')
            result[f'{segment},{section}'] = (address, size, hashlib.sha256(data[start:start + size]).hexdigest())
    return result


def inject(path, library):
    data = bytearray(path.read_bytes())
    first_section = len(data)
    for kind, offset, length in commands(data):
        if kind == 0xc:
            start = struct.unpack_from('<I', data, offset + 8)[0]
            if data[offset + start:offset + length].split(b'\0')[0].decode() == library:
                return
        if kind == 0x19:
            count = struct.unpack_from('<I', data, offset + 64)[0]
            for i in range(count):
                start = struct.unpack_from('<I', data, offset + 72 + i * 80 + 48)[0]
                if start:
                    first_section = min(first_section, start)
    count, size = struct.unpack_from('<II', data, 16)
    name = library.encode() + b'\0'
    length = (24 + len(name) + 7) & ~7
    end = 32 + size
    if end + length > first_section or any(data[end:end + length]):
        raise ValueError('Insufficient Mach-O header padding for shim; this IPA is unsupported')
    command = struct.pack('<6I', 0xc, length, 24, 2, 0x10000, 0x10000) + name
    data[end:end + length] = command.ljust(length, b'\0')
    struct.pack_into('<II', data, 16, count + 1, size + length)
    path.write_bytes(data)


def extract(ipa, output):
    with zipfile.ZipFile(ipa) as archive:
        seen = set()
        for entry in archive.infolist():
            target = (output / entry.filename).resolve()
            if not target.is_relative_to(output) or target in seen:
                raise ValueError(f'Unsafe or duplicate ZIP member: {entry.filename}')
            seen.add(target)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f'ZIP symlinks are unsupported: {entry.filename}')
        archive.extractall(output)
    apps = list((output / 'Payload').glob('*.app'))
    if len(apps) != 1:
        raise ValueError('IPA must contain exactly one Payload/*.app')
    return apps[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ipa', type=Path, help='original, unencrypted IPA; never modified')
    parser.add_argument('--output', type=Path, required=True, help='new directory; never overwrite an existing output')
    parser.add_argument('--bundle-id', default='local.nullsroyale.mac', help='keep stable to retain the same sandbox/account data')
    parser.add_argument('--name', default="Null's Royale", help='application display name')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('Run on an Apple Silicon Mac, using native ARM64 Python')
    if not args.ipa.is_file():
        parser.error('IPA does not exist')
    if not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', args.bundle_id):
        parser.error('Invalid bundle identifier')
    ipa, output = args.ipa.resolve(), args.output.expanduser().resolve()
    if output.exists():
        parser.error('Output already exists; choose a new directory')
    for tool in ('xcrun', 'codesign', 'xattr'):
        if not shutil.which(tool):
            parser.error(f'Missing tool: {tool}')
    sdk = Path(run('xcrun', '--sdk', 'macosx', '--show-sdk-path'))
    support = sdk / 'System/iOSSupport'
    if not (support / 'System/Library/Frameworks/UIKit.framework').exists():
        parser.error('Full Xcode with the Mac Catalyst SDK is required; Command Line Tools alone are insufficient')
    for tool in ('clang', 'clang++', 'vtool', 'otool', 'lipo', 'install_name_tool'):
        run('xcrun', '--find', tool)
    # https://github.com/ayush5harma/ipa-install-on-mac
    # lib/ipa-keychain.c at f102181b711d6c06c1e42691640dbdade0fc4569 (MIT; LICENSE.keychain)
    source = ROOT
    expected = '26d11a5cd9080baffb3810a6f5ac060bbedf80bc4aa3fc32599969f90536e7c5'
    if digest(source / 'ipa-keychain.c') != expected:
        raise ValueError('Keychain source differs from the pinned upstream version')
    output.mkdir(parents=True, exist_ok=False)
    print('Extracting a new copy...', flush=True)
    app = extract(ipa, output)
    if list(app.rglob('*.appex')):
        raise ValueError('App extensions are unsupported by this converter')
    info_path = app / 'Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    executable = app / info['CFBundleExecutable']
    if executable.parent != app or not executable.is_file():
        raise ValueError('Invalid main executable')
    if (app / 'firstlight_probe.json').exists() or any(app.rglob('libfirstlight*.dylib')):
        raise ValueError('Use the original IPA, not a previously instrumented build')
    original_files = {str(p.relative_to(app)): digest(p) for p in app.rglob('*') if p.is_file()}
    binaries = []
    baselines = {}
    records = []
    for path in sorted(app.rglob('*')):
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in MAGICS:
                continue
        arches = run('xcrun', 'lipo', '-archs', path).split()
        if 'arm64' not in arches:
            raise ValueError(f'No ARM64 slice: {path.name}')
        temporary = path.with_name(path.name + '.converted')
        if len(arches) > 1:
            run('xcrun', 'lipo', path, '-thin', 'arm64', '-output', temporary)
            temporary.replace(path)
        baseline = sections(path.read_bytes())
        listing = run('xcrun', 'otool', '-l', path)
        if re.search(r'cryptid\s+[1-9]', listing):
            raise ValueError(f'Encrypted binary: {path.name}; decryption is not provided')
        version = re.search(r'\bsdk\s+([\d.]+)', listing)
        run('xcrun', 'vtool', '-set-build-version', 'maccatalyst', MINIMUM,
            version[1] if version else MINIMUM, '-replace', '-output', temporary, path)
        temporary.replace(path)
        dependencies = run('xcrun', 'otool', '-L', path)
        replaced = []
        for old in ('@rpath/libswiftUIKit.dylib', '/usr/lib/swift/libswiftUIKit.dylib'):
            if old in dependencies:
                run('xcrun', 'install_name_tool', '-change', old,
                    '/System/iOSSupport/usr/lib/swift/libswiftUIKit.dylib', path)
                replaced.append(old)
        path.chmod(0o755)
        baselines[path] = baseline
        binaries.append(path)
        records.append({'path': str(path.relative_to(app)), 'original_architectures': arches,
                        'swift_uikit_paths_replaced': replaced})
    if executable not in binaries:
        raise ValueError('Main executable is not a supported Mach-O')
    print(f'Converted {len(binaries)} original binaries; building compatibility libraries...', flush=True)
    frameworks = app / 'Frameworks'
    frameworks.mkdir(exist_ok=True)
    common = ['-target', f'arm64-apple-ios{MINIMUM}-macabi', '-isysroot', sdk, '-O2', '-dynamiclib']
    libraries = ['libnr_portrait.dylib', 'libnr_keychain.dylib']
    for name in libraries:
        if (frameworks / name).exists():
            raise ValueError(f'Input already contains {name}; use the original IPA')
    run('xcrun', 'clang++', *common, '-fobjc-arc', '-isystem', support / 'usr/include',
        '-iframework', support / 'System/Library/Frameworks', '-F', support / 'System/Library/Frameworks',
        '-L', support / 'usr/lib', ROOT / 'portrait.mm', '-framework', 'UIKit', '-framework', 'Foundation',
        '-install_name', '@rpath/' + libraries[0], '-o', frameworks / libraries[0])
    run('xcrun', 'clang', *common, '-Wall', source / 'ipa-keychain.c',
        '-framework', 'CoreFoundation', '-framework', 'Security',
        '-install_name', '@rpath/' + libraries[1], '-o', frameworks / libraries[1])
    for name in libraries:
        inject(executable, '@executable_path/Frameworks/' + name)
    info.update(CFBundleIdentifier=args.bundle_id, CFBundleDisplayName=args.name, MinimumOSVersion=MINIMUM)
    info_path.write_bytes(plistlib.dumps(info))
    (app / 'embedded.mobileprovision').unlink(missing_ok=True)
    entitlement_path = output / 'entitlements.plist'
    entitlement_path.write_bytes(plistlib.dumps({'com.apple.security.app-sandbox': True,
                                               'com.apple.security.network.client': True}))
    for attribute in ('com.apple.ResourceFork', 'com.apple.FinderInfo'):
        subprocess.run(['xattr', '-dr', attribute, str(app)], capture_output=True)
    print('Signing and verifying...', flush=True)
    for path in binaries + [frameworks / name for name in libraries]:
        run('codesign', '--force', '--sign', '-', path)
    for framework in sorted(app.rglob('*.framework'), key=lambda p: len(p.parts), reverse=True):
        run('codesign', '--force', '--sign', '-', framework)
    run('codesign', '--force', '--sign', '-', '--entitlements', entitlement_path, app)
    for path in binaries:
        if sections(path.read_bytes()) != baselines[path]:
            raise ValueError(f'Original section contents changed unexpectedly: {path.name}')
        run('codesign', '--verify', '--strict', path)
    run('codesign', '--verify', '--deep', '--strict', app)
    current = {str(p.relative_to(app)): digest(p) for p in app.rglob('*') if p.is_file()}
    report = {'schema': 'nulls-royale-mac.conversion.v1', 'source_ipa_sha256': digest(ipa),
              'source_version': info.get('CFBundleShortVersionString'), 'bundle_id': args.bundle_id,
              'catalyst_minimum': MINIMUM, 'original_binaries': records,
              'added_libraries': libraries, 'original_file_backed_sections_unchanged': True,
              'signature_verified': True,
              'unchanged_file_count': sum(current.get(n) == h for n, h in original_files.items()),
              'modified_files': sorted(n for n in original_files.keys() & current.keys() if original_files[n] != current[n]),
              'added_files': sorted(current.keys() - original_files.keys()),
              'removed_files': sorted(original_files.keys() - current.keys()),
              'output_sha256': current}
    (output / 'conversion-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Created: {app}\nReport: {output / "conversion-report.json"}\nThe app has not been launched or installed.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile) as error:
        print(f'Error: {error}\nAn incomplete output may remain. Use a new output directory when retrying.', file=sys.stderr)
        sys.exit(1)
