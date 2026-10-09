name = "slash_trail"

version = "1.0.0"

authors = ["Arsam Ali"]

description = "Glowing slash trails for any animated object in Maya, with a Qt window for animators."

requires = [
    "python-3.10+",
    "maya-2024+",
]


def commands():
    env.PYTHONPATH.append("{root}/python")
