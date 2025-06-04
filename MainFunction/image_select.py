import cv2
import numpy as np
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

# 预定义每个类的颜色
CLASS_COLORS = {
    'Pistol': (255, 0, 0),          # 红色
    'Rope': (0, 255, 0),            # 绿色
    'Screw Driver': (0, 0, 255),    # 蓝色
    'Wrench': (255, 255, 0),        # 黄色
    'hammer': (255, 0, 255),        # 洋红色
    'knife': (0, 255, 255),         # 青色
    'pliers': (128, 0, 128),        # 紫色
    'rifle': (128, 128, 0),         # 橄榄色
    'stone': (0, 128, 128)          # 青绿色
}

def calculate_iou(box1, box2):
    """计算两个标注框的IOU值"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1 - w1 / 2, x2 - w2 / 2)
    yi1 = max(y1 - h1 / 2, y2 - h2 / 2)
    xi2 = min(x1 + w1 / 2, x2 + w2 / 2)
    yi2 = min(y1 + h1 / 2, y2 + h2 / 2)

    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area

    return inter_area / union_area

def image_pred(self, keiyao, confidence_threshold, iou_threshold):
    if keiyao == 2:
        self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
    
    if confidence_threshold is not None:
        self.model.conf = confidence_threshold
    
    self.img = np.clip(self.img, 0, 255).astype(np.uint8)
    
    if keiyao == 0:
        # 调整原始图片大小以适应显示区域
        display_width = self.output.width()
        display_height = self.output.height()
        self.img = cv2.resize(self.img, (display_width, display_height), interpolation=cv2.INTER_AREA)
    
    results = self.model(self.img)
    
    image_frame = results[0].boxes.xywh.cpu().numpy()
    classes = results[0].boxes.cls.cpu().numpy()
    class_names = results[0].names
    confidences = results[0].boxes.conf.cpu().numpy()
    
    if image_frame is not None and image_frame.shape[0] > 0:
        to_delete = []
        for i in range(image_frame.shape[0]):
            for j in range(i + 1, image_frame.shape[0]):
                iou = calculate_iou(image_frame[i], image_frame[j])
                if iou_threshold is not None and iou > iou_threshold:
                    if confidences[i] > confidences[j]:
                        to_delete.append(j)
                    else:
                        to_delete.append(i)

        to_delete = list(set(to_delete))
        image_frame = np.delete(image_frame, to_delete, axis=0)
        classes = np.delete(classes, to_delete, axis=0)
        confidences = np.delete(confidences, to_delete, axis=0)

        for i in range(image_frame.shape[0]):
            confidence = confidences[i]
            if confidence < confidence_threshold:
                continue
            
            x, y, w, h = image_frame[i]
            class_id = int(classes[i])
            label = class_names[class_id]
            label_with_confidence = f"{label} {confidence:.2f}"
            color = CLASS_COLORS.get(label, (255, 255, 255))
            
            # 尝试缩小检测框的大小以降低IOU值
            while True:
                iou_exceeded = False
                for j in range(image_frame.shape[0]):
                    if i != j:
                        iou = calculate_iou(image_frame[i], image_frame[j])
                        if iou > iou_threshold:
                            iou_exceeded = True
                            w *= 0.9
                            h *= 0.9
                            image_frame[i] = [x, y, w, h]
                            break
                if not iou_exceeded:
                    break
            
            cv2.rectangle(self.img, 
                          (int(x - w / 2), int(y - h / 2)), 
                          (int(x + w / 2), int(y + h / 2)), 
                          color, 1)
            cv2.putText(self.img, label_with_confidence, 
                        (int(x - w / 2), int(y - h / 2) - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    img_rgb = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
    h, w, ch = img_rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg)
    
    # if keiyao == 1:
    #     # 调整图片大小以适应显示区域
    #     pixmap = pixmap.scaled(display_width, display_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    self.output.setPixmap(pixmap)
    self.output.setAlignment(Qt.AlignCenter)
