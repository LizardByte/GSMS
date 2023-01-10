#!/usr/bin/env python3
"""
gsms.py

A migration tool for Nvidia Gamestream to Sunshine.

This script updates the `apps.json` file for Sunshine and copies box art images to a specified directory. It reads
shortcut files (.lnk) from a specified directory and adds them to Sunshine as new apps. If an
app with the same name already exists in Sunshine, it will be skipped.

Usage
-----

To run the script, use the following command:

$ python gsms.py [OPTIONS]

OPTIONS

--apps, -a
    Specify the sunshine `apps.json` file to update, otherwise we will attempt to use the `apps.json` file from the
    default Sunshine installation location.

--image_path, -i
    Specify the full directory where to copy box art to. If not specified, box art will be copied to
    `%USERPROFILE%/Pictures/Sunshine`

--shortcut_dir, -s
    Specify a custom shortcut directory. If not specified, `%localappdata%/NVIDIA Corporation/Shield Apps` will be used.

--dry_run, -d
    If set, the `apps.json` file will not be overwritten. Use this flag to preview the changes that would be made
    without committing them.

--no_sleep
    If set, the script will not pause for 10 seconds at the end of the import.

Examples
--------

To migrate all Gamestream apps to Sunshine and copy box art images to the default directory:

$ python gsms.py

To migrate all Gamestream apps to Sunshine and copy box art images to a custom directory:

$ python gsms.py --image_path /path/to/custom/dir

To preview the changes that would be made without actually updating the `apps.json` file:

$ python gsms.py --dry_run
"""

# standard imports
import argparse
import ctypes
from ctypes import wintypes
import json
import os
import re
import shutil
import time
import uuid

# lib imports
import pylnk3


# Code from here and modified to work in this project
# https://gist.github.com/mkropat/7550097
class GUID(ctypes.Structure):
    """
    Class to build a GUID compliant object for use in Windows libraries

    Parameters
    ----------
    uuid : str
        The UUID to parse into a GUID object.

    Examples
    --------
    >>> GUID(uuid.UUID("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"))
    ...
    """
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]

    def __init__(self, uuid: str) -> None:
        ctypes.Structure.__init__(self)
        self.Data1, self.Data2, self.Data3, self.Data4[0], self.Data4[1], rest = uuid.fields
        for i in range(2, 8):
            self.Data4[i] = rest >> (8 - i - 1)*8 & 0xff


# https://learn.microsoft.com/en-us/windows/win32/api/combaseapi/nf-combaseapi-cotaskmemfree
# Define function to free pointer memory
_CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
# Add response type to function call
_CoTaskMemFree.restype = None
# Add argument types to C function call
_CoTaskMemFree.argtypes = [ctypes.c_void_p]

# https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
# Define function call for resolving the GUID path
_SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
# Add argument types to the C function call
_SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
]


def stopwatch(message: str, sec: int) -> None:
    """
    Countdown function that updates the console with a message and the remaining time in minutes and seconds.

    Parameters
    ----------
    message : str
        Prefix message to display before the countdown timer.
    sec : int
        Time, in seconds, to countdown from.

    Returns
    -------
    None

    Examples
    --------
    >>> stopwatch(message="Exiting in: ", sec=10)
    Exiting in: 00:10
    Exiting in: 00:09
    ...
    Exiting in: 00:00
    """
    while sec:
        minute, second = divmod(sec, 60)
        time_format = '{}{:02d}:{:02d}'.format(message, minute, second)
        print(time_format, end='\r')
        time.sleep(1)
        sec -= 1


