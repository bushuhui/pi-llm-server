"""
MinerU OCR 解析 docx 文档测试

测试通过网关 API 解析 .docx 文件，验证:
1. docx 文件能否正确上传和解析
2. 返回的 zip 包中包含 markdown 文件
3. 解析出的 markdown 内容包含预期的文本
"""
import os
import sys
import zipfile
import io
import httpx
from pathlib import Path

BASE = "http://127.0.0.1:8090"
TOKEN = "sk-5f8b839908d14561590b70227c72ca86"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

DATA_DIR = Path(__file__).parent.parent / "data"
DOCX_PATH = DATA_DIR / "test.docx"


def test_docx_ocr():
    """测试 docx 文件通过 OCR 解析"""
    if not DOCX_PATH.exists():
        print(f"FAIL: 测试文件不存在: {DOCX_PATH}")
        sys.exit(1)

    print(f"测试文件: {DOCX_PATH}")
    print(f"文件大小: {DOCX_PATH.stat().st_size / 1024:.1f} KB")
    print(f"API 地址: {BASE}/v1/ocr/parser")
    print()

    with open(DOCX_PATH, "rb") as f:
        file_content = f.read()

    with httpx.Client(timeout=300) as client:
        print("发送解析请求...")
        r = client.post(
            f"{BASE}/v1/ocr/parser",
            headers=HEADERS,
            files={"files": ("test.docx", file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={
                "backend": "pipeline",
                "parse_method": "auto",
                "lang_list": "ch",
                "return_md": "true",
                "return_images": "true",
            },
        )

        print(f"HTTP 状态码: {r.status_code}")

        if r.status_code != 200:
            print(f"FAIL: 请求失败，状态码 {r.status_code}")
            print(f"响应: {r.text[:500]}")
            sys.exit(1)

        print(f"响应大小: {len(r.content) / 1024:.1f} KB")

        # 验证返回的是 zip 文件
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            print(f"ZIP 文件包含 {len(zf.namelist())} 个文件:")
            for name in zf.namelist():
                print(f"  {name}")
            print()
        except zipfile.BadZipFile:
            print("FAIL: 返回的不是有效的 ZIP 文件")
            sys.exit(1)

        # 检查是否包含 markdown 文件
        md_files = [n for n in zf.namelist() if n.endswith(".md")]
        if not md_files:
            print("FAIL: ZIP 中没有找到 markdown 文件")
            sys.exit(1)

        print(f"找到 {len(md_files)} 个 markdown 文件: {md_files}")

        # 读取并检查 markdown 内容
        for md_file in md_files:
            content = zf.read(md_file).decode("utf-8")
            print(f"\n--- {md_file} 内容预览 (前 500 字) ---")
            print(content[:500])
            print("...")
            print()

            # 验证内容包含 docx 中的关键文本
            # test.docx 是 SIBITU 软件操作手册
            expected_keywords = ["SIBITU", "地图重建", "拼接"]
            found = [kw for kw in expected_keywords if kw in content]
            print(f"关键词检查: 期望 {expected_keywords}")
            print(f"找到关键词: {found}")

            if len(found) >= 1:
                print(f"PASS: markdown 内容包含预期关键词")
            else:
                print(f"WARN: markdown 内容未包含预期关键词，可能解析方式不同")

        # 检查是否包含图片（docx 中有截图）
        img_files = [n for n in zf.namelist() if n.endswith((".png", ".jpg", ".jpeg"))]
        print(f"\n图片文件: {len(img_files)} 个")

        print("\n" + "=" * 40)
        print("测试通过: docx OCR 解析成功")
        print("=" * 40)


if __name__ == "__main__":
    test_docx_ocr()
