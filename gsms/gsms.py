#!/usr/bin/env python3
"""
gsms.py

A migration tool for Nvidia GameStream to Sunshine.

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
    If set, the `apps.json` file will not be overwritten and box-art images won't be copied. Use this flag to preview
    the changes that would be made without committing them.

--no_sleep
    If set, the script will not pause for 10 seconds at the end of the import.

--nv_add_autodetect, -n
    If set, the script will add all streamable apps from Nvidia GameStream's automatically detected applications.

Examples
--------

To migrate all GameStream apps to Sunshine and copy box art images to the default directory:

$ python gsms.py

To migrate all GameStream apps to Sunshine and copy box art images to a custom directory:

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
import xml.etree.ElementTree

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
    C:\\Users\\...\\Desktop
    >>> get_win_path(folder_id="B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
    C:\\Users\\...\\Desktop
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


def copy_image(src_image: str, dst_image: str) -> None:
    """
    Copy an image from `src_image` to `dst_image` if the destination image does not exist.

    Parameters
    ----------
    src_image : str
        Source path of the image.
    dst_image : str
        Destination path of the image.

    Examples
    --------
    >>> copy_image(src_image="C:\\Image1.png", dst_image="D:\\Image1.png")
    """
    # if src_image exists and dst_image does not exist
    if os.path.isfile(src_image) and not os.path.isfile(dst_image):
        shutil.copy2(src=src_image, dst=dst_image)  # copy2 preserves metadata
        print(f'Copied box-art image to: {dst_image}')
    else:
        print(f'No box-art image found at: {src_image}')


def has_app(sunshine_apps: dict, name: str) -> bool:
    """
    Checks if a given app name is in the sunshine_apps object.

    Parameters
    ----------
    sunshine_apps : dict
        Dictionary object of the sunshine `apps.json`.
    name : str
        Name to check for.

    Returns
    -------
    bool
        True if the app is in the sunshine_apps object, otherwise False.

    Examples
    --------
    >>> has_app(sunshine_apps={}, name="Game Name")
    False
    """
    app_exists = False

    for existing_app in sunshine_apps['apps']:
        if name == existing_app['name']:
            app_exists = True
            print(f'{name} app already exist in Sunshine apps.json, skipping.')
            break

    return app_exists


def add_game(sunshine_apps: dict, name: str, logfile: str, cmd: str, working_dir: str, image_path: str) -> None:
    """
    Add an app to the sunshine_apps object.

    Parameters
    ----------
    sunshine_apps : dict
        Dictionary object of the sunshine `apps.json`.
    name : str
        Name of the app.
    logfile : str
        Logfile name for the app.
    cmd : str
        Commandline to start the app.
    working_dir : str
        Working directory for the app.
    image_path : str
        Path to an image file to display as box-art.

    Examples
    --------
    >>> add_game(sunshine_apps={}, name="Game Name", logfile="game.log", cmd="game.exe",
    >>>          working_dir="C:\\game_dir", image_path="C:\\game_dir\\image.png")
    """
    working_dir = known_path_to_absolute(path=working_dir)
    cmd = known_path_to_absolute(path=cmd)

    # remove final path separator but only if it exists
    while working_dir.endswith(os.sep):
        working_dir = working_dir[:-1]

    # remove preceding separator on the command if it exists
    while cmd.startswith(os.sep):
        cmd = cmd[1:]

    # we don't need ot keep quotes around the path or working directory
    working_dir = working_dir.replace('"', "")
    cmd = cmd.replace('"', '')

    detached = False

    # cmd begins with "start", this must be a detached command
    if cmd.lower().startswith("start"):
        detached = True
        cmd = cmd[5:].strip()

    # command is a URI, this must be a detached command
    if '://' in cmd:
        detached = True

        # if the URI uses the steam protocol we prepend the steam executable
        if 'steam://' in cmd:
            cmd = f"steam {cmd}"
    # if it's not a URI we check if the command includes the working_directory
    elif not cmd.startswith(working_dir):
        cmd = os.path.join(working_dir, cmd)

    data = {
        'name': name,
        'output': logfile,
        'working-dir': working_dir,
        'image-path': image_path
    }

    # we add the command to the appropriate field
    if detached:
        data['detached'] = [cmd]
    else:
        data['cmd'] = cmd

    sunshine_apps['apps'].append(data)


def known_path_to_absolute(path: str) -> str:
    """
    Convert paths containing Windows known path UUID to absolute path.

    Parameters
    ----------
    path : str
        Path that may contain Windows UUID.

    Returns
    -------
    str
        The absolute path.

    Examples
    --------
    >>> known_path_to_absolute(path='::{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}')
    C:\\ProgramData
    """
    # prepare regex to get folder UUIDs which can only be at the start exactly 1 time with 2 preceding colons
    regex = re.compile(
        r"^::(\{[\da-fA-F]{8}-[\da-fA-F]{4}-[\da-fA-F]{4}-[\da-fA-F]{4}-[\da-fA-F]{12}})"
    )

    path_result = regex.findall(path)

    if len(path_result) == 1:
        path = path.replace(
            f"::{path_result[0]}",
            get_win_path(folder_id=path_result[0])
        )

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

    Raises
    ------
    FileNotFoundError
        When the ``apps.json`` file specified or the default ``apps.json`` file is not found.

    Examples
    --------
    >>> main()
    ...
    """
    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='GSMS is a migration tool for Nvidia GameStream to Sunshine.')

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
                        help='If set, the `apps.json` file will not be overwritten and box-art images won\'t be copied.'
                             'Use this flag to preview the changes that would be made without committing them.')
    parser.add_argument('--no_sleep', action='store_true',
                        help='If set, the script will not pause for 10 seconds at the end of the import.')
    parser.add_argument('--nv_add_autodetect', '-n', action='store_true',
                        help='If set, GSMS will import the automatically detected apps from Nvidia GameStream.')

    args = parser.parse_args()

    # create the image destination if it doesn't exist
    os.makedirs(name=args.image_path, exist_ok=True)

    # create some helper path variables for later usage
    nvidia_base_dir = os.path.join(os.environ['localappdata'], "NVIDIA", "NvBackend")
    # Path for the main application xml Nvidia GFE uses
    nvidia_autodetect_dir = os.path.join(nvidia_base_dir, "journalBS.main.xml")
    # Base folder for the box-art
    nvidia_images_base_dir = os.path.join(nvidia_base_dir, "VisualOPSData")

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

                if has_app(sunshine_apps=sunshine_apps, name=name):
                    continue

                count += 1

                shortcut = pylnk3.parse(lnk=os.path.join(args.shortcut_dir, gs_app))
                shortcut.work_dir = "" if shortcut.work_dir is None else shortcut.work_dir
                print(f'Found GameStream app: {name}')
                print(f'working-dir: {shortcut.work_dir}')
                print(f'path: {shortcut.path}')

                # GFE converts jpg to png, so no reason to handle anything except PNG files
                src_image = os.path.join(args.shortcut_dir, 'StreamingAssets', name, 'box-art.png')
                dst_image = os.path.join(args.image_path, f'{name}.png')

                if not args.dry_run:
                    copy_image(src_image=src_image, dst_image=dst_image)

                add_game(
                    sunshine_apps=sunshine_apps,
                    name=name,
                    logfile=f"{name.lower().replace(' ', '_')}.log",
                    cmd=shortcut.path,
                    working_dir=shortcut.work_dir,
                    image_path=dst_image
                )

        if args.nv_add_autodetect:
            # Use ElementTree lib to build XML tree
            tree = xml.etree.ElementTree.parse(nvidia_autodetect_dir)
            # Get root so we can loop through children
            root = tree.getroot()
            applications_root = root.find("Application")

            # Prepare JSON object to fetch version numbers for use in getting the box-art image
            with open(file=os.path.join(nvidia_images_base_dir, "ApplicationData.json"), mode="r") as f:
                gfe_apps = json.load(f)

            # Loop through all applications in the 'Application' parent element
            for application in applications_root:

                name = application.find("DisplayName").text

                # We skip the GFE GS steam application
                if name == "Steam":
                    continue

                # If we already have an App with the EXACT same name we skip it
                if has_app(sunshine_apps=sunshine_apps, name=name):
                    continue

                cmd = application.find("StreamingCommandLine").text
                if cmd is None:
                    print(application.find("DisplayName").text, 'has no streaming command line. Skipping')
                    continue

                working_dir = application.find("InstallDirectory").text
                # Nvidia's short_name is a pre-shortened and filesystem safe name for the game
                short_name = application.find("ShortName").text

                print(f'Found GameStream app: {name}')
                print(f'working-dir: {working_dir}')
                print(f'path: {cmd}')

                if short_name in gfe_apps["metadata"]:
                    src_image = os.path.join(
                        nvidia_images_base_dir,
                        short_name,
                        gfe_apps["metadata"][short_name]["c"],
                        f"{short_name}-box-art.png"
                    )
                    dst_image = os.path.join(args.image_path, f'{short_name}.png')

                    if not args.dry_run:
                        copy_image(src_image=src_image, dst_image=dst_image)

                    add_game(
                        sunshine_apps=sunshine_apps,
                        name=name,
                        logfile=f"{short_name}.log",
                        cmd=cmd,
                        working_dir=working_dir,
                        image_path=dst_image
                    )

                    # Increase count here to exclude some stuff
                    count += 1

        if not args.dry_run:
            with open(file=args.apps, mode="w") as f:
                json.dump(obj=sunshine_apps, indent=4, fp=f)
        print(json.dumps(obj=sunshine_apps, indent=4))
        print('Completed importing Nvidia GameStream games.')
        print(f'Added {count} apps to Sunshine.')
        if not args.no_sleep:
            stopwatch(message='Exiting in: ', sec=10)
    else:
        raise FileNotFoundError('Specified apps.json does not exist. '
                                'If you used the Sunshine Windows installer version, be sure to run Sunshine first '
                                'and we will automatically detect it IF you use the default installation directory. '
                                'Use the `--apps` arg to specify the full path of the file if you\'d like to use a '
                                'custom location.')


if __name__ == '__main__':
    main()
