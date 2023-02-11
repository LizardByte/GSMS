# standard imports
import os
import time
import uuid

# lib imports
import pytest

# local imports
import gsms


def test_windows_guid_wrapper():
    guid = gsms.WindowsGUIDWrapper(unique_id=uuid.uuid4())
    assert isinstance(guid, gsms.WindowsGUIDWrapper)


def test_get_win_path():
    with pytest.raises(ValueError):
        gsms.get_win_path(folder_id="not_a_valid_uuid")
    with pytest.raises(NotADirectoryError):
        gsms.get_win_path(folder_id=str(uuid.uuid4()))  # what are the chances this will resolve to a valid path?

    folder_ids = [
        # uuid list
        # more known UUIDs: https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
        "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",  # user "Desktop" folder
        "F42EE2D3-909F-4907-8871-4C22FC0BF756",  # user "Documents" folder
        "FDD39AD0-238F-46AF-ADB4-6C85480369C7",  # alternate user "Documents" folder
        "F38BF404-1D43-42F2-9305-67DE0B28FC23",  # "C:\\WINDOWS" folder
        "374DE290-123F-4565-9164-39C4925E467B",  # user "Downloads" folder
        "1777F761-68AD-4D8A-87BD-30B759FA33DD",  # user "Favorites" folder
        "FD228CB7-AE11-4AE3-864C-16F3910AB8FE",  # "C:\\WINDOWS\\Fonts" folder
        "4BD8D571-6D19-48D3-BE97-422220080E43",  # user "Music" folder
        "18989B1D-99B5-455B-841C-AB7C74E4DDFC",  # user "Videos" folder
        "C5ABBF53-E17F-4121-8900-86626FC2C973",  # "AppData\\Roaming\\Microsoft\\Windows\\Network Shortcuts" folder
        "D65231B0-B2F1-4857-A4CE-A8E7C6EA7D27",  # "C:\\WINDOWS\\SysWOW64" folder
        "A63293E8-664E-48DB-A079-DF759E0509F7",  # "AppData\\Roaming\\Microsoft\\Windows\\Templates" folder
        "B94237E7-57AC-4347-9151-B08C6C32D1F7",  # "C:\\ProgramData\\Microsoft\\Windows\\Templates" folder
    ]
    for folder_id in folder_ids:
        assert os.path.isdir(gsms.get_win_path(folder_id=folder_id))
        assert os.path.isdir(gsms.get_win_path(folder_id='{%s}' % folder_id))


def test_copy_image():
    src_image = os.path.join('tests', 'box.png')
    dst_image = "box_copy.png"

    gsms.copy_image(src_image, dst_image)
    assert os.path.isfile(dst_image)

    # compare the hash of each file
    with open(src_image, 'rb') as f:
        src_hash = hash(f.read())
    with open(dst_image, 'rb') as f:
        dst_hash = hash(f.read())
    assert src_hash == dst_hash

    # remove the copied image
    os.remove(dst_image)


def test_has_app(sunshine_default_apps):
    assert gsms.has_app(sunshine_apps=sunshine_default_apps, name="Desktop")
    assert not gsms.has_app(sunshine_apps=sunshine_default_apps, name="Not a valid app")


def test_add_game(sunshine_default_apps):
    name = "Added Game"
    gsms.add_game(sunshine_apps=sunshine_default_apps,
                  name=name,
                  logfile="added_game.log",
                  cmd="added_game.exe",
                  working_dir=os.path.join(os.path.curdir, 'test_directory'),
                  image_path=os.path.join(os.path.curdir, 'image_directory')
                  )
    assert gsms.has_app(sunshine_apps=sunshine_default_apps, name=name)


def test_known_path_to_absolute():
    # UUID is for "C:\Windows"
    paths = [
        r"::{F38BF404-1D43-42F2-9305-67DE0B28FC23}\System32",
        r"::{F38BF404-1D43-42F2-9305-67DE0B28FC23}",
    ]
    for path in paths:
        assert os.path.isdir(gsms.known_path_to_absolute(path=path))


def test_stopwatch():
    seconds = 5

    # measure the time taken by the function
    start_time = time.time()
    gsms.stopwatch(message="test_stopwatch", sec=seconds)
    stop_time = time.time()

    # calculate the difference between the start and stop times
    elapsed_time = stop_time - start_time

    assert elapsed_time >= seconds, f"Elapsed time: {elapsed_time} is not greater than or equal to {seconds}"
