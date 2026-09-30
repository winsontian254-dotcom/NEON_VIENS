#!/usr/bin/env python3
"""
SDK-free APK build for Neon Veins.

Android Studio / Gradle users: just open the android/ folder and build normally.
This script exists for machines without the Android SDK. It only needs a JDK (javac, java) and Python with
`pip install pyaxml cryptography`. It downloads two jars from Maven Central (cached in android/.tools):
  - org.robolectric:android-all (API 34 framework classes) to compile against
  - com.jakewharton.android.repackaged:dalvik-dx to turn .class files into classes.dex
Then it encodes the binary AndroidManifest.xml (pyaxml), writes a minimal resources.arsc for the launcher
icon, zips and 4-byte aligns the APK, and signs it with APK Signature Scheme v2.

Usage:  python3 android/tools/build-apk.py            -> android/NeonVeins.apk
"""
import hashlib
import os
import re
import struct
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # android/
REPO = os.path.dirname(ROOT)                      # repo root (index.html lives here)
MAIN = os.path.join(ROOT, 'app', 'src', 'main')
CACHE = os.path.join(ROOT, '.tools')
BUILD = os.path.join(ROOT, 'build-sdkfree')
OUT_APK = os.path.join(ROOT, 'NeonVeins.apk')
KEYDIR = os.path.join(ROOT, 'keystore')

PKG, VERSION_CODE, VERSION_NAME, MIN_SDK, TARGET_SDK = 'com.neonveins.game', 1, '1.0', 24, 34
ICON_PATH = 'res/mipmap-xxxhdpi-v4/ic_launcher.png'

MIRRORS = ['https://maven-central.storage-download.googleapis.com/maven2', 'https://repo1.maven.org/maven2', 'https://repo.maven.apache.org/maven2']
TOOLS = {
    'android-all.jar': 'org/robolectric/android-all/14-robolectric-10818077/android-all-14-robolectric-10818077.jar',
    'dx.jar': 'com/jakewharton/android/repackaged/dalvik-dx/16.0.1/dalvik-dx-16.0.1.jar',
}


def log(*a):
    print('[build-apk]', *a, flush=True)


def fetch_tools():
    os.makedirs(CACHE, exist_ok=True)
    for name, path in TOOLS.items():
        dst = os.path.join(CACHE, name)
        if os.path.exists(dst) and zipfile.is_zipfile(dst):
            continue
        for m in MIRRORS:
            try:
                log('downloading', name, 'from', m)
                urllib.request.urlretrieve(m + '/' + path, dst)
                if zipfile.is_zipfile(dst):
                    break
            except Exception as e:  # try the next mirror
                log('  failed:', e)
        else:
            sys.exit('could not download ' + name)


# ---------------------------------------------------------------- compile + dex
def compile_java():
    classes = os.path.join(BUILD, 'classes')
    os.makedirs(classes, exist_ok=True)
    srcs = []
    for d, _, fs in os.walk(os.path.join(MAIN, 'java')):
        srcs += [os.path.join(d, f) for f in fs if f.endswith('.java')]
    log('javac', len(srcs), 'files')
    subprocess.check_call(['javac', '--release', '8', '-nowarn', '-Xlint:-options', '-encoding', 'UTF-8',
                           '-cp', os.path.join(CACHE, 'android-all.jar'), '-d', classes] + srcs)
    dex = os.path.join(BUILD, 'classes.dex')
    log('dx -> classes.dex')
    subprocess.check_call(['java', '-cp', os.path.join(CACHE, 'dx.jar'), 'com.android.dx.command.Main', '--dex',
                           '--min-sdk-version=%d' % MIN_SDK, '--output=' + dex, classes])
    return open(dex, 'rb').read()


