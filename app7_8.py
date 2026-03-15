# app7_8.py
from flask import Flask, request, render_template, send_from_directory, jsonify
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import base64
import re
import threading
import time
import uuid
import json
import csv
from werkzeug.utils import secure_filename as werkzeug_secure_filename
from PIL import Image
from PIL.ExifTags import TAGS
import io

# 初始化Tkinter
root = tk.Tk()
root.withdraw()

# 弹出文件夹选择对话框
UPLOAD_FOLDER = filedialog.askdirectory(title="选择图片保存路径")

if not UPLOAD_FOLDER:
    UPLOAD_FOLDER = 'uploads'
    print("未选择路径，默认保存到uploads目录下")

app = Flask(__name__)

# 增加最大文件大小限制到100MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

# 定义端口号
server_port = '80'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 文件名映射记录文件
FILENAME_MAPPING_FILE = os.path.join(UPLOAD_FOLDER, 'filename_mapping.json')
FILENAME_LOG_FILE = os.path.join(UPLOAD_FOLDER, 'upload_log.csv')

@app.route('/')
def index():
    return render_template('index7_8.html')

@app.route('/test')
def test():
    """文件名测试页面"""
    return render_template('test_filename.html')

@app.route('/test-file-time')
def test_file_time():
    """文件时间测试页面"""
    return render_template('test_file_time.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def clean_filename(filename):
    """
    清理文件名，保留原始名称特征，只移除必要的非法字符
    尽可能保持手机端原始文件名不变
    """
    if not filename:
        return None

    # 如果文件名过长，截断（保留扩展名）
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        # 限制名称部分长度，为扩展名和可能的序号预留空间
        max_name_length = 240
        filename = name[:max_name_length] + ext

    # 只替换Windows/Linux中绝对必要的非法字符
    # 使用更保守的替换策略，保留更多原始字符
    illegal_chars = {
        '<': '_', '>': '_', ':': '_', '"': '_', '/': '_',
        '\\': '_', '|': '_', '?': '_', '*': '_'
    }

    for char, replacement in illegal_chars.items():
        filename = filename.replace(char, replacement)

    # 移除控制字符（不可见字符）
    filename = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', filename)

    # 去除首尾空格（但保留点，因为以点开头的文件名在某些系统中有特殊含义）
    filename = filename.strip(' ')

    # 如果文件名为空，返回None
    if not filename:
        return None

    return filename

def load_filename_mapping():
    """加载文件名映射记录"""
    if os.path.exists(FILENAME_MAPPING_FILE):
        try:
            with open(FILENAME_MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载映射文件失败: {e}")
            return {}
    return {}

def save_filename_mapping(mapping):
    """保存文件名映射记录"""
    try:
        with open(FILENAME_MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存映射文件失败: {e}")

def log_upload(original_filename, saved_filename, file_size, upload_time):
    """记录上传日志到CSV文件"""
    file_exists = os.path.exists(FILENAME_LOG_FILE)

    try:
        with open(FILENAME_LOG_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 如果文件不存在，写入表头
            if not file_exists:
                writer.writerow(['上传时间', '原始文件名', '保存文件名', '文件大小(字节)', '文件大小(MB)'])

            # 写入记录
            file_size_mb = round(file_size / (1024 * 1024), 2)
            writer.writerow([upload_time, original_filename, saved_filename, file_size, file_size_mb])
    except Exception as e:
        print(f"记录上传日志失败: {e}")

def get_exif_datetime(file_data):
    """
    从图片EXIF数据中提取拍摄时间
    返回格式: YYYYMMDD_HHMMSS
    如果无法获取，返回None
    """
    try:
        # 从文件数据创建Image对象
        image = Image.open(io.BytesIO(file_data))

        # 获取EXIF数据
        exif_data = image._getexif()
        if not exif_data:
            return None

        # 查找DateTimeOriginal标签（拍摄时间）
        datetime_original = None
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'DateTimeOriginal':
                datetime_original = value
                break

        if not datetime_original:
            # 如果没有DateTimeOriginal，尝试使用DateTime
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTime':
                    datetime_original = value
                    break

        if not datetime_original:
            return None

        # EXIF时间格式通常是 "YYYY:MM:DD HH:MM:SS"
        # 转换为 "YYYYMMDD_HHMMSS"
        try:
            # 尝试解析EXIF时间格式
            dt = datetime.strptime(datetime_original, '%Y:%m:%d %H:%M:%S')
            return dt.strftime('%Y%m%d_%H%M%S')
        except:
            return None

    except Exception as e:
        print(f"读取EXIF数据失败: {e}")
        return None

def generate_camera_like_filename(file_data, original_filename=None, file_timestamp=None, exif_filename=None):
    """
    生成类似相机的文件名
    格式: IMG_YYYYMMDDHHMMSS.jpg (所有数字连续，无下划线)

    时间优先级：
    1. 前端传递的EXIF文件名（最准确，避免压缩后丢失EXIF）
    2. 后端从EXIF获取拍摄时间
    3. 前端传递的文件时间戳（file.lastModified）
    4. 服务器当前时间（最后备选）

    Args:
        file_data: 文件二进制数据
        original_filename: 原始文件名
        file_timestamp: 前端传递的文件修改时间戳（毫秒）
        exif_filename: 前端提取的EXIF文件名（如 IMG_20250312143322.jpg）
    """
    # 优先使用前端传递的EXIF文件名（压缩后的图片无法在后端提取EXIF）
    if exif_filename:
        print(f"  📸 使用前端传递的EXIF文件名: {exif_filename}")
        return exif_filename

    # 尝试从EXIF获取拍摄时间
    exif_time = get_exif_datetime(file_data)

    if exif_time:
        # exif_time 已经是 YYYYMMDD_HHMMSS 格式，去掉下划线
        base_name = exif_time.replace('_', '')
        print(f"  ✅ 使用后端EXIF时间生成文件名")
    elif file_timestamp:
        # 使用前端传递的文件时间戳
        try:
            # 将毫秒时间戳转换为秒
            file_time = datetime.fromtimestamp(file_timestamp / 1000)
            base_name = file_time.strftime('%Y%m%d%H%M%S')
            print(f"  ⏰ 使用文件时间戳: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"  ⚠️ 文件时间戳转换失败: {e}，使用服务器时间")
            base_name = datetime.now().strftime('%Y%m%d%H%M%S')
    else:
        # 使用服务器当前时间，格式：YYYYMMDDHHMMSS
        base_name = datetime.now().strftime('%Y%m%d%H%M%S')
        print(f"  🕐 使用服务器当前时间")

    # 获取原始文件的扩展名
    if original_filename:
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.jpg'
    else:
        ext = '.jpg'

    return f"IMG_{base_name}{ext}"

def get_unique_filename(folder, filename):
    """生成唯一的文件名，如果文件已存在则添加序号"""
    if not filename:
        # 如果没有文件名，生成一个基于时间的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"photo_{timestamp}.jpg"
    
    # 分离文件名和扩展名
    name, ext = os.path.splitext(filename)
    if not ext:
        ext = '.jpg'  # 默认扩展名
    
    counter = 1
    unique_filename = filename
    
    while os.path.exists(os.path.join(folder, unique_filename)):
        unique_filename = f"{name}_{counter}{ext}"
        counter += 1
        
    return unique_filename

def save_file(file_data, filename):
    """同步保存文件"""
    try:
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(save_path, 'wb') as f:
            f.write(file_data)
        print(f"文件保存成功: {filename}")
        return True
    except Exception as e:
        print(f"文件保存失败 {filename}: {str(e)}")
        return False

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'success': False, 'message': '文件太大，请选择小于100MB的图片'}), 413

@app.route('/upload', methods=['POST'])
def upload_file():
    # 打印完整的请求信息用于调试
    print("\n" + "="*50)
    print(f"收到上传请求: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"请求方法: {request.method}")
    print(f"内容类型: {request.content_type}")
    print(f"请求头: {dict(request.headers)}")
    
    # 打印所有表单字段
    print("\n表单字段:")
    for key, value in request.form.items():
        print(f"  {key}: {value[:100] if value else 'None'}")
    
    # 打印所有文件
    print("\n上传的文件:")
    for key, file in request.files.items():
        print(f"  {key}: filename='{file.filename}', content_type='{file.content_type}'")
    
    print("="*50 + "\n")

    # 处理所有可能的文件字段
    file_to_save = None
    original_filename = None
    file_data = None

    # 检查是否有显式的 original_filename 参数
    explicit_original_filename = request.form.get('original_filename', '').strip()
    print(f"📝 收到的 original_filename 参数: '{explicit_original_filename}'")

    # 检查是否有文件时间戳参数（前端传递的 lastModified）
    file_timestamp_str = request.form.get('file_timestamp', '').strip()
    file_timestamp = None
    if file_timestamp_str:
        try:
            file_timestamp = int(file_timestamp_str)
            print(f"⏰ 收到文件时间戳: {file_timestamp} ({datetime.fromtimestamp(file_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')})")
        except ValueError:
            print(f"⚠️ 文件时间戳格式无效: '{file_timestamp_str}'")

    # 检查是否有前端传递的EXIF文件名（压缩后图片需要）
    exif_filename = request.form.get('exif_filename', '').strip()
    if exif_filename:
        print(f"📸 收到前端EXIF文件名: '{exif_filename}'")

    # 情况1: 处理 'image' 字段 (移动设备拍照)
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            file_to_save = file
            # 优先使用前端传递的原始文件名
            original_filename = explicit_original_filename if explicit_original_filename else file.filename
            print(f"📸 找到文件字段 'image': {original_filename}")
            print(f"   - file.filename: '{file.filename}'")
            print(f"   - 使用文件名: '{original_filename}'")
    
    # 情况2: 处理 'file' 字段
    elif 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            file_to_save = file
            # 优先使用前端传递的原始文件名
            original_filename = explicit_original_filename if explicit_original_filename else file.filename
            print(f"找到文件字段 'file': {original_filename}")
    
    # 情况3: 处理 'files[]' 字段 (多文件)
    elif 'files[]' in request.files:
        files = request.files.getlist('files[]')
        if files:
            # 这里简化处理，只保存第一个文件
            file_to_save = files[0]
            # 优先使用前端传递的原始文件名
            original_filename = explicit_original_filename if explicit_original_filename else file_to_save.filename
            print(f"找到多文件字段 'files[]': {original_filename}")
    
    # 如果找到了文件
    if file_to_save and original_filename:
        try:
            # 读取文件数据
            file_data = file_to_save.read()
            file_size = len(file_data)
            print(f"文件大小: {file_size} 字节")

            # 检查文件大小
            if file_size > 100 * 1024 * 1024:
                return jsonify({'success': False, 'message': '文件太大，请选择小于100MB的图片'}), 413

            # 检查是否是浏览器默认的通用文件名
            browser_default_names = ['image', 'img', 'photo', 'picture', 'pic']
            file_base_name = os.path.splitext(original_filename)[0].lower()
            is_browser_default = any(file_base_name == name for name in browser_default_names)
            filename_changed = False

            # 检查是否已经是EXIF格式的文件名（IMG_开头 + 14位数字）
            is_already_exif_format = bool(
                file_base_name.startswith('IMG_') and
                len(file_base_name) == 18 and  # IMG_ + 14位数字
                file_base_name[4:].isdigit()
            )

            # 统一策略：所有文件都使用EXIF时间生成文件名
            # 除非文件已经是IMG_YYYYMMDDHHMMSS格式
            if is_already_exif_format:
                print(f"✓ 文件名已是EXIF格式: '{original_filename}'")
                print(f"📝 保留此文件名")
            else:
                print(f"📷 尝试从EXIF生成文件名，原始文件名: '{original_filename}'")
                camera_filename = generate_camera_like_filename(file_data, original_filename, file_timestamp, exif_filename)
                if camera_filename != original_filename:
                    print(f"📷 从EXIF生成文件名: '{camera_filename}'")
                    original_filename = camera_filename
                    filename_changed = True
                else:
                    print(f"📝 无法生成新文件名，使用原始文件名")

            # 清理文件名
            cleaned_filename = clean_filename(original_filename)
            print(f"🧹 清理后的文件名: {cleaned_filename}")
            print(f"   - 原始: '{original_filename}'")
            print(f"   - 清理后: '{cleaned_filename}'")
            
            # 如果没有有效的文件名，生成一个
            if not cleaned_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                ext = os.path.splitext(original_filename)[1] or '.jpg'
                cleaned_filename = f"photo_{timestamp}{ext}"
                print(f"生成文件名: {cleaned_filename}")
            
            # 确保文件名唯一
            final_filename = get_unique_filename(UPLOAD_FOLDER, cleaned_filename)
            print(f"最终文件名: {final_filename}")
            
            # 保存文件
            if save_file(file_data, final_filename):
                # 记录文件名映射
                upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_upload(original_filename, final_filename, file_size, upload_time)

                # 更新JSON映射文件
                mapping = load_filename_mapping()
                mapping[final_filename] = {
                    'original_filename': original_filename,
                    'upload_time': upload_time,
                    'file_size': file_size
                }
                save_filename_mapping(mapping)

                print(f"✓ 文件保存成功!")
                print(f"   - 原始文件名: {original_filename}")
                print(f"   - 清理后文件名: {cleaned_filename}")
                print(f"   - 最终保存文件名: {final_filename}")
                print(f"   - 文件大小: {file_size} 字节 ({round(file_size/1024/1024, 2)} MB)")

                return jsonify({
                    'success': True,
                    'message': '文件上传成功',
                    'files': [final_filename],
                    'original_filename': original_filename,
                    'saved_as': final_filename,
                    'file_size': file_size,
                    'filename_from_exif': filename_changed
                })
            else:
                return jsonify({'success': False, 'message': '文件保存失败'}), 500
                
        except Exception as e:
            print(f"处理文件时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'处理文件失败: {str(e)}'}), 500
    
    # 情况4: 处理 Base64 数据
    elif 'captured_image_data' in request.form:
        captured_image = request.form.get('captured_image_data')
        # 优先使用 original_filename 字段，其次使用 filename 字段
        original_filename = request.form.get('original_filename', '') or request.form.get('filename', '')
        
        if captured_image:
            try:
                print(f"处理Base64数据, 原始文件名: {original_filename}")
                
                # 解码Base64
                if ',' in captured_image:
                    header, encoded = captured_image.split(',', 1)
                else:
                    encoded = captured_image
                
                image_data = base64.b64decode(encoded)
                file_size = len(image_data)
                print(f"解码后大小: {file_size} 字节")
                
                if file_size > 100 * 1024 * 1024:
                    return jsonify({'success': False, 'message': '图片太大，请重新拍摄'}), 413
                
                # 确定文件名
                if original_filename:
                    cleaned_filename = clean_filename(original_filename)
                    if not cleaned_filename:
                        cleaned_filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                else:
                    cleaned_filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                
                # 确保有扩展名
                if not os.path.splitext(cleaned_filename)[1]:
                    cleaned_filename += '.jpg'
                
                # 确保文件名唯一
                final_filename = get_unique_filename(UPLOAD_FOLDER, cleaned_filename)
                
                # 保存文件
                if save_file(image_data, final_filename):
                    # 记录文件名映射
                    upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    original_fname = original_filename or '未知'
                    log_upload(original_fname, final_filename, file_size, upload_time)

                    # 更新JSON映射文件
                    mapping = load_filename_mapping()
                    mapping[final_filename] = {
                        'original_filename': original_fname,
                        'upload_time': upload_time,
                        'file_size': file_size
                    }
                    save_filename_mapping(mapping)

                    print(f"✓ 文件保存成功: {original_fname} -> {final_filename}")
                    print(f"  文件大小: {file_size} 字节 ({round(file_size/1024/1024, 2)} MB)")

                    return jsonify({
                        'success': True,
                        'message': '图片上传成功',
                        'files': [final_filename],
                        'original_filename': original_fname,
                        'saved_as': final_filename,
                        'file_size': file_size
                    })
                else:
                    return jsonify({'success': False, 'message': '文件保存失败'}), 500
                    
            except Exception as e:
                print(f"处理Base64图片失败: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f'处理图片失败: {str(e)}'}), 500
    
    # 没有找到文件
    print("错误: 没有找到有效的文件数据")
    return jsonify({
        'success': False, 
        'message': '没有接收到有效的文件数据',
        'debug': {
            'form_keys': list(request.form.keys()),
            'file_keys': list(request.files.keys()),
            'content_type': request.content_type
        }
    }), 400

@app.route('/mapping')
def view_mapping():
    """查看文件名映射记录（JSON格式）"""
    mapping = load_filename_mapping()
    return jsonify(mapping)

@app.route('/log')
def view_log():
    """查看上传日志（HTML表格格式）"""
    log_data = []
    if os.path.exists(FILENAME_LOG_FILE):
        try:
            with open(FILENAME_LOG_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                log_data = list(reader)
        except Exception as e:
            return f"读取日志文件失败: {e}"

    # 生成HTML表格
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>上传日志</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            tr:hover { background-color: #ddd; }
            h1 { color: #333; }
            .back-link { margin-bottom: 20px; }
            .back-link a { color: #4CAF50; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="back-link">
            <a href="/">← 返回上传页面</a>
        </div>
        <h1>文件上传日志</h1>
    """

    if log_data:
        html += "<table>"
        for i, row in enumerate(log_data):
            if i == 0:
                html += "<tr>"
                for cell in row:
                    html += f"<th>{cell}</th>"
                html += "</tr>"
            else:
                html += "<tr>"
                for cell in row:
                    html += f"<td>{cell}</td>"
                html += "</tr>"
        html += "</table>"
    else:
        html += "<p>暂无上传记录</p>"

    html += """
    </body>
    </html>
    """

    return html

if __name__ == '__main__':
    print(f'\n{"="*60}')
    print(f'  图片上传服务器 - 前端EXIF提取版本')
    print(f'{"="*60}')
    print(f'  📁 图片保存路径: {UPLOAD_FOLDER}')
    print(f'  🌐 服务器端口: {server_port}')
    print(f'  🔗 访问地址: http://localhost:{server_port}')
    print(f'\n  🚀 突破浏览器限制:')
    print(f'     • ✅ 前端JavaScript提取EXIF数据')
    print(f'     • ✅ 绕过浏览器文件名限制')
    print(f'     • ✅ 所有上传都使用EXIF时间生成文件名')
    print(f'     • ✅ 文件名格式: IMG_2025031214330.jpg')
    print(f'\n  📋 页面访问:')
    print(f'     • 主页: http://localhost:{server_port}/')
    print(f'     • 文件名测试页: http://localhost:{server_port}/test')
    print(f'     • 文件时间测试页: http://localhost:{server_port}/test-file-time')
    print(f'     • 映射记录: http://localhost:{server_port}/mapping')
    print(f'     • 上传日志: http://localhost:{server_port}/log')
    print(f'\n  📝 技术细节:')
    print(f'     • 前端EXIF库: exif-js (CDN)')
    print(f'     • 后端EXIF库: Pillow')
    print(f'     • 双重保障: 前端提取 + 后端验证')
    print(f'     • 重名文件自动添加序号')
    print(f'{"="*60}\n')

    # 使用debug=False，避免自动重载干扰调试
    app.run(debug=False, host='0.0.0.0', port=server_port)