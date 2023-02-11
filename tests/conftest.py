# lib imports
import pytest


@pytest.fixture
def sunshine_default_apps():
    apps_json = {
        "env": {
            "PATH": "$(PATH);$(ProgramFiles(x86))\\Steam"
        },
        "apps": [
            {
                "name": "Desktop",
                "image-path": "desktop.png"
            },
            {
                "name": "Steam Big Picture",
                "detached": [
                    "steam steam://open/bigpicture"
                ],
                "image-path": "steam.png"
            }
        ]
    }

    return apps_json
