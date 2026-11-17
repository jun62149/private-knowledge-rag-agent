"""验证 utils/load_docs.get_file_content 的各条分支。"""
import json
import os
import sys
import tempfile

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WS)

from utils.load_docs import get_file_content, MAX_CHARS  # noqa: E402

temp_dir = tempfile.TemporaryDirectory()
tmp = temp_dir.name
results = []


def case(name, path, expect_ok):
    text, err = get_file_content(path)
    ok = (not err) if expect_ok else bool(err)
    results.append((name, ok, err or f"{len(text)} 字"))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {err or str(len(text)) + ' 字'}")


def w(name, content, mode="w"):
    p = os.path.join(tmp, name)
    with open(p, mode, encoding=None if "b" in mode else "utf-8") as f:
        f.write(content)
    return p


# 1. txt
case("txt 正常", w("a.txt", "你好,这是一段测试文本。"), True)
# 2. md / py 走同一条分支
case("md 正常", w("a.md", "# 标题\n正文"), True)
case("py 正常", w("a.py", "print(1)"), True)
# 3. csv
case("csv 正常", w("a.csv", "a,b\n1,2\n"), True)
# 4. json 合法
case("json 合法", w("a.json", json.dumps({"k": "值", "n": 1}, ensure_ascii=False)), True)
# 5. json 非法 → 必须返回错误而不是抛异常
case("json 非法", w("a.json", "{不是合法 json"), False)
# 6. docx(真实文件,python-docx 已安装)
try:
    from docx import Document
    d = Document()
    d.add_paragraph("第一段:知识库测试文档")
    d.add_paragraph("第二段:混合检索")
    dp = os.path.join(tmp, "a.docx")
    d.save(dp)
    case("docx 正常", dp, True)
except ImportError:
    print("[SKIP] docx:未安装 python-docx")

# 7. pdf:PyMuPDF → pypdf 回退链
try:
    import fitz  # noqa: F401
    has_pdf_lib = "fitz"
except ImportError:
    try:
        import pypdf  # noqa: F401
        has_pdf_lib = "pypdf"
    except ImportError:
        has_pdf_lib = None

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 24 Tf 20 100 Td (Hello PDF) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""


def build_valid_pdf(path):
    """手写一个带正确 xref 的合法 PDF,内含一行可抽取的英文文字。"""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 18 Tf 30 120 Td (Hello PDF Knowledge Base) Tj ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(buf))
        buf += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_off = len(buf)
    buf += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n"
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += ("%010d 00000 n \n" % off).encode()
    buf += b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\n"
    buf += b"startxref\n" + str(xref_off).encode() + b"\n%%EOF\n"
    with open(path, "wb") as f:
        f.write(buf)
    return path


pdf_path = build_valid_pdf(os.path.join(tmp, "a.pdf"))
text, err = get_file_content(pdf_path)
if has_pdf_lib:
    ok = (not err) and "Hello PDF Knowledge Base" in text
    results.append(("pdf 文字抽取", ok, err or repr(text.strip())))
    print(f"[{'PASS' if ok else 'FAIL'}] pdf 文字抽取({has_pdf_lib}): {err or repr(text.strip())}")
else:
    ok = bool(err) and "pypdf" in err
    results.append(("pdf 无依赖时优雅退化", ok, err))
    print(f"[{'PASS' if ok else 'FAIL'}] pdf 无依赖时优雅退化: {err}")

# 7b. 损坏的 PDF → 报解析失败,不冒泡异常
bad_pdf = os.path.join(tmp, "broken.pdf")
with open(bad_pdf, "wb") as f:
    f.write(b"%PDF-1.4\n%not-a-real-pdf\n")
case("pdf 损坏文件", bad_pdf, False)

# 8. 二进制格式 → 明确提示
png = os.path.join(tmp, "a.png")
with open(png, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
case("png 二进制提示", png, False)

# 9. 未知格式 → 明确提示
case("未知格式 .xyz", w("a.xyz", "whatever"), False)

# 10. 空文件 → 明确提示
case("空 txt", w("empty.txt", "   \n  "), False)

# 11. 不存在的文件 → 不抛异常
case("文件不存在", os.path.join(tmp, "nope.txt"), False)

# 12. 超长截断
big = os.path.join(tmp, "big.txt")
with open(big, "w", encoding="utf-8") as f:
    f.write("字" * (MAX_CHARS + 500))
text, err = get_file_content(big)
ok = (not err) and "已截断" in text and len(text) < MAX_CHARS + 200
results.append(("超长截断", ok, f"{len(text)} 字"))
print(f"[{'PASS' if ok else 'FAIL'}] 超长截断: {len(text)} 字 (MAX={MAX_CHARS})")

# 13. 中文不被打乱
p = w("cn.txt", "中文编码测试:你好,世界。")
text, err = get_file_content(p)
ok = (not err) and "你好,世界" in text
results.append(("中文编码", ok, text.strip()))
print(f"[{'PASS' if ok else 'FAIL'}] 中文编码: {text.strip()}")

bad = [r for r in results if not r[1]]
print("\n==== 汇总 ====")
print(f"共 {len(results)} 项,通过 {len(results) - len(bad)},失败 {len(bad)}")
for name, _, info in bad:
    print(f"  FAIL {name}: {info}")
temp_dir.cleanup()
sys.exit(1 if bad else 0)
