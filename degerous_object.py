import requests
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QLineEdit,QLabel
from PySide6.QtCore import QSettings, QTimer, QEvent, Qt
from PySide6.QtGui import QPixmap, QImage
import cv2
import pymysql
import os
import shutil
import ffmpeg

from MainFunction.ModelAdd import YOLOLoader, YOLOLoaderThread, LoadingDialog, YOLOImportThread
from MainFunction.image_select import image_pred

from degerous_object_ui import Ui_MainWindow

class MyWindow(QMainWindow, Ui_MainWindow):
      
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Dangerous goods detection", "LoginApp")
        self.setupUi(self)
        self.stackedWidget.setCurrentIndex(0)
        
        self.timer_video = QTimer(self)
        self.timer_video.timeout.connect(self.process_and_display_frame)
        
        # 设置combox控件选择为初始
        self.comboBox_select_model.setCurrentIndex(-1)
        
        # 设置初始没有选择模型地址
        self.model_path = None
        self.model = None
        
        self.load_credentials()
        self.bind_slots()
        
        # 设置窗口大小和位置
        self.setGeometry(100, 100, 1200, 600)
        
        # 初始化置信度阈值
        self.confidence_threshold = 0.4  # 设置默认置信度阈值
        self.iou_threshold = 0.5  # 设置默认IOU阈值
        
        self.on_page_changed(0)  # 初始化时隐藏菜单栏
        
        # 绑定 horizontalSlider 的值变化信号到槽函数
        self.horizontalSlider.valueChanged.connect(self.update_confidence_threshold)

        # 启动线程引入 YOLOv10 库
        self.yolo_import_thread = YOLOImportThread()
        self.yolo_import_thread.import_finished.connect(self.on_yolo_import_finished)
        self.yolo_import_thread.start()

        # 初始化上次选择的文件夹路径
        self.last_directory = self.settings.value("last_directory", "我的电脑")

        # 检查并创建 test_image 文件夹
        self.ensure_test_image_folder_exists()

        # 连接页面切换信号到槽函数
        self.stackedWidget.currentChanged.connect(self.on_page_changed)

        # 初始化检测类型
        self.detection_type = None
        self.populate_model_combobox()# 填充模型选择框
        self.video_path = None  # 初始化视频路径属性
    
    def populate_model_combobox(self):
        """扫描 model 文件夹中的文件，并将文件名添加到 QComboBox 控件中"""
        model_dir = os.path.join(os.path.dirname(__file__), 'model')
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            print(f"Created directory: {model_dir}")
        
        model_files = [f for f in os.listdir(model_dir) if f.endswith('.pt')]
        self.comboBox_select_model.clear()
        for model_file in model_files:
            self.comboBox_select_model.addItem(model_file)
        
    def ensure_test_image_folder_exists(self):
        output_dir = os.path.join(os.path.dirname(__file__), 'test_image')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
                 
    def on_yolo_import_finished(self, success):
        if success:
            print("YOLOv10 library imported successfully.")
        else:
            print("Failed to import YOLOv10 library.")
                   
    def update_confidence_threshold(self, value):
        """更新置信度阈值"""
        self.confidence_threshold = 0.2 + value / 100.0 * 0.6  # 将值转换为 0.2 到 0.8 之间
        self.label_2.setText(f"当前置信度阈值: {self.confidence_threshold:.2f}")
        print(f"Updated confidence threshold: {self.confidence_threshold}")

        # 重新检测并显示图片
        if hasattr(self, 'img') and self.img is not None:
            self.img = cv2.imread(self.file_path)
            if self.img is not None:
                image_pred(self, 0, self.confidence_threshold,self.iou_threshold)

                # 保存检测好的图片
                output_dir = os.path.join(os.path.dirname(__file__), 'save_continue', 'test_image')  # 保存目录
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                output_path = os.path.join(output_dir, os.path.basename(self.file_path))
                cv2.imwrite(output_path, self.img)
                print(f"Image saved to {output_path}")

                # 检查并删除多余的图片
                self.cleanup_old_images(output_dir, max_images=20)
            else:
                print("Failed to read image from file path.")

        # 重新检测并显示视频帧
        if hasattr(self, 'video') and self.video.isOpened():
            self.process_and_display_frame()

        # 重新检测并显示摄像头帧
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.update_frame()
            
    def cleanup_old_images(self, directory, max_images):
        """删除目录中多余的图片，保留最新的 max_images 张"""
        images = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if len(images) > max_images:
            images.sort(key=os.path.getmtime)  # 按修改时间排序
            for image in images[:-max_images]:
                os.remove(image)
                print(f"Deleted old image: {image}")
                    
    def load_credentials_return(self):
        """加载保存的账号、密码及复选框状态"""
        account = self.settings.value("account", "")
        password = self.settings.value("password", "")
        checkbox_state = self.settings.value("checkbox_state", False, type=bool)
        if account:  # 如果有保存的账号
            self.lineEdit.setText(account)  # 填充账号

            if account and password:
                # 填充到界面上的输入框
                self.checkBox.setChecked(checkbox_state)
                if checkbox_state:
                    self.lineEdit.setText(account)
                    self.lineEdit_2.setText(password)
                                      
    def load_credentials(self):
        """加载保存的账号、密码及复选框状态"""
        account = self.settings.value("account", "")
        password = self.settings.value("password", "")
        checkbox_state = self.settings.value("checkbox_state", False, type=bool)
        checkbox_2_state = self.settings.value("checkbox_2_state", False, type=bool)

        if account:  # 如果有保存的账号
            self.lineEdit.setText(account)  # 填充账号

            if account and password:
                # 填充到界面上的输入框
                self.checkBox.setChecked(checkbox_state)
                if checkbox_state:
                    self.lineEdit.setText(account)
                    self.lineEdit_2.setText(password)
                    #解除自动登录框的设置
                    self.checkBox_2.setEnabled(True)
                    self.checkBox_2.setChecked(checkbox_2_state)
                if checkbox_2_state:
                    self.logic_menthon()

            
            #print("已加载保存的账号、密码和复选框状态")
        else:
            #print("没有保存的账号和密码")
            pass
        
    def logic_menthon(self):
        # 拿到账号
        account = self.lineEdit.text()
        # 拿到密码
        password = self.lineEdit_2.text()
        
        self.save_credentials(self.lineEdit.text(), self.lineEdit_2.text(), self.checkBox.isChecked(), self.checkBox_2.isChecked()) 

        if self.lineEdit.text() == '' or self.lineEdit_2.text() == '':
            # 创建一个消息框
            msg21 = QMessageBox()
            # 设置消息框的标题和内容
            msg21.setWindowTitle("提示")
            msg21.setText("请输入账号和密码")
            msg21.setIcon(QMessageBox.Information)

            # 添加按钮
            msg21.setStandardButtons(QMessageBox.Ok)
        
            # 显示消息框并等待用户操作
            msg21.exec()
        else:
            try:
                url = 'http://127.0.0.1:5000/login'  # 服务器地址和端口
                data = {'username': account, 'password': password}
                response = requests.post(url, json=data)
                response_data = response.json()

                if response.status_code == 200 and response_data['status'] == 'success':
                    self.stackedWidget.setCurrentIndex(1)
                else:
                    # 创建一个消息框
                    msg = QMessageBox()
                    # 设置消息框的标题和内容
                    msg.setWindowTitle("提示")
                    msg.setText(response_data.get('message', '登录失败'))
                    msg.setIcon(QMessageBox.Information)

                    # 添加按钮
                    msg.setStandardButtons(QMessageBox.Ok)
        
                    # 显示消息框并等待用户操作
                    msg.exec()
            except Exception as e:
                print(e)
                # 创建一个消息框
                msg = QMessageBox()
                # 设置消息框的标题和内容
                msg.setWindowTitle("错误")
                msg.setText("无法连接到服务器")
                msg.setIcon(QMessageBox.Critical)

                # 添加按钮
                msg.setStandardButtons(QMessageBox.Ok)
        
                # 显示消息框并等待用户操作
                msg.exec()
                
    def resister_main(self):
        self.stackedWidget_2.setCurrentIndex(1)
        
    def register_methon(self):
        self.name = self.lineEdit_8.text()
        self.password = self.lineEdit_9.text()
        self.repassword = self.lineEdit_10.text()
        self.protectpass = self.lineEdit_11.text()
        self.retpassword = self.lineEdit_12.text()
        
        # 设置密码输入框的回显模式为密码模式
        self.lineEdit_9.setEchoMode(QLineEdit.Password)
        self.lineEdit_10.setEchoMode(QLineEdit.Password)
        
        if self.name == "" or self.password == "" or self.protectpass == "" or self.retpassword == "":
            # 创建一个消息框
            msg = QMessageBox()
            # 设置消息框的标题和内容
            msg.setWindowTitle("提示")
            msg.setText("所有字段都是必填的")
            msg.setIcon(QMessageBox.Information)

            # 添加按钮
            msg.setStandardButtons(QMessageBox.Ok)
        
            # 显示消息框并等待用户操作
            msg.exec()
            return
        
        if self.password != self.repassword:
            # 创建一个消息框
            msg3 = QMessageBox()
            # 设置消息框的标题和内容
            msg3.setWindowTitle("提示")
            msg3.setText("两次密码输入不一致")
            msg3.setIcon(QMessageBox.Information)

            # 添加按钮
            msg3.setStandardButtons(QMessageBox.Ok)

            # 显示消息框并等待用户操作
            msg3.exec()
            return
        
        # 发送注册请求到服务器
        url = 'http://127.0.0.1:5000/register'
        data = {
            'name': self.name,
            'password': self.password,
            'protectpass': self.protectpass,
            'retpassword': self.retpassword
        }
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            # 注册成功
            self.stackedWidget_2.setCurrentIndex(0)
        else:
            # 注册失败，显示错误信息
            msg = QMessageBox()
            msg.setWindowTitle("错误")
            msg.setText(response.json().get('message', '注册失败'))
            msg.setIcon(QMessageBox.Critical)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
    
    def renewpassword_main(self):
        self.stackedWidget_2.setCurrentIndex(2)
        self.select_protect_password_button.clicked.connect(self.SelectProtectPassword)
        self.updata_password.clicked.connect(self.renewpassword_methon)
        
    def SelectProtectPassword(self):
        
        #数据库连接
        self.db = pymysql.connect(host='localhost',port=3306,user='root',passwd='430538',database='theundergraduator',charset='utf8')
        cursor=self.db.cursor()
        
        if self.lineEdit_13.text()=="":
            
            #设置一个消息框
            msg=QMessageBox()
            msg.setWindowTitle("提示")
            msg.setText("账号为空")
            msg.setIcon(QMessageBox.Information)
            
            msg.setStandardButtons(QMessageBox.Ok)
            
            msg.exec()
            
        else:
            try:
                sql='select security_question from users where username=%s'
                value=self.lineEdit.text()
                cursor.execute(sql,value)
            
                #找出查询后的内容
                rows = cursor.fetchall()
                #print(rows)
                rowshow=str(rows[0])
                rowshow_cleaned=rowshow.replace("(", "").replace(")", "").replace(",", "").replace("'", "")
                self.textEdit.setText("回答下面密保问题:\n" +rowshow_cleaned )                
                
                        
            #抛出异常(以免程序执行sql语句时报错)   
            except Exception as e:      
                print(e)
                self.db.rollback()
        
        
        
        self.db.close()
        cursor.close()
    
    def renewpassword_methon(self):
        self.password = self.lineEdit_14.text()
        self.repassword = self.lineEdit_15.text()
        self.protectpass = self.lineEdit_17.text()
        
        if self.password == "":
            # 创建一个消息框
            msg2 = QMessageBox()
            # 设置消息框的标题和内容
            msg2.setWindowTitle("提示")
            msg2.setText("请输入重置密码")
            msg2.setIcon(QMessageBox.Information)

            # 添加按钮
            msg2.setStandardButtons(QMessageBox.Ok)
        
            # 显示消息框并等待用户操作
            msg2.exec()
            return
        
        if self.password != self.repassword:
            # 创建一个消息框
            msg3 = QMessageBox()
            # 设置消息框的标题和内容
            msg3.setWindowTitle("提示")
            msg3.setText("两次密码输入不一致")
            msg3.setIcon(QMessageBox.Information)

            # 添加按钮
            msg3.setStandardButtons(QMessageBox.Ok)
        
            # 显示消息框并等待用户操作
            msg3.exec()
            return
        
        if self.protectpass == "":
            # 创建一个消息框
            msg4 = QMessageBox()
            # 设置消息框的标题和内容
            msg4.setWindowTitle("提示")
            msg4.setText("请输入密保答案")
            msg4.setIcon(QMessageBox.Information)
                
            # 添加按钮
            msg4.setStandardButtons(QMessageBox.Ok)

            # 显示消息框并等待用户操作
            msg4.exec()
            return
        
        # 发送重置密码请求到服务器
        url = 'http://127.0.0.1:5000/reset_password'
        data = {
            'username': self.lineEdit_13.text(),
            'password': self.password,
            'protectpass': self.protectpass
        }
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            # 重置密码成功
            msg6 = QMessageBox()
            msg6.setWindowTitle("提示")
            msg6.setText("密码已经重置完成")
            msg6.setIcon(QMessageBox.Information)
            msg6.setStandardButtons(QMessageBox.Ok)
            msg6.exec()
        else:
            # 重置密码失败，显示错误信息
            msg5 = QMessageBox()
            msg5.setWindowTitle("错误")
            msg5.setText(response.json().get('message', '重置密码失败'))
            msg5.setIcon(QMessageBox.Critical)
            msg5.setStandardButtons(QMessageBox.Ok)
            msg5.exec()
    
    def save_credentials(self, account, password,remeberPassword,authourityLogic):
        """保存账号和密码"""
        self.settings.setValue("account", account)
        self.settings.setValue("password", password)
        self.settings.setValue("checkbox_state", remeberPassword)
        self.settings.setValue("checkbox_2_state", authourityLogic)
        
        #print("已保存账号和密码")
    
    def renturn_logic(self):
        
        # 停止检测
        self.stop_detection()

        # 获取当前页面的所有 QLineEdit 控件
        current_page = self.stackedWidget.currentWidget()  # 获取当前页面的小部件
        line_edits = current_page.findChildren(QLineEdit)  # 查找页面中的所有 QLineEdit 控件
    
        # 清空每个 QLineEdit 的文本内容
        for line_edit in line_edits:
            line_edit.clear()  # 清空文本
        
        # 获取当前页面的所有 QLabel 控件
        labels = current_page.findChildren(QLabel)  # 查找页面中的所有 QLabel 控件

        # 清空每个 QLabel 的内容
        for label in labels:
            label.clear()  # 清空内容

        # 将 self.file_path、self.model 设置为空值
        self.file_path = None
        self.model = None
        self.comboBox_select_model.setCurrentIndex(-1)
        
        self.stackedWidget.setCurrentIndex(0)
        self.stackedWidget_2.setCurrentIndex(0)
        self.load_credentials_return()
        #print("renturn_logic executed")  # 调试信息
        
    def image_use(self):
        self.clearLabel()
        
        # 创建一个关闭事件对象
        self.mutex = self.Modeltask()
        if (self.mutex == False):
            # 创建一个消息框
            msg212 = QMessageBox()
            # 设置消息框的标题和内容
            msg212.setWindowTitle("提示")
            msg212.setText("请先添加模型")
            msg212.setIcon(QMessageBox.Information)
            # 添加按钮
            msg212.setStandardButtons(QMessageBox.Ok)
            # 显示消息框并等待用户操作
            msg212.exec()
            return 
        
        # 创建一个关闭事件对象
        close_event = QEvent(QEvent.Close)
        # 调用 closeEvent 方法
        self.closeEvent(close_event)
        
        file_dialog = QFileDialog(self)
        file_dialog.setDirectory(self.last_directory)
        self.file_path = file_dialog.getOpenFileName(self, "选择图片", self.last_directory, "Images (*.jpg *.png *.jpeg)")[0]
        if self.file_path:
            self.last_directory = os.path.dirname(self.file_path)
            self.settings.setValue("last_directory", self.last_directory)
            self.img = cv2.imread(self.file_path)  # 使用 OpenCV 读取图像
            self.img2 = self.img.copy()
            image_pred(self, 0, self.confidence_threshold,self.iou_threshold)  # 传递置信度阈值
            
            # 调整原始图片大小以适应显示区域
            display_width = self.output.width()
            display_height = self.output.height()
            self.img2 = cv2.resize(self.img2, (display_width, display_height), interpolation=cv2.INTER_AREA)

             # 转换 NumPy 数组为 QImage
            img_rgb = cv2.cvtColor(self.img2, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            
             # 调整图片大小以适应显示区域
            pixmap = pixmap.scaled(display_width, display_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
            self.input.setPixmap(pixmap)
            
            # 保存检测好的图片
            output_dir = os.path.join(os.path.dirname(__file__), 'save_continue/test_image')  # 保存目录
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)         
            output_path = os.path.join(output_dir, os.path.basename(self.file_path))
            cv2.imwrite(output_path, self.img)      
            print(f"Image saved to {output_path}")  
                                                    
            # 检查并删除多余的图片
            self.cleanup_old_images(output_dir, max_images=20)

    def cleanup_old_images(self, directory, max_images):
        """删除目录中多余的图片，保留最新的 max_images 张"""
        images = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if len(images) > max_images:
            images.sort(key=os.path.getmtime)  # 按修改时间排序
            for image in images[:-max_images]:
                os.remove(image)
                print(f"Deleted old image: {image}")

    def ModelSelect(self):
        
        #from ultralytics import YOLOv10
        #self.model_path="first25task/model/yolov10_first.pt"
        
        model_name = self.comboBox_select_model.currentText()
        model_dir = os.path.join(os.path.dirname(__file__), 'model')
        self.model_path = os.path.join(model_dir, model_name)

        if not os.path.exists(self.model_path):
            print(f"Model file {self.model_path} does not exist.")
            return
        
        #如果选择空值，自动结束
        if self.comboBox_select_model.currentIndex() == -1:
            return 
        
        self.LoadingDialog = LoadingDialog()
        
        # 当按钮被点击时，加载 YOLOv10 模型
        self.yolo_loader = YOLOLoader(self.model_path)
        self.yolo_loader.result_ready.connect(self.on_model_loaded)  # 连接信号到槽函数
        self.thread = YOLOLoaderThread(self.yolo_loader)
        self.thread.start()  # 启动线程
        self.LoadingDialog.exec()  # 显示加载对话框
        
        '''
        from MainFunction.ModelAdd import on_load_model_clicked
        
        self.model_select=self.comboBox_select_model.currentText()
        on_load_model_clicked(self)
        
        '''
    
    def on_model_loaded(self, model):
        # 这个槽函数会在主线程中被调用
        if model is not None:
            # print("Model loaded successfully:", model)
            self.model=model
            self.LoadingDialog.close()
            # 在这里更新界面或执行其他操作
        else:
            print("Failed to load model.")
            # 在这里显示错误信息或执行其他操作
            
    def camera_main(self):
        self.mutex = self.Modeltask()
        if self.mutex == False:
            # 创建一个消息框
            msg212 = QMessageBox()
            # 设置消息框的标题和内容
            msg212.setWindowTitle("提示")
            msg212.setText("请先添加模型")
            msg212.setIcon(QMessageBox.Information)
            # 添加按钮
            msg212.setStandardButtons(QMessageBox.Ok)
            # 显示消息框并等待用户操作
            msg212.exec()
            return 
        
        
        from PySide6.QtCore import QTimer
        import cv2
        
        #创建摄像头对象
        self.cap = cv2.VideoCapture(0)  # <- 正确的对象初始化
    
        # 创建并启动定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 每30毫秒更新一次帧
        #print(self.cap.isOpened())
    
    def update_frame(self):
        import cv2
        from PySide6.QtGui import QPixmap, QImage
    
        # 从摄像头读取帧
        success, self.img = self.cap.read()
        if not success:
            return
        # 调试打印：确认读取到了帧
        #print("Frame captured successfully.")
    
        # 转换颜色空间从BGR到RGB
        self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
    
        # 转换NumPy数组为QImage
        h, w, ch = self.img.shape
        bytes_per_line = ch * w
        q_image = QImage(self.img.data, w, h, bytes_per_line, QImage.Format_RGB888)
    
        # 将QImage转为QPixmap，并设置到QLabel
        pixmap = QPixmap.fromImage(q_image)
        image_pred(self, 2, self.confidence_threshold,self.iou_threshold)
        self.input.setPixmap(pixmap)
        
    def closeEvent(self, event):
        # 在退出前自动停止检测（此处确保视频、摄像头等资源释放并保存视频文件）
        self.stop_detection()
        # 其他关闭处理逻辑（比如释放其他已打开文件等）
        event.accept()

    def open_video(self):
        # 检测模型是否存在
        self.mutex = self.Modeltask()
        if self.mutex == False:
            msg212 = QMessageBox()
            msg212.setWindowTitle("提示")
            msg212.setText("请先添加模型")
            msg212.setIcon(QMessageBox.Information)
            msg212.setStandardButtons(QMessageBox.Ok)
            msg212.exec()
            return 

        close_event = QEvent(QEvent.Close)
        self.closeEvent(close_event)

        file_dialog = QFileDialog(self)
        file_dialog.setDirectory(self.last_directory)
        file_path = file_dialog.getOpenFileName(self, "选择视频", self.last_directory, "Videos (*.mp4)")[0]
        if file_path:
            self.file_path = file_path
            self.video_path = file_path  # 新增赋值，保证后续使用有定义
            self.last_directory = os.path.dirname(self.file_path)
            self.settings.setValue("last_directory", self.last_directory)
            self.video = cv2.VideoCapture(self.file_path)

            # 保存原始视频名
            self.original_video_title = os.path.splitext(os.path.basename(self.file_path))[0]

            # 设置输出视频文件保存的路径到 save_continue/save_video 下（如果没有则创建）
            output_video_folder = os.path.join(os.path.dirname(__file__), 'save_continue', 'save_video')
            if not os.path.exists(output_video_folder):
                os.makedirs(output_video_folder)
                print(f"Created directory: {output_video_folder}")

            # 输出视频命名为原视频的命名
            self.output_video_path = os.path.join(output_video_folder, f"{self.original_video_title}.mp4")
            # 如果存在相同的保存的视频，则替换掉
            if os.path.exists(self.output_video_path):
                os.remove(self.output_video_path)
                print(f"Existing video {self.output_video_path} replaced。")

            # 初始化 VideoWriter（假设 image_pred 函数会在 self.img 中绘制检测标注框）
            fps = self.video.get(cv2.CAP_PROP_FPS)
            self.fps = fps  # 保存fps供后续计算
            width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.video_frame_size = (width, height)  # 保存原始视频尺寸
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.output_video_writer = cv2.VideoWriter(self.output_video_path, fourcc, fps, self.video_frame_size)
            print(f"Video writer initialized: {self.output_video_path}")
            
            # 初始化保存的秒数为0
            self.saved_seconds = 0  
            self.timer_video.start(30)  # 每30毫秒更新一次帧

    def process_and_display_frame(self):
        # 检查视频捕获对象是否已初始化
        if not self.video:
            return

        ret, frame = self.video.read()
        if not ret:
            if hasattr(self, 'timer_video') and self.timer_video.isActive():
                self.timer_video.stop()
            return

        # 保留原始帧（高分辨率）用于保存视频
        original_frame = frame.copy()
        
        # 在原始帧上调用 image_pred，绘制检测标注
        self.img = original_frame.copy()
        image_pred(self, 1, self.confidence_threshold, self.iou_threshold)
        
        # 写入带标注的原始帧到输出视频
        if hasattr(self, 'output_video_writer'):
            self.output_video_writer.write(self.img)

        # 为了显示，将检测后的帧调整为按照 output 控件尺寸
        display_frame = cv2.resize(self.img, (self.output.width(), self.output.height()), interpolation=cv2.INTER_AREA)
        display_frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = display_frame_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(display_frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        
        # 同时设置 input 和 output 为相同图像
        self.input.setPixmap(pixmap)
        self.output.setPixmap(pixmap)

    def stop_detection(self):
        """停止视频检测和摄像头检测，并自动保存视频文件"""
        # 停止摄像头检测
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            self.detection_type = 'camera'
            print("Camera detection stopped.")

        # 停止视频检测
        if hasattr(self, 'video') and self.video.isOpened():
            self.video_position = self.video.get(cv2.CAP_PROP_POS_FRAMES)
            # 计算当前播放秒数（向下取整）
            current_seconds = int(self.video_position / self.fps)
            self.saved_seconds = current_seconds
            self.video.release()
            self.timer_video.stop()
            self.detection_type = 'video'
            print("Video detection stopped.")
            # 释放视频写入器并确保文件保存
            if hasattr(self, 'output_video_writer') and self.output_video_writer.isOpened():
                self.output_video_writer.release()
                print(f"Video writer released, video saved to {self.output_video_path}")

        # 停止普通定时器
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
            print("Timer stopped。")

    def Modeltask(self):
        if not self.model:
            # 创建一个关闭事件对象
            close_event = QEvent(QEvent.Close)
    
            # 调用 closeEvent 方法
            self.closeEvent(close_event)
            return False
    
    def clearLabel(self):
        self.input.setPixmap(QPixmap())     # 清空 input 中的内容
        self.output.setPixmap(QPixmap())    # 清空 output 中的内容
    
    def on_page_changed(self, index):
        """根据当前页面索引显示或隐藏主菜单"""
        if index == 1:  # main_page 的索引是 1
            self.menuBar.show()
        else:
            self.menuBar.hide()
    
    def open_test_image_folder(self):
        """打开 test_image 文件夹"""
        test_image_dir = os.path.join(os.path.dirname(__file__), 'save_continue', 'test_image')
        if not os.path.exists(test_image_dir):
            os.makedirs(test_image_dir)
            print(f"Created directory: {test_image_dir}")
        os.startfile(test_image_dir)
        
    def ensure_test_image_folder_exists(self):
        output_dir = os.path.join(os.path.dirname(__file__), 'save_continue', 'test_image')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
    
    def stop_detection(self):
        """停止视频检测和摄像头检测"""
        # 停止摄像头检测
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            self.detection_type = 'camera'
            print("Camera detection stopped.")
    
        # 停止视频检测
        if hasattr(self, 'video') and self.video.isOpened():
            self.video_position = self.video.get(cv2.CAP_PROP_POS_FRAMES)
            # 计算当前播放秒数（向下取整）
            current_seconds = int(self.video_position / self.fps)
            self.saved_seconds = current_seconds
            self.video.release()
            self.timer_video.stop()
            self.detection_type = 'video'
            print("Video detection stopped。")
            if hasattr(self, 'output_video_writer'):
                self.output_video_writer.release()
    
            # 删除重命名逻辑，保留输出视频的文件名为原视频名
            # 原先的代码如下（现已删除）：
            # final_output_path = os.path.join(
            #     os.path.dirname(self.output_video_path),
            #     f"{self.original_video_title}_played_{self.saved_seconds}s.mp4"
            # )
            # os.rename(self.output_video_path, final_output_path)
            # print(f"Final video saved to {final_output_path}")
    
        # 停止定时器
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
            print("Timer stopped。")
    
        # 确保视频定时器停止
        if hasattr(self, 'timer_video') and self.timer_video.isActive():
            self.timer_video.stop()
            print("Video timer stopped。")
    
        # 释放新的视频文件资源
        if hasattr(self, 'output_video_writer') and self.output_video_writer.isOpened():
            self.output_video_writer.release()

        # 拼接所有视频文件
        if hasattr(self, 'video_files') and self.video_files:
            final_output_path = os.path.join(os.path.dirname(self.output_video_path), f"{os.path.splitext(os.path.basename(self.file_path))[0]}_final.mp4")
            self.concatenate_videos(self.video_files, final_output_path)
            print(f"Final video saved to {final_output_path}")

    def continue_detection(self):
        """继续视频检测和摄像头检测"""
        if self.detection_type == 'camera':
            # 继续摄像头检测
            if hasattr(self, 'cap') and not self.cap.isOpened():
                self.cap.open(0)
                self.timer.start(30)
                print("Camera detection continued。")
        elif self.detection_type == 'video':
            # 继续视频检测
            if self.video_path:
                self.video = cv2.VideoCapture(self.video_path)
                self.video.set(cv2.CAP_PROP_POS_FRAMES, self.video_position)
                self.timer_video.start(30)
                print("Video detection continued。")
                
                # 重新打开视频写入器，追加新的帧
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                fps = self.video.get(cv2.CAP_PROP_FPS)
                width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.output_video_writer = cv2.VideoWriter(self.output_video_path, fourcc, fps, (width, height), True)
                print("Video writer continued。")
        
    def cleanup_old_videos(self, directory, max_videos):
        """删除目录中多余的视频，保留最新的 max_videos 个"""
        videos = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.mp4')]
        if len(videos) > max_videos:
            videos.sort(key=os.path.getmtime)  # 按修改时间排序
            for video in videos[:-max_videos]:
                os.remove(video)
                print(f"Deleted old video: {video}")

    def open_video_continue_folder(self):
        """打开 save_video 文件夹"""
        video_continue_dir = os.path.join(os.path.dirname(__file__), 'save_continue', 'save_video')
        if not os.path.exists(video_continue_dir):
            os.makedirs(video_continue_dir)
            print(f"Created directory: {video_continue_dir}")
        os.startfile(video_continue_dir)

    def update_iou_threshold(self, value):
        """更新IOU阈值"""
        self.iou_threshold = value / 100.0  # 假设滑动条范围为0~100，50对应0.50
        self.IOU_label.setText(f"当前IOU阈值: {self.iou_threshold:.2f}")
        print(f"Updated IOU threshold: {self.iou_threshold:.2f}")

        # 重新检测并显示图片
        if hasattr(self, 'img') and self.img is not None:
            self.img = cv2.imread(self.file_path)
            if self.img is not None:
                image_pred(self, 0, self.confidence_threshold, self.iou_threshold)
                output_dir = os.path.join(os.path.dirname(__file__), 'save_continue', 'test_image')
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                output_path = os.path.join(output_dir, os.path.basename(self.file_path))
                cv2.imwrite(output_path, self.img)
                print(f"Image saved to {output_path}")
                self.cleanup_old_images(output_dir, max_images=20)
            else:
                print("Failed to read image from file path。")

        # 重新检测视频帧
        if hasattr(self, 'video') and self.video.isOpened():
            self.process_and_display_frame()

        # 重新检测摄像头帧
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.update_frame()

    def bind_slots(self):
        self.logic_main_putton.clicked.connect(self.logic_menthon)
        self.designer_putton.clicked.connect(self.resister_main)
        self.renewpassword_button.clicked.connect(self.renewpassword_main)
        self.exit_main_putton.clicked.connect(self.renturn_logic)
        self.exit_logic_putton.clicked.connect(self.renturn_logic)
        self.exit_renew_logic_putton.clicked.connect(self.renturn_logic)
        self.register_putton.clicked.connect(self.register_methon)
        self.image_detection.triggered.connect(self.image_use)  
        self.comboBox_select_model.currentIndexChanged.connect(self.ModelSelect)
        self.video_detection.triggered.connect(self.open_video)                        
        self.cammer_detection.triggered.connect(self.camera_main)
        self.horizontalSlider.valueChanged.connect(self.update_confidence_threshold)
        self.horizontalSlider_IOC.valueChanged.connect(self.update_iou_threshold)  # 滑动 IOU 滑块时更新 IOU 阈值并重新检测
        self.actionhug.triggered.connect(self.open_test_image_folder)
        self.stop_Continue.clicked.connect(self.stop_detection)
        self.Continue_test.clicked.connect(self.continue_detection)
        self.actionfaf.triggered.connect(self.open_video_continue_folder) 
              
if __name__=='__main__':
    app=QApplication([])
    window=MyWindow()
    window.show()
    app.exec()
