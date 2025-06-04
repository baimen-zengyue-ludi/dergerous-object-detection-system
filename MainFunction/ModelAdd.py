from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import QThread, Signal, QObject, Qt

class YOLOLoaderThread(QThread):
    def __init__(self, yolo_loader):
        super().__init__()
        self.yolo_loader = yolo_loader

    def run(self):
        # 在这里加载模型，YOLOLoader 会负责发射信号
        self.yolo_loader.load_model()

class YOLOImportThread(QThread):
    import_finished = Signal(bool)  # 定义一个信号来通知引入是否完成

    def run(self):
        try:
            from ultralytics import YOLOv10
            self.import_finished.emit(True)  # 引入成功
        except Exception as e:
            print(f"An error occurred while importing YOLOv10: {e}")
            self.import_finished.emit(False)  # 引入失败

class YOLOLoader(QObject):
    result_ready = Signal(object)  # 定义一个信号来传递加载完成后的模型或错误信息

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path
        self.model = None

    def load_model(self):
        from ultralytics import YOLOv10
        try:
            self.model = YOLOv10(self.model_path)  # 加载 YOLO 模型
            self.result_ready.emit(self.model)  # 发射信号，传递加载完成的模型
        except Exception as e:
            print(f"An error occurred while loading the YOLO model: {e}")
            self.result_ready.emit(None)  # 或者发射一个特定的错误信息对象

# 加载窗口类
class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在加载模型...")
        self.setFixedSize(300, 100)
        self.layout = QVBoxLayout(self)
        self.label = QLabel("正在加载模型，请稍候...", self)
        self.layout.addWidget(self.label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # 设置范围为0到0，使进度条显示为忙碌状态
        self.layout.addWidget(self.progress_bar)
        # 禁用关闭按钮（X按钮）
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
