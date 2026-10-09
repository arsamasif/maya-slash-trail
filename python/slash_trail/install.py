"""Install slash_trail for one Maya user without touching PYTHONPATH.

Writes a Maya module file (``slash_trail.mod``) into the user's modules
folder. Maya reads module files at startup and adds the module's ``python``
folder to ``sys.path``, so the tool keeps working after a restart. The
installer also puts the folder on ``sys.path`` for the running session and
adds a "Slash" button to the current shelf. ``install_slash_trail.py`` at the
repo root calls ``run`` when the file is dropped into the viewport.

"""

import os
import sys

from slash_trail import __version__

MODULE_NAME = "slash_trail"
MOD_FILE = MODULE_NAME + ".mod"
SHELF_LABEL = "Slash"
SHELF_TAG = "slashTrailOpen"
SHELF_COMMAND = "from slash_trail import ui\nui.show()"
SHELF_ICON = "pythonFamily.png"


def module_text(root):
    """Return the contents of the module file for a repo folder.

    Args:
        root (str): Folder that holds ``python/slash_trail``.

    Returns:
        str: Module file text. Forward slashes keep it valid on every OS.

    """
    path = os.path.abspath(root).replace("\\", "/")
    return "+ {0} {1} {2}\nPYTHONPATH +:= python\n".format(MODULE_NAME, __version__, path)


def write_module_file(root, modules_dir):
    """Write (or overwrite) the module file.

    Args:
        root (str): Folder that holds ``python/slash_trail``.
        modules_dir (str): The user's Maya modules folder.

    Returns:
        str: Path of the written file.

    Raises:
        FileNotFoundError: If ``root`` does not contain the package.

    """
    package = os.path.join(root, "python", MODULE_NAME)
    if not os.path.isdir(package):
        raise FileNotFoundError("Missing slash_trail package: {0}".format(package))
    if not os.path.isdir(modules_dir):
        os.makedirs(modules_dir)
    path = os.path.join(modules_dir, MOD_FILE)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(module_text(root))
    return path


def add_to_session(root):
    """Make the package importable in the running Maya session.

    Args:
        root (str): Folder that holds ``python/slash_trail``.

    Returns:
        str: The ``python`` folder that is now on ``sys.path``.

    """
    python_dir = os.path.normpath(os.path.join(os.path.abspath(root), "python"))
    if python_dir not in [os.path.normpath(entry) for entry in sys.path]:
        sys.path.append(python_dir)
    return python_dir


def user_modules_dir():
    """Return the current user's Maya modules folder.

    Returns:
        str: ``<user app dir>/modules``, e.g. ``Documents/maya/modules``.

    """
    from maya import cmds

    return os.path.join(cmds.internalVar(userAppDir=True), "modules")


def add_shelf_button():
    """Add a "Slash" button to the current shelf, once.

    Returns:
        str: The button name, or None when Maya has no shelves (batch mode).

    """
    from maya import cmds
    from maya import mel

    # In batch mode the shelf variable is not declared; checking first avoids
    # a MEL error in the log.
    if mel.eval('whatIs "$gShelfTopLevel"') == "Unknown":
        return None
    top_level = mel.eval("$slashTrailShelfTop = $gShelfTopLevel")
    if not top_level or not cmds.tabLayout(top_level, exists=True):
        return None
    shelf = cmds.tabLayout(top_level, query=True, selectTab=True)
    for button in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        if cmds.shelfButton(button, exists=True) and (
            cmds.shelfButton(button, query=True, docTag=True) == SHELF_TAG
        ):
            return button
    return cmds.shelfButton(
        parent=shelf,
        label=SHELF_LABEL,
        annotation="Open the Slash Trail window",
        docTag=SHELF_TAG,
        image=SHELF_ICON,
        imageOverlayLabel=SHELF_LABEL,
        sourceType="python",
        command=SHELF_COMMAND,
    )


def run(root, modules_dir=None):
    """Install for the current user and report what was done.

    Args:
        root (str): Folder that holds ``python/slash_trail``.
        modules_dir (str): Modules folder; defaults to the user's.

    Returns:
        dict: ``module_file``, ``python_dir`` and ``shelf_button``.

    """
    module_file = write_module_file(root, modules_dir or user_modules_dir())
    python_dir = add_to_session(root)
    button = add_shelf_button()
    print("=" * 60)
    print(f"Slash Trail {__version__} installed")
    print(f"  module file : {module_file}")
    print(f"  python path : {python_dir}")
    print(f"  shelf button: {button or 'none (no shelves in this session)'}")
    print("Open it with the Slash shelf button, or: from slash_trail import ui; ui.show()")
    print("=" * 60)
    return {"module_file": module_file, "python_dir": python_dir, "shelf_button": button}
