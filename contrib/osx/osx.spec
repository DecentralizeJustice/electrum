# -*- mode: python -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

import sys, os

PACKAGE='Electrum'
PYPKG='electrum'
MAIN_SCRIPT='run_electrum'
ICONS_FILE=PYPKG + '/gui/icons/electrum.icns'
APP_SIGN = os.environ.get('APP_SIGN', '')

def fail(*msg):
    RED='\033[0;31m'
    NC='\033[0m' # No Color
    print("\r🗯 {}ERROR:{}".format(RED, NC), *msg)
    sys.exit(1)

def codesign(identity, binary):
    d = os.path.dirname(binary)
    saved_dir=None
    if d:
        # switch to directory of the binary so codesign verbose messages don't include long path
        saved_dir = os.path.abspath(os.path.curdir)
        os.chdir(d)
        binary = os.path.basename(binary)
    os.system("codesign -v -f -s '{}' '{}'".format(identity, binary))==0 or fail("Could not code sign " + binary)
    if saved_dir:
        os.chdir(saved_dir)

def monkey_patch_pyinstaller_for_codesigning(identity):
    # Monkey-patch PyInstaller so that we app-sign all binaries *after* they are modified by PyInstaller
    # If we app-sign before that point, the signature will be invalid because PyInstaller modifies
    # @loader_path in the Mach-O loader table.
    try:
        import PyInstaller.depend.dylib
        _saved_func = PyInstaller.depend.dylib.mac_set_relative_dylib_deps
    except (ImportError, NameError, AttributeError):
        # Hmm. Likely wrong PyInstaller version.
        fail("Could not monkey-patch PyInstaller for code signing. Please ensure that you are using PyInstaller 3.4.")
    _signed = set()
    def my_func(fn, distname):
        _saved_func(fn, distname)
        if  (fn, distname) not in _signed:
            codesign(identity, fn)
            _signed.add((fn,distname)) # remember we signed it so we don't sign again
    PyInstaller.depend.dylib.mac_set_relative_dylib_deps = my_func


for i, x in enumerate(sys.argv):
    if x == '--name':
        VERSION = sys.argv[i+1]
        break
else:
    raise Exception('no version')

electrum = os.path.abspath(".") + "/"
block_cipher = None

# see https://github.com/pyinstaller/pyinstaller/issues/2005
hiddenimports = []
hiddenimports += collect_submodules('pkg_resources')  # workaround for https://github.com/pypa/setuptools/issues/1963
hiddenimports += collect_submodules('websocket')

datas = [
    (electrum + PYPKG + '/*.json', PYPKG),
    (electrum + PYPKG + '/lnwire/*.csv', PYPKG + '/lnwire'),
    (electrum + PYPKG + '/wordlist/english.txt', PYPKG + '/wordlist'),
    (electrum + PYPKG + '/locale', PYPKG + '/locale'),
]

# Add the QR Scanner helper app

# Add libusb so Trezor and Safe-T mini will work
binaries = [(electrum + "contrib/osx/libsecp256k1.0.dylib", ".")]


# We don't put these files in to actually include them in the script but to make the Analysis method scan them for imports
a = Analysis([electrum+ MAIN_SCRIPT,
              electrum+'electrum/util.py',
              electrum+'electrum/wallet.py',
              electrum+'electrum/simple_config.py',
              electrum+'electrum/bitcoin.py',
              electrum+'electrum/dnssec.py',
              electrum+'electrum/commands.py',
              ],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[])

# http://stackoverflow.com/questions/19055089/pyinstaller-onefile-warning-pyconfig-h-when-importing-scipy-or-scipy-signal
for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break
print (a.binaries)
# Strip out parts of Qt that we never use. Reduces binary size by tens of MBs. see #4815
qt_bins2remove=('qtweb', 'qt3d', 'qtgame', 'qtdesigner', 'qtquick', 'qtlocation', 'qttest', 'qtxml', 'qtgui', 'qtwidgets', 'qtmultimedia')
print("Removing Qt binaries:", *qt_bins2remove)
for x in a.binaries.copy():
    print (x)
    for r in qt_bins2remove:
        if x[0].lower().startswith(r):
            a.binaries.remove(x)
            print('----> Removed x =', x)

# If code signing, monkey-patch in a code signing step to pyinstaller. See: https://github.com/spesmilo/electrum/issues/4994
if APP_SIGN:
    monkey_patch_pyinstaller_for_codesigning(APP_SIGN)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name=MAIN_SCRIPT,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
