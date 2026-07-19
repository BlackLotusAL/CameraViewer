import os


# Must be set before PySide2 creates QApplication in headless CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