# ---------------------------------------------------------------- manifest
ENUMS = {
    'screenOrientation': {'unspecified': -1, 'landscape': 0, 'portrait': 1, 'sensorLandscape': 6, 'sensorPortrait': 7, 'fullSensor': 10},
    'launchMode': {'standard': 0, 'singleTop': 1, 'singleTask': 2, 'singleInstance': 3},
}
CONFIG_FLAGS = {'mcc': 0x1, 'mnc': 0x2, 'locale': 0x4, 'touchscreen': 0x8, 'keyboard': 0x10, 'keyboardHidden': 0x20, 'navigation': 0x40,
                'orientation': 0x80, 'screenLayout': 0x100, 'uiMode': 0x200, 'screenSize': 0x400, 'smallestScreenSize': 0x800, 'density': 0x1000}


def build_manifest():
    import pyaxml
    x = open(os.path.join(MAIN, 'AndroidManifest.xml'), encoding='utf-8').read()
    x = re.sub(r'<!--.*?-->', '', x, flags=re.S)
    # what Gradle normally merges in from app/build.gradle
    x = x.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
                  '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="%s" android:versionCode="%d" android:versionName="%s">'
                  '<uses-sdk android:minSdkVersion="%d" android:targetSdkVersion="%d"/>' % (PKG, VERSION_CODE, VERSION_NAME, MIN_SDK, TARGET_SDK), 1)
    x = x.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@7f010000"')
    x = re.sub(r'android:name="\.', 'android:name="%s.' % PKG, x)
    for attr, table in ENUMS.items():
        x = re.sub(r'android:%s="(\w+)"' % attr, lambda m, t=table, a=attr: 'android:%s="%d"' % (a, t[m.group(1)]), x)
    x = re.sub(r'android:configChanges="([\w|]+)"', lambda m: 'android:configChanges="0x%x"' % sum(CONFIG_FLAGS[f] for f in m.group(1).split('|')), x)
    a = pyaxml.AXML()
    a.from_xml(pyaxml._to_element(x))
    return a.pack()


# ---------------------------------------------------------------- resources.arsc (one mipmap: 0x7f010000 -> the icon)
def pad4(b):
    return b + b'\0' * (-len(b) % 4)


def string_pool(strings, utf8):
    data, offs = b'', []
    for s in strings:
        offs.append(len(data))
        if utf8:
            e = s.encode('utf-8')
            data += bytes([len(s), len(e)]) + e + b'\0'
        else:
            data += struct.pack('<H', len(s)) + s.encode('utf-16-le') + b'\0\0'
    data = pad4(data)
    hdr = 28
    starts = hdr + 4 * len(strings)
    body = b''.join(struct.pack('<I', o) for o in offs) + data
    return struct.pack('<HHIIIIII', 0x0001, hdr, hdr + len(body), len(strings), 0, 0x100 if utf8 else 0, starts, 0) + body


def build_arsc():
    gpool = string_pool([ICON_PATH], True)
    tpool = string_pool(['mipmap'], False)
    kpool = string_pool(['ic_launcher'], False)
    spec = struct.pack('<HHIBBHI', 0x0202, 16, 16 + 4, 1, 0, 0, 1) + struct.pack('<I', 0)
    config = struct.pack('<I', 64) + b'\0' * 60
    config = config[:14] + struct.pack('<H', 640) + config[16:]          # density = xxxhdpi
    entry = struct.pack('<HHI', 8, 0, 0) + struct.pack('<HBBI', 8, 0, 0x03, 0)  # key 0 -> string 0 (file path)
    thdr = 20 + len(config)
    tbody = struct.pack('<I', 0) + entry
    ttype = struct.pack('<HHIBBHII', 0x0201, thdr, thdr + len(tbody), 1, 0, 0, 1, thdr + 4) + config + tbody
    phdr = 288
    name = PKG.encode('utf-16-le').ljust(256, b'\0')
    pbody = tpool + kpool + spec + ttype
    pkg = struct.pack('<HHII', 0x0200, phdr, phdr + len(pbody), 0x7f) + name + struct.pack('<IIIII', phdr, 1, phdr + len(tpool), 1, 0) + pbody
    return struct.pack('<HHII', 0x0002, 12, 12 + len(gpool) + len(pkg), 1) + gpool + pkg


