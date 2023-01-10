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

--nv_add_autodetect, -n
    If set, the swcript will add all streamable apps from NVidia GFE's autodetected applications

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
from uuid import UUID
import xml.etree.ElementTree as ET
import re

# lib imports
import pylnk3


# Code from here and simplified to work with GSMS
# https://gist.github.com/mkropat/7550097
class WindowsGUIDWrapper(ctypes.Structure):
    """
    Create a GUID compliant object for use in Windows libraries.

    Parameters
    ----------
    unique_id : UUID
        The UUID to parse into a GUID object.

    Examples
    --------
    >>> WindowsGUIDWrapper(unique_id=UUID("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"))
    ...
    """
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]

    def __init__(self, unique_id: UUID) -> None:
        ctypes.Structure.__init__(self)
        self.Data1, self.Data2, self.Data3, self.Data4[0], self.Data4[1], rest = unique_id.fields
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
    ctypes.POINTER(WindowsGUIDWrapper), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
]


def get_win_path(folder_id: str) -> str:
    """
    Resolve Windows UUID folders into their absolute path.

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
    >>> get_win_path(folder_id="{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}")
    ...
    """
    # Get actual Windows folder id (fid)
    fid = WindowsGUIDWrapper(unique_id=UUID(folder_id))

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
    parser.add_argument('--nv_add_autodetect', '-n', action='store_true',
                        help='If set, GSMS will import the autodetected apps from NVIDIA Gamestream.')

    args = parser.parse_args()

    # create the image destination if it doesn't exist
    os.makedirs(name=args.image_path, exist_ok=True)

    # create some helper path variables for later usage
    nvidia_base_dir = os.path.join(os.environ['localappdata'], "NVIDIA", "NvBackend")
    # Path for the main application xml NVidia GFE uses
    nvidia_autodetect_dir = os.path.join(nvidia_base_dir, "journalBS.main.xml")
    # Base folder for the box-art
    nvidia_images_base_dir = os.path.join(nvidia_base_dir, "StreamingAssetsData")

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

                copy_image(src_image, dst_image)

                if has_app(sunshine_apps, name):
                    continue

                count += 1

                # remove final path separator but only if it exists
                if shortcut.work_dir.endswith(os.sep):
                    shortcut.work_dir = shortcut.work_dir[:-1]

                add_game(
                    sunshine_apps,
                    name,
                    f"{name.lower().replace(' ', '_')}.log",
                    shortcut.path.replace(shortcut.work_dir, ''),
                    shortcut.work_dir.rsplit('\\', 1)[0],
                    dst_image
                )

        if args.nv_add_autodetect:
            # Use ElementTree lib to build XML tree
            tree = ET.parse(nvidia_autodetect_dir)
            # Get root so we can loop through children
            root = tree.getroot()
            applications_root = root.find("Application")

            # Prepare JSON object to fetch version numbers for use in getting the box-art image
            with open(file=os.path.join(nvidia_images_base_dir, "ApplicationData.json"), mode="r") as f:
                gfe_apps = json.load(f)

            # Loop through all applications in the 'Application' parent element
            for application in applications_root:
                # If GFE GS marked an app as not streaming supported we skip it
                if application.find("IsStreamingSupported").text == "0":
                    continue

                name = application.find("DisplayName").text

                # We skip the GFE GS steam application
                if name == "Steam":
                    continue

                # If we already have an App with the EXACT same name we skip it
                if has_app(sunshine_apps, name):
                    continue

                # Increae count here to exclude some stuff
                count += 1

                cmd = application.find("StreamingCommandLine").text
                working_dir = application.find("InstallDirectory").text
                # NVidia's short_name is a pre-shortened and filesystem safe name for the game
                short_name = application.find("ShortName").text

                print(f'Found gamestream app: {name}')
                print(f'working-dir: {working_dir}')
                print(f'path: {cmd}')

                src_image = os.path.join(
                    nvidia_images_base_dir,
                    short_name,
                    gfe_apps["metadata"][short_name]["c"],
                    f"{short_name}-box-art.png"
                )
                dst_image = os.path.join(args.image_path, f'{short_name}.png')

                copy_image(src_image, dst_image)

                add_game(sunshine_apps, name, f"{short_name}.log", cmd, working_dir, dst_image)

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


def copy_image(src_image, dst_image) -> None:
    """
    Copies an image from src_image to dst_image if the dst is empty or different

    Parameters
    ----------
    src_image: str
        Source path of the image
    dst_image: str
        Destination path of the image

    Returns
    -------
    None

    Examples
    --------
    >>> copy_image("C:\\Image1.png", "D:\\Image1.png")
    """
    # if src_image exists and dst_image does not exist
    if os.path.isfile(src_image) and not os.path.isfile(dst_image):
        shutil.copy2(src=src_image, dst=dst_image)  # copy2 preserves metadata
        print(f'Copied box-art image to: {dst_image}')
    else:
        print(f'No box-art image found at: {src_image}')


def has_app(sunshine_apps, name) -> bool:
    """
    Checks if a given app name is in the sunshine_apps object

    Parameters
    ----------
    sunshine_apps: Object
        Parsed JSON object of the sunshine `apps.json`
    name: string
        Name to check for

    Returns
    -------
    bool:
        True if the app is in the sunshine_apps object. Otherwise False

    Examples
    --------
    >>> has_app(sunshine_apps_object, "Game Name")
    False
    """
    app_exists = False

    for existing_app in sunshine_apps['apps']:
        if name == existing_app['name']:
            app_exists = True
            print(f'{name} app already exist in Sunshine apps.json, skipping.')
            break

    return app_exists


def add_game(sunshine_apps, name, logfile, cmd, working_dir, image_path) -> None:
    """
    Function to add an app to the sunshine_apps object passed in

    Parameters
    ----------
    sunshine_apps: Object
        Parsed JSON object of the sunshine `apps.json`
    name: str
        Name of the app
    logfile: str
        Logfile name for the app
    cmd: str
        Commandline to start the app
    working_dir: str
        Working directory for the app
    image_path: str
        Path to an image file to display as box-art

    Returns
    -------
    None

    Examples
    --------
    >>> add_game(sunshine_apps_object, "Game Name", "game.log", "game.exe", "C:\\gamedir", "C:\\gamedir\\image.png")
    """
    sunshine_apps['apps'].append(
        {
            'name': name,
            'output': logfile,
            'cmd': cmd,
            'working-dir': working_dir,
            'image-path': image_path
        }
    )


if __name__ == '__main__':
    main()
