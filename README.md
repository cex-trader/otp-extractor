# otp-extractor

[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Offline](https://img.shields.io/badge/Network-Offline%20Only-brightgreen.svg)](#安全说明)

Offline CLI tool to extract OTP secrets from QR code images or URIs.

从二维码图片或 URI 中离线提取 OTP 密钥的命令行工具，支持标准 otpauth 和 Google Authenticator 导出格式。

**纯离线运行，不发送任何网络请求，适合处理 TOTP 密钥等敏感信息。**

## Features / 功能

- 传入二维码图片，自动识别并提取 TOTP/HOTP 密钥
- 传入 URI 字符串，直接解码输出密钥
- 支持 `otpauth://totp/...` 标准格式
- 支持 `otpauth-migration://offline?data=...` Google Authenticator 批量导出格式
- 多引擎识别（OpenCV + zbarimg），互为兜底，提高成功率
- 零外部服务依赖，所有计算在本地完成

## Install / 安装

### 1. 确认 Python 版本

```bash
python3 --version   # 需要 3.6+
```

### 2. 安装依赖

**必装**（二维码识别）：

```bash
pip3 install opencv-python Pillow
```

**可选**（识别兜底，提高成功率）：

```bash
# macOS
brew install zbar

# Ubuntu/Debian
sudo apt-get install zbar-tools

# CentOS/RHEL
sudo yum install zbar
```

> 脚本优先用 OpenCV 识别，失败时自动尝试 zbarimg。两个都装效果最好。

### 3. 获取脚本

```bash
git clone https://github.com/cex-trader/otp-extractor.git
cd otp-extractor
```

也可以直接下载 `decode_otp.py` 单文件使用，无需额外构建。

## Usage / 使用

### 从二维码图片提取（最常用）

```bash
python3 decode_otp.py /path/to/qrcode.png
```

支持 PNG、JPG、BMP、WEBP 等常见图片格式。

### 从 URI 字符串提取

```bash
# Google Authenticator 导出格式
python3 decode_otp.py --uri "otpauth-migration://offline?data=AnfuhgeuHgf..."

# 标准 TOTP 格式
python3 decode_otp.py --uri "otpauth://totp/Example:user@example.com?secret=AnfuhgeuHgf&issuer=Example"
```

## Output / 输出示例

```
正在识别二维码: auth_qr.png
  尝试 OpenCV QRCodeDetector...
  ✓ OpenCV 识别成功

识别到的二维码内容:
  otpauth-migration://offline?data=AnfuhgeuHgf...

==================================================
 共找到 2 个 OTP 条目
==================================================

  [1] GitHub - GitHub:octocat
      Type:   totp
      Secret: XXXXXXXXXXXXXXXXXX

  [2] AWS - AWS:admin@example.com
      Type:   totp
      Secret: XXXXXXXXXXXXXXXXXX

  → 请找到对应条目，其 Secret 即为 TOTP 密钥
```

## Supported Formats / 支持的格式

| 格式 | 来源 | 说明 |
|------|------|------|
| `otpauth://totp/...` | 各平台绑定 2FA 时的二维码 | 直接提取 `secret` 参数 |
| `otpauth://hotp/...` | 基于计数器的 OTP | 同上 |
| `otpauth-migration://offline?data=...` | Google Authenticator → 导出账号 | 解码 Protobuf 提取所有条目 |

## Security / 安全说明

- **零网络请求**：纯 Python 标准库 + OpenCV 本地图像处理，不连接任何外部服务
- **本地计算**：所有解码在本机 CPU 完成，密钥不会离开本地
- **可审计**：核心逻辑不到 200 行，源码完全公开透明
- **建议**：使用完毕后删除本地的二维码图片文件，避免密钥泄露

## FAQ / 常见问题

### 二维码识别失败

1. 确认图片清晰，二维码没有被裁剪
2. 尝试将图片放大或提高对比度后重试
3. 确保 zbar 已安装作为兜底方案
4. 如果是截图，尝试保存原始二维码图片而非截屏

### 提取到的 Secret 怎么用？

提取到的 Secret 是 Base32 编码字符串，可以：

- 导入到任意 Authenticator App（Google Authenticator、Authy、1Password 等）
- 用 `pyotp` 生成一次性验证码：

```python
import pyotp
totp = pyotp.TOTP("YOUR_SECRET")
print(totp.now())  # 输出当前 6 位验证码
```

- 作为环境变量配置到自动化系统中

## Contributing / 贡献

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交更改：`git commit -m "Add my feature"`
4. 推送到分支：`git push origin feature/my-feature`
5. 发起 Pull Request

## License

[MIT License](LICENSE) - 可自由使用、修改和分发。
