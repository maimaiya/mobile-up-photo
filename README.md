# mobile-up-photo
通过AI写的局域网上传图片的py，每次运行后选取一个目录作为图片存储路径，不选默认在py目录下uploads目录，曾经功能好用，ssd意外掉盘后丢失，重制版不如原来，但是得备份起来了。  </br>
现用库：</br>
Flask        3.1.2</br>
pillow       12.0.0</br>
Werkzeug     3.1.4</br>
已实现功能：</br>
1、通过JavaScript读取exif或修改时间，作为上传后的命名基础，如果无法读取或信息不存在使用上传时间；</br>
2、图片压缩，使用pillow库</br>
完全通过AI编辑</br>