def main() -> None:
    """
    Main application entrypoint. Migrates Nvidia Gamestream apps to Sunshine by updating the `apps.json` file and
    copying box art images to a specified directory.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        When the `apps.json` file specified or the default `apps.json` file is not found.

    Examples
    --------
    >>> main()
    ...
    """
    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='GSMS is a migration tool for Nvidia Gamestream to Sunshine.')

    parser.add_argument('--apps', '-a',
                        help='Specify the sunshine `apps.json` file to update, otherwise we will attempt to use the '
                             '`apps.json` file from the default Sunshine installation location.',
                        default=os.path.join(os.environ['programfiles'], 'Sunshine', 'config', 'apps.json')
                        )
    parser.add_argument('--image_path', '-i',
                        help='Specify the full directory where to copy box art to. If not specified, box art will be '
                             'copied to `%%USERPROFILE%%/Pictures/Sunshine`',
                        default=os.path.join(os.environ['userprofile'], 'Pictures', 'Sunshine')
                        )
    parser.add_argument('--shortcut_dir', '-s',
                        help='Specify a custom shortcut directory. If not specified,'
                             '`%%localappdata%%/NVIDIA Corporation/Shield Apps` will be used.',
                        default=os.path.join(os.environ['localappdata'], 'NVIDIA Corporation', 'Shield Apps')
                        )
    parser.add_argument('--dry_run', '-d', action='store_true',
                        help='If set, the `apps.json` file will not be overwritten. Use this flag to preview the '
                             'changes that would be made without committing them.')
    parser.add_argument('--no_sleep', action='store_true',
                        help='If set, the script will not pause for 10 seconds at the end of the import.')

    args = parser.parse_args()

    # create the image destination if it doesn't exist
    os.makedirs(name=args.image_path, exist_ok=True)

    count = 0
    if os.path.isfile(args.apps):
        # file exists
        with open(file=args.apps, mode="r") as f:
            sunshine_apps = json.load(f)
        print('Found apps.json file.')
        print(json.dumps(obj=sunshine_apps, indent=4))
        print('----')

        gs_apps = os.listdir(args.shortcut_dir)

        for gs_app in gs_apps:
            if gs_app.lower().endswith('.lnk'):
                name = gs_app.rsplit('.', 1)[0]  # split the lnk name by the extension separator
                shortcut = pylnk3.parse(lnk=os.path.join(args.shortcut_dir, gs_app))
                shortcut.work_dir = "" if shortcut.work_dir is None else shortcut.work_dir
                print(f'Found gamestream app: {name}')
                print(f'working-dir: {shortcut.work_dir}')
                print(f'path: {shortcut.path}')

                # GFE converts jpg to png, so no reason to handle anything except PNG files
                src_image = os.path.join(args.shortcut_dir, 'StreamingAssets', name, 'box-art.png')
                dst_image = os.path.join(args.image_path, f'{name}.png')

                # if src_image exists and dst_image does not exist
                if os.path.isfile(src_image) and not os.path.isfile(dst_image):
                    shutil.copy2(src=src_image, dst=dst_image)  # copy2 preserves metadata
                    print(f'Copied box-art image to: {dst_image}')
                else:
                    print(f'No box-art image found at: {src_image}')

                app_exists = False
                for app in sunshine_apps['apps']:
                    if name == app['name']:
                        app_exists = True
                        print(f'{name} app already exist in Sunshine apps.json, skipping.')

                if not app_exists:
                    count += 1

                    # remove final path separator but only if it exists
                    while shortcut.work_dir.endswith(os.sep):
                        shortcut.work_dir = shortcut.work_dir[:-1]

                    target_path = shortcut.path

                    # prepare regex to get folder UUIDs
                    regex = re.compile(
                        r"^::(\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\})\\"
                    )

                    work_dir_result = regex.findall(shortcut.work_dir)

                    if len(work_dir_result) == 1:
                        shortcut.work_dir = shortcut.work_dir.replace(
                            f"::{work_dir_result[0]}",
                            get_win_path(work_dir_result[0])
                        )

                    path_result = regex.findall(shortcut.path)

                    if len(path_result) == 1:
                        target_path = shortcut.path.replace(
                            f"::{path_result[0]}",
                            get_win_path(folder_id=path_result[0])
                        )

                    target_path = target_path.replace(shortcut.work_dir, '')

                    # remove first path separator but only if it exists
                    if target_path.startswith(os.sep):
                        target_path = target_path[1:]

                    sunshine_apps['apps'].append(
                        {
                            'name': name,
                            'output': f"{name.lower().replace(' ', '_')}.log",
                            'cmd': target_path,
                            'working-dir': shortcut.work_dir,
                            'image-path': dst_image
                        }
                    )
        if not args.dry_run:
            with open(file=args.apps, mode="w") as f:
                json.dump(obj=sunshine_apps, indent=4, fp=f)
        print(json.dumps(obj=sunshine_apps, indent=4))
        print('Completed importing Nvidia gamestream games.')
        print(f'Added {count} apps to Sunshine.')
        if not args.no_sleep:
            stopwatch(message='Exiting in: ', sec=10)
    else:
        raise FileNotFoundError('Specified apps.json does not exist. '
                                'If you used the Sunshine Windows installer version, be sure to run Sunshine first '
                                'and we will automatically detect it IF you use the default installation directory. '
                                'Use the `--apps` arg to specify the full path of the file if you\'d like to use a '
                                'custom location.')


def get_win_path(folder_id: str) -> str:
    """
    Function to resolve Windows UUID folders into their absolute path

    Parameters
    ----------
    folder_id : str
        The folder UUID to convert into the absolute path.

    Returns
    -------
    str
        Resolved Windows path as string.

    Raises
    ------
    NotADirectoryError
        When a UUID can not be resolved to a path as it is not a Windows UUID path this will be raised.

    Examples
    --------
    >>> get_win_path("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", UserHandle.Common)
    ...
    """
    # Get actual Windows folder id (fid)
    fid = GUID(uuid.UUID(folder_id))
    # Prepare pointer to store the path
    path_pointer = ctypes.c_wchar_p()
    # Execute function (which stores the path in our pointer) and check return value for success (0 = OK)
    if _SHGetKnownFolderPath(ctypes.byref(fid), 0, wintypes.HANDLE(0), ctypes.byref(path_pointer)) != 0:
        raise NotADirectoryError(f"The specified UUID '{folder_id}' could not be resolved to a path")
    # Get value from pointer
    path = path_pointer.value
    # Free memory used by pointer
    _CoTaskMemFree(path_pointer)
    return path


if __name__ == '__main__':
    main()