# ---------------------------------------------------------------- zip (aligned) + APK Signature Scheme v2
def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data, stored in entries:
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            if stored:  # zipalign: data of uncompressed entries must start on a 4-byte boundary
                off = z.fp.tell() + 30 + len(name.encode())
                zi.extra = b'\0' * (-off % 4)
            z.writestr(zi, data)


def lp(b):
    return struct.pack('<I', len(b)) + b


def load_key():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime
    os.makedirs(KEYDIR, exist_ok=True)
    kp, cp = os.path.join(KEYDIR, 'debug-key.pem'), os.path.join(KEYDIR, 'debug-cert.der')
    if not os.path.exists(kp):
        log('creating a debug signing key in', KEYDIR)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Neon Veins Debug'), x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Neon Veins')])
        now = datetime.datetime(2026, 1, 1)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365 * 30))
                .sign(key, hashes.SHA256()))
        open(kp, 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        open(cp, 'wb').write(cert.public_bytes(serialization.Encoding.DER))
    key = serialization.load_pem_private_key(open(kp, 'rb').read(), None)
    return key, open(cp, 'rb').read()


def sign_v2(unsigned, out):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    data = open(unsigned, 'rb').read()
    eocd = data.rfind(b'PK\x05\x06')
    cd_size, cd_off = struct.unpack('<II', data[eocd + 12:eocd + 20])
    sections = [data[:cd_off], data[cd_off:cd_off + cd_size], data[eocd:]]

    def chunks_digest():
        digs = []
        for sec in sections:
            for i in range(0, len(sec), 1 << 20):
                c = sec[i:i + (1 << 20)]
                digs.append(hashlib.sha256(b'\xa5' + struct.pack('<I', len(c)) + c).digest())
        return hashlib.sha256(b'\x5a' + struct.pack('<I', len(digs)) + b''.join(digs)).digest()

    ALG = 0x0103  # RSASSA-PKCS1-v1_5 with SHA2-256
    key, cert = load_key()
    pub = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    signed = lp(lp(struct.pack('<I', ALG) + lp(chunks_digest()))) + lp(lp(cert)) + lp(b'')
    sig = key.sign(signed, padding.PKCS1v15(), hashes.SHA256())
    signer = lp(signed) + lp(lp(struct.pack('<I', ALG) + lp(sig))) + lp(pub)
    value = lp(lp(signer))
    pair = struct.pack('<Q', 4 + len(value)) + struct.pack('<I', 0x7109871a) + value
    size = len(pair) + 8 + 16
    block = struct.pack('<Q', size) + pair + struct.pack('<Q', size) + b'APK Sig Block 42'
    new_eocd = bytearray(sections[2])
    new_eocd[16:20] = struct.pack('<I', cd_off + len(block))
    open(out, 'wb').write(sections[0] + block + sections[1] + bytes(new_eocd))


def main():
    fetch_tools()
    os.makedirs(BUILD, exist_ok=True)
    dex = compile_java()
    manifest = build_manifest()
    arsc = build_arsc()
    icon = open(os.path.join(MAIN, 'res', 'mipmap-xxxhdpi', 'ic_launcher.png'), 'rb').read()
    game = open(os.path.join(REPO, 'index.html'), 'rb').read()
    unsigned = os.path.join(BUILD, 'unsigned.apk')
    write_zip(unsigned, [('AndroidManifest.xml', manifest, False), ('classes.dex', dex, False), ('resources.arsc', arsc, True),
                         (ICON_PATH, icon, True), ('assets/index.html', game, False)])
    sign_v2(unsigned, OUT_APK)
    log('wrote', OUT_APK, '(%d KB)' % (os.path.getsize(OUT_APK) // 1024))


if __name__ == '__main__':
    main()
