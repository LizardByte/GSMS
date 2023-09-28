"""
..
   build.py

Creates spec and builds binaries for GSMS.
"""
# standard imports
import sys

# lib imports
import PyInstaller.__main__


def build():
    """Sets arguments for pyinstaller, creates spec, and builds binaries."""
    pyinstaller_args = [
        'gsms/gsms.py',
        '--onefile',
        '--noconfirm',
        '--paths=./',
        '--icon=./sunshine.ico'
    ]

    if sys.platform.lower() == 'win32':  # windows
        pyinstaller_args.append('--console')

        # fix args for windows
        arg_count = 0
        for arg in pyinstaller_args:
            pyinstaller_args[arg_count] = arg.replace(':', ';')
            arg_count += 1

    # no point in having macos/linux versions for this project

    PyInstaller.__main__.run(pyinstaller_args)


if __name__ == '__main__':
    build()
