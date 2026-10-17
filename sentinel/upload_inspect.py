"""上传文件识别：判断用户传上来的到底是"聊天记录文本"还是"QQ 加密备份"。

背景（为什么需要这个模块）：
    QQ（NT 版）导出的 `.bak` 是**加密备份**，里面是 SQLCipher 加密的 SQLite，
    密钥登录时由腾讯服务器下发，**任何网站都无法离线解密**。
    所以网站不可能"帮用户解开 .bak"，能做的是：**立刻识别出来并给出正确引导**，
    而不是把二进制当文本读成一堆乱码。

本模块只读文件头 / 尝试解码文本，**不解密、不联网、不落盘**。
"""

import io
import zipfile

# 文本尝试解码的顺序：UTF-8（含 BOM）优先，再退回 GB18030（覆盖 GBK/GB2312）
_TEXT_ENCODINGS = ("utf-8-sig", "gb18030", "utf-16")

_QQ_DB_MAGIC = b"SQLite header 3"   # QQNT 伪装头（正版 SQLite 是 "SQLite format 3\0"）
_SQLITE_MAGIC = b"SQLite format 3\x00"
_MSG0_MAGIC = b"MSG0"               # .bak 里数据库头的魔数（偏移 32）


def looks_like_qq_backup(data: bytes) -> bool:
    """判断是否为 QQ 加密备份（ZIP 包，内含 db/ 条目）。"""
    if not data[:4] == b"PK\x03\x04":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
    except Exception:
        return False
    return any(n.startswith("db/") or n.startswith("files/") for n in names)


def looks_like_encrypted_db(data: bytes) -> bool:
    """判断是否为 QQNT 加密数据库（伪装头 / MSG0 魔数）。"""
    head = data[:64]
    if head.startswith(_QQ_DB_MAGIC):
        return True
    if len(data) > 40 and data[32:36] == _MSG0_MAGIC:
        return True
    return False


def looks_like_zip(data: bytes) -> bool:
    return data[:4] == b"PK\x03\x04"


def decode_text(data: bytes):
    """尝试把字节按常见中文编码解成文本。

    返回 (text, encoding) 或 (None, None)。
    判定原则：能解码 + 基本没有 NUL + 控制字符占比很低，才算"文本"。
    """
    if not data:
        return None, None
    # 二进制特征：NUL 字节过多，基本可以断定不是文本
    if data.count(b"\x00") > max(2, len(data) // 100):
        return None, None

    for enc in _TEXT_ENCODINGS:
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        # 控制字符（除 \t \n \r）占比过高 -> 判为二进制
        bad = sum(1 for ch in text if ord(ch) < 32 and ch not in "\t\n\r")
        if bad <= max(2, len(text) // 200):
            return text, enc
    return None, None


def inspect_upload(data: bytes, filename: str = "") -> dict:
    """识别上传内容，返回给前端使用的结构。

    返回 dict：
        ok      : 是否可以当作聊天记录文本使用
        kind    : text / qq_backup / encrypted_db / zip / binary / empty
        error   : 给用户看的说明（ok=False 时）
        guide   : 操作建议列表（ok=False 时）
        text    : 解析出的文本（kind=text 时）
        encoding: 识别出的编码（kind=text 时）
    """
    name = (filename or "").strip() or "上传文件"

    if not data:
        return {
            "ok": False, "kind": "empty",
            "error": "文件是空的，请换一份聊天记录再试。",
            "guide": ["在 QQ 里复制聊天内容，直接粘贴到上面的输入框也可以。"],
        }

    # 1) QQ 加密备份（ZIP 包）
    if looks_like_qq_backup(data):
        return {
            "ok": False, "kind": "qq_backup",
            "error": f"「{name}」是 QQ 的**加密备份包**（.bak），网站无法直接读到里面的文字。",
            "guide": [
                "这是正常的：.bak 里的聊天记录被加密了，密钥只在 QQ 登录时由腾讯服务器下发，任何网站都解不开。",
                "方法一（推荐，零安装）：在 QQ 里打开课程群，右键消息 → 多选 → 勾选要用的记录 → 复制，然后粘贴到页面最上面的「懒人用法」框。",
                "方法二：在 QQ 桌面端点「导入聊天记录」把这份 .bak 导入，再导出为 txt 后上传。",
                "方法三：把聊天记录逐条复制粘贴进标准输入框（时间 | 发送人 | 群名 | 内容）。",
            ],
        }

    # 2) 单独的加密数据库（有些备份是单个文件，不是 ZIP）
    if looks_like_encrypted_db(data):
        return {
            "ok": False, "kind": "encrypted_db",
            "error": f"「{name}」是 QQ 的**加密数据库**，网站无法离线解密。",
            "guide": [
                "密钥由腾讯服务器在登录时下发，且按设备独立，无法离线推导。",
                "请在 QQ 里复制聊天内容后直接粘贴到页面的「懒人用法」框。",
            ],
        }

    # 3) 其他 ZIP（不是 QQ 备份）
    if looks_like_zip(data):
        return {
            "ok": False, "kind": "zip",
            "error": f"「{name}」是一个压缩包，请先解压出里面的 txt 再上传。",
            "guide": ["解压后选择 .txt 文件上传，或直接把内容粘贴到输入框。"],
        }

    # 4) 尝试当文本解码
    text, enc = decode_text(data)
    if text is None:
        return {
            "ok": False, "kind": "binary",
            "error": f"「{name}」不像文本文件，无法读取其中的聊天记录。",
            "guide": [
                "请上传 QQ 导出的 txt，或直接在 QQ 里复制聊天内容粘贴到输入框。",
                "如果它是图片 / 视频 / 表情，本工具无法分析。",
            ],
        }

    if not text.strip():
        return {
            "ok": False, "kind": "empty",
            "error": f"「{name}」里没有可读的文字内容。",
            "guide": ["请确认导出时选的是文本格式。"],
        }

    # 5) 文本，但可能不是聊天记录（例如 SQLite 明文库之类）
    if text.lstrip().startswith(_SQLITE_MAGIC.decode("latin-1")):
        return {
            "ok": False, "kind": "binary",
            "error": f"「{name}」是一个数据库文件，不是聊天记录文本。",
            "guide": ["请上传 QQ 导出的 txt，或直接粘贴聊天内容。"],
        }

    return {"ok": True, "kind": "text", "text": text, "encoding": enc, "error": "", "guide": []}
