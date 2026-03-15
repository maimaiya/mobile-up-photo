# app5.py
from flask import Flask, request, render_template, send_from_directory
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import base64
import re

# 初始化Tkinter
root = tk.Tk()
root.withdraw()

# 弹出文件夹选择对话框
UPLOAD_FOLDER = filedialog.askdirectory(title="选择图片保存路径")

if not UPLOAD_FOLDER:
    UPLOAD_FOLDER = 'uploads'
    print("未选择路径，默认保存到uploads目录下")

app = Flask(__name__)

# 定义端口号
server_port = '80'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index6.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def secure_filename(filename):
    """确保文件名安全"""
    # 移除不安全的字符
    filename = re.sub(r'[^\w\-_\.]', '', filename)
    # 确保文件名不为空
    if not filename:
        filename = 'unnamed'
    return filename

def get_unique_filename(folder, filename):
    """生成唯一的文件名，如果文件已存在则添加序号"""
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    
    while os.path.exists(os.path.join(folder, unique_filename)):
        unique_filename = f"{name}_{counter}{ext}"
        counter += 1
        
    return unique_filename

@app.route('/upload', methods=['POST'])
def upload_file():
    # 支持单文件字段 'file' 和多文件字段 'files[]'
    saved_files = []

    # 处理 base64 图片数据 (从新表单字段)
    captured_image = request.form.get('captured_image_data')
    if captured_image:
        try:
            # 解码base64数据
            if ',' in captured_image:
                header, encoded = captured_image.split(',', 1)
            else:
                encoded = captured_image
                
            image_data = base64.b64decode(encoded)
            
            # 创建文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            safe_name = f"{timestamp}.jpg"
            save_path = os.path.join(UPLOAD_FOLDER, safe_name)
            
            # 保存图片
            with open(save_path, 'wb') as f:
                f.write(image_data)
            saved_files.append(safe_name)
            
            return {'success': True, 'files': saved_files}
        except Exception as e:
            return {'success': False, 'message': f'Failed to save captured image: {str(e)}'}, 500

    # 处理通过<input type="file" capture="environment">拍摄的照片
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename != '':
            # 使用原始文件名并确保安全性
            original_filename = secure_filename(file.filename)
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = '.jpg'
                original_filename += ext
                
            # 确保文件名唯一
            safe_name = get_unique_filename(UPLOAD_FOLDER, original_filename)
            save_path = os.path.join(UPLOAD_FOLDER, safe_name)
            try:
                file.save(save_path)
                saved_files.append(safe_name)
                return {'success': True, 'files': saved_files}
            except Exception as e:
                return {'success': False, 'message': f'Failed to save file: {str(e)}'}, 500

    # 处理多文件字段
    if 'files[]' in request.files:
        files = request.files.getlist('files[]')
        for file in files:
            if not file or file.filename == '':
                continue

            # 使用原始文件名并确保安全性
            original_filename = secure_filename(file.filename)
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = '.jpg'
                original_filename += ext

            # 确保文件名唯一
            safe_name = get_unique_filename(UPLOAD_FOLDER, original_filename)
            save_path = os.path.join(UPLOAD_FOLDER, safe_name)
            try:
                file.save(save_path)
                saved_files.append(safe_name)
            except Exception as e:
                return {'success': False, 'message': f'Failed to save file: {str(e)}'}, 500

        return {'success': True, 'files': saved_files}

    return {'success': False, 'message': 'No file part'}, 400

if __name__ == '__main__':
    print(f'图片保存路径是：{UPLOAD_FOLDER}')
    app.run(debug=False, host='0.0.0.0', port=server_port)