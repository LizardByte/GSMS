Overview
========

About
-----

.. attention:: This project is archived since NVIDIA GeForce Experience is now end-of-life. GSMS is not planning to
   support the new NVIDIA app.

GSMS is a migration tool that allows users to import their custom apps and games from Nvidia GameStream to
`Sunshine <https://github.com/LizardByte/Sunshine>`_. Note that Nvidia GameStream support has ended in February 2023,
so users who relied on GameStream may want to consider migrating their library to Sunshine. This program updates the
`apps.json` file for Sunshine and copies the corresponding box art images to a specified directory. It reads shortcut
files (.lnk) from the default GameStream installation location. Additionally it can add games that were automatically
detected by Nvidia GameStream. The found games and applications are added to Sunshine as new apps. If an app with
the same name already exists in Sunshine, it will be skipped.

This program is intended for users who want to migrate their GameStream library to Sunshine and have their custom apps
and games available in Sunshine. It can save users the time and effort of manually adding each app to Sunshine and
finding and copying the corresponding box art images. The GameStream library and box-art images will not be modified.

To use this script, users will need to have both GameStream and Sunshine installed on their system and have a basic
understanding of using the command line. The script can be run with a variety of options to customize its behavior,
such as specifying the `apps.json` file to update, the directory where to copy box art images, and whether to preview
the changes without actually updating the `apps.json` file.

As an alternative option to migrating custom GameStream apps, you may also migrate any directory containing
``.lnk`` (shortcut) files. Below is the preferred directory structure of a custom directory. Cover images
(``box-art.png``) is optional.

.. code-block::

   .
   ├── A Game.lnk
   ├── Another Game.lnk
   └── StreamingAssets
       ├── A Game
       │   └── box-art.png
       └── Another Game
           └── box-art.png

Usage
-----
#. Download the latest version from our `latest release <https://github.com/LizardByte/GSMS/releases/latest>`_.
#. Double click the program to run with default arguments OR...
#. Open command prompt/terminal and execute the following command to see available options.

   .. Tip:: This code requires no modification if you download the program to your Downloads directory, otherwise
      be sure to change the directory accordingly.

   .. code-block:: batch

      cd /d "%userprofile%/Downloads"
      gsms.exe --help

Command Line
^^^^^^^^^^^^

To run the script, use the following command:

.. code-block:: batch

   gsms.exe [OPTIONS]

OPTIONS

``--apps, -a``
    Specify the sunshine ``apps.json`` file to update, otherwise we will attempt to use the ``apps.json`` file from the
    default Sunshine installation location.

``--image_path, -i``
    Specify the full directory where to copy box art to. If not specified, box art will be copied to
    ``%USERPROFILE%/Pictures/Sunshine``

``--shortcut_dir, -s``
    Specify a custom shortcut directory. If not specified, ``%localappdata%/NVIDIA Corporation/Shield Apps``
    will be used.

``--dry_run, -d``
    If set, the `apps.json` file will not be overwritten and box-art images won't be copied. Use this flag to preview
    the changes that would be made without committing them.

``--no_sleep``
    If set, the script will not pause for 10 seconds at the end of the import.

``--nv_add_autodetect, -n``
    If set, the script will add all streamable apps from Nvidia GameStream's automatically detected applications.

Examples
^^^^^^^^

To migrate all GameStream apps to Sunshine and copy box art images to the default directory:

.. code-block:: batch

   gsms.exe

To migrate all GameStream apps to Sunshine and copy box art images to a custom directory:

.. code-block:: batch

   gsms.exe --image_path C:\\Users\MyUser\\Photos\\Sunshine

To preview the changes that would be made without actually updating the `apps.json` file:

.. code-block:: batch

   gsms.exe --dry_run

Integrations
------------

.. image:: https://img.shields.io/github/actions/workflow/status/lizardbyte/gsms/CI.yml?branch=master&label=CI%20build&logo=github&style=for-the-badge
   :alt: GitHub Workflow Status (CI)
   :target: https://github.com/LizardByte/GSMS/actions/workflows/CI.yml?query=branch%3Amaster

Support
-------

Our support methods are listed in our
`LizardByte Docs <https://lizardbyte.readthedocs.io/en/latest/about/support.html>`_.

Downloads
---------

.. image:: https://img.shields.io/github/downloads/lizardbyte/gsms/total?style=for-the-badge&logo=github
   :alt: GitHub Releases
   :target: https://github.com/LizardByte/GSMS/releases/latest

Stats
-----
.. image:: https://img.shields.io/github/stars/lizardbyte/gsms?logo=github&style=for-the-badge
   :alt: GitHub stars
   :target: https://github.com/LizardByte/GSMS

.. image:: https://img.shields.io/codecov/c/gh/LizardByte/GSMS?token=IC678AQFBI&style=for-the-badge&logo=codecov&label=codecov
   :alt: Codecov
   :target: https://codecov.io/gh/LizardByte/GSMS
