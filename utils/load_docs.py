"""多格式纯文本提取:把上传/随对话附带的文件抽成纯文本。

设计要点:
    ① 可选依赖惰性加载:PDF 解析按 PyMuPDF → pypdf 顺序回退,两个都没有时
       只返回可读提示;python-docx 同理。模块导入本身永不失败 ——
       保证 Gradio / ReAct Agent 链不被打断。
    ② get_file_content() 全程不抛异常,统一返回 (文本, 错误信息) 二元组,
       调用方据此决定展示内容还是展示提示。
    ③ 超长文本按 MAX_CHARS 截断,避免把整个大文件塞进 prompt。

被 webui/chat_with_agent_api.py::_read_document() 调用(聊天窗附件解析)。
"""

import json
import os

# 单文件抽取上限:超出部分截断,防止把上下文撑爆
MAX_CHARS = int(os.environ.get("ATTACHMENT_MAX_CHARS", "20000"))

# 这些是二进制/媒体格式,抽不出有意义正文,直接给出明确提示
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ico",
    ".mp3", ".wav", ".mp4", ".avi", ".mov", ".mkv",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".xls", ".xlsx", ".ppt", ".pptx",
}

SUPPORTED_EXTS = {".txt", ".md", ".py", ".csv", ".json", ".pdf", ".docx"}


def _truncate(text: str) -> str:
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + f"\n…(已截断到前 {MAX_CHARS} 字)"
    return text


def _read_pdf_with_pymupdf(file_path: str) -> str:
    import fitz  # PyMuPDF

    parts = []
    with fitz.open(file_path) as pdf_document:
        for page_num in range(pdf_document.page_count):
            parts.append(pdf_document[page_num].get_text() + "\n")
    return "".join(parts)


def _read_pdf_with_pypdf(file_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    return "".join((page.extract_text() or "") + "\n" for page in reader.pages)


def _read_pdf(file_path: str) -> str:
    """PDF 解析:P yMuPDF → pypdf 依次回退,都不可用时报明确安装提示。"""
    errors = []
    for reader in (_read_pdf_with_pymupdf, _read_pdf_with_pypdf):
        try:
            return reader(file_path)
        except ImportError as e:
            errors.append(f"{reader.__name__}: {e}")
            continue
        except Exception as e:
            # 依赖已安装但解析失败(加密/损坏等):直接报错,不必换库重试
            raise RuntimeError(f"PDF 内容解析失败:{e}")
    raise RuntimeError(
        "解析 PDF 需要 PyMuPDF 或 pypdf,当前环境都没有"
        "(请执行 pip install pypdf,或 pip install pymupdf)"
    )


def _read_docx(file_path: str) -> str:
    """用 python-docx 抽段落文本;未安装时给出安装提示。"""
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError(
            "解析 Word 需要 python-docx,当前环境未安装(请执行 pip install python-docx)"
        )
    document = Document(file_path)
    return "".join(paragraph.text + "\n" for paragraph in document.paragraphs)


def get_file_content(file_path: str):
    """把文件抽成纯文本。

    返回 (text, error):
        成功 → (正文, "")
        失败 → ("", 可读的错误说明)
    """
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    if ext in BINARY_EXTS:
        return "", f"[附件 {filename} 是二进制/媒体格式,无法抽取正文,请改用知识库上传]"

    try:
        if ext in (".txt", ".md", ".py", ".csv"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = json.dumps(json.load(f), indent=4, ensure_ascii=False)

        elif ext == ".pdf":
            content = _read_pdf(file_path)

        elif ext == ".docx":
            content = _read_docx(file_path)

        else:
            return "", f"[附件 {filename} 格式暂不支持解析,当前支持:{', '.join(sorted(SUPPORTED_EXTS))}]"

    except RuntimeError as e:
        # 缺可选依赖 / 解析失败:提示明确,不抛给上层
        return "", f"[附件 {filename} 解析失败:{e}]"
    except json.JSONDecodeError as e:
        return "", f"[附件 {filename} 不是合法 JSON:{e}]"
    except Exception as e:
        return "", f"[附件 {filename} 读取失败:{e}]"

    if not content.strip():
        return "", f"[附件 {filename} 解析成功,但内容为空]"

    return _truncate(content), ""
