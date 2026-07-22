import os


# 无头测试必须在 PySide2 创建 QApplication 前设置平台插件。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
