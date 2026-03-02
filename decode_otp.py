"""
一站式 OTP 密钥提取工具

用法:
  python3 decode_otp.py <二维码图片路径>
  python3 decode_otp.py --uri "otpauth-migration://offline?data=..."

支持:
  1. 直接传入二维码图片 → 自动识别并解码
  2. 传入 otpauth-migration:// URI → 解码 Google Authenticator 批量导出
  3. 传入 otpauth://totp/ URI → 直接提取密钥

纯离线运行，不发送任何网络请求。
"""
import base64
import sys
import os
import subprocess
from urllib.parse import urlparse, parse_qs


# ─────────────── 二维码识别 ───────────────

def read_qr_opencv(image_path):
    """使用 OpenCV 识别二维码"""
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return None
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            return data

        # 尝试多个二维码
        retval, decoded_info, _, _ = detector.detectAndDecodeMulti(img)
        if retval and decoded_info:
            for info in decoded_info:
                if info:
                    return info
    except Exception as e:
        print(f"  OpenCV 识别失败: {e}")
    return None


def read_qr_zbarimg(image_path):
    """使用 zbarimg 命令行工具识别二维码"""
    try:
        result = subprocess.run(
            ['zbarimg', '--raw', '-q', image_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  zbarimg 识别失败: {e}")
    return None


def read_qr_from_image(image_path):
    """依次尝试多种方式识别二维码"""
    if not os.path.exists(image_path):
        print(f"错误: 文件不存在 - {image_path}")
        return None

    print(f"正在识别二维码: {image_path}")

    # 方式1: OpenCV
    print("  尝试 OpenCV QRCodeDetector...")
    data = read_qr_opencv(image_path)
    if data:
        print("  ✓ OpenCV 识别成功")
        return data

    # 方式2: zbarimg
    print("  尝试 zbarimg...")
    data = read_qr_zbarimg(image_path)
    if data:
        print("  ✓ zbarimg 识别成功")
        return data

    print("  ✗ 所有识别方式均失败")
    return None


# ─────────────── Protobuf 解码 ───────────────

def decode_varint(data, pos):
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def parse_protobuf_fields(data):
    fields = {}
    pos = 0
    while pos < len(data):
        if pos >= len(data):
            break
        tag, pos = decode_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 0:  # varint
            value, pos = decode_varint(data, pos)
        elif wire_type == 2:  # length-delimited
            length, pos = decode_varint(data, pos)
            value = data[pos:pos + length]
            pos += length
        else:
            break

        fields[field_num] = value
    return fields


def parse_migration_payload(data):
    entries = []
    pos = 0
    while pos < len(data):
        tag, pos = decode_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:
            length, pos = decode_varint(data, pos)
            entry_data = data[pos:pos + length]
            pos += length
            if field_num == 1:
                fields = parse_protobuf_fields(entry_data)
                secret_bytes = fields.get(1, b'')
                name = fields.get(2, b'').decode('utf-8', errors='replace') if isinstance(fields.get(2, b''), bytes) else ''
                issuer = fields.get(3, b'').decode('utf-8', errors='replace') if isinstance(fields.get(3, b''), bytes) else ''
                otp_type = fields.get(6, 0)
                secret_b32 = base64.b32encode(secret_bytes).decode().rstrip('=')
                type_name = {0: 'unspecified', 1: 'hotp', 2: 'totp'}.get(otp_type, f'unknown({otp_type})')
                entries.append({
                    'name': name,
                    'secret': secret_b32,
                    'issuer': issuer,
                    'type': type_name,
                })
        elif wire_type == 0:
            _, pos = decode_varint(data, pos)
        else:
            break
    return entries


# ─────────────── URI 解析 ───────────────

def decode_otpauth_totp(uri):
    """解析标准 otpauth://totp/ URI"""
    parsed = urlparse(uri)
    params = parse_qs(parsed.query)
    secret = params.get('secret', [''])[0]
    issuer = params.get('issuer', [''])[0]
    # label 在 path 中, 格式: /issuer:account 或 /account
    label = parsed.path.lstrip('/')

    return [{
        'name': label,
        'secret': secret,
        'issuer': issuer,
        'type': parsed.netloc,  # totp 或 hotp
    }]


def decode_otpauth_migration(uri):
    """解析 otpauth-migration:// URI"""
    parsed = urlparse(uri)
    params = parse_qs(parsed.query)
    data_b64 = params.get('data', [''])[0]

    if not data_b64:
        print("错误: URI 中没有 data 参数")
        return []

    raw = base64.b64decode(data_b64)
    return parse_migration_payload(raw)


def decode_uri(uri):
    """自动识别 URI 类型并解码"""
    uri = uri.strip()
    if uri.startswith('otpauth-migration://'):
        return decode_otpauth_migration(uri)
    elif uri.startswith('otpauth://'):
        return decode_otpauth_totp(uri)
    else:
        print(f"错误: 不支持的 URI 格式")
        print(f"  支持: otpauth://totp/... 或 otpauth-migration://offline?data=...")
        return []


# ─────────────── 输出结果 ───────────────

def print_entries(entries):
    if not entries:
        print("\n未找到任何 OTP 条目")
        return

    print(f"\n{'='*50}")
    print(f" 共找到 {len(entries)} 个 OTP 条目")
    print(f"{'='*50}\n")

    for i, entry in enumerate(entries, 1):
        print(f"  [{i}] {entry['issuer'] or '(无issuer)'} - {entry['name']}")
        print(f"      Type:   {entry['type']}")
        print(f"      Secret: {entry['secret']}")
        print()

    if len(entries) == 1:
        print(f"  → 可直接使用的 TOTP 密钥: {entries[0]['secret']}")
    else:
        print(f"  → 请找到 Bybit 对应条目，其 Secret 即为 BYBIT_TOTP_SECRET")


# ─────────────── 主入口 ───────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("示例:")
        print('  python3 decode_otp.py qrcode.png')
        print('  python3 decode_otp.py --uri "otpauth-migration://offline?data=..."')
        sys.exit(1)

    if sys.argv[1] == '--uri':
        if len(sys.argv) < 3:
            print("错误: --uri 后需要提供 URI")
            sys.exit(1)
        entries = decode_uri(sys.argv[2])
    else:
        image_path = sys.argv[1]
        qr_data = read_qr_from_image(image_path)
        if not qr_data:
            print("\n无法从图片中识别二维码，请确认:")
            print("  1. 图片路径正确")
            print("  2. 图片中包含有效的二维码")
            print("  3. 图片清晰度足够")
            sys.exit(1)

        print(f"\n识别到的二维码内容:\n  {qr_data[:80]}{'...' if len(qr_data) > 80 else ''}")
        entries = decode_uri(qr_data)

    print_entries(entries)


if __name__ == '__main__':
    main()
