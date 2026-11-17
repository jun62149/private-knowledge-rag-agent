import os

import requests

from utils.load_docs import get_file_content

chat_with_agent_url = os.environ.get(
    "CHAT_API_URL", "http://127.0.0.1:6605/chat/agent_chat"
)


def _resolve_file_path(item):
    """Gradio 多模态消息里的文件项可能是路径字符串或 {"path": ...} 字典。"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("path") or item.get("data")
    return None


def _read_document(path):
    """把附件解析成文本,随 documents 一起发给后端作为上下文。

    统一走 utils.load_docs.get_file_content:txt/md/py/csv/json 直接读,
    pdf/docx 走可选依赖解析,二进制与未知格式返回可读提示。
    """
    filename = os.path.basename(path)
    text, error = get_file_content(path)
    if error:
        return error
    return f"文件: {filename}\n内容:\n{text}"


def chat_with_agent(prompt, history, sys_prompt, history_len, temperature, top_p, max_tokens, stream, session_id):
    """与后端 /chat/agent_chat 通信（JSON 请求体 + 纯文本流式响应）。"""
    if isinstance(prompt, dict):
        text = prompt.get("text", "")
        raw_files = prompt.get("files") or []
    else:
        text = prompt or ""
        raw_files = []

    documents = []
    for item in raw_files:
        path = _resolve_file_path(item)
        if path:
            documents.append(_read_document(path))

    data = {
        "query": text,
        "documents": "\n\n".join(documents),
        "sys_prompt": sys_prompt,
        "history_len": history_len,
        "history": history,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "session_id": session_id,
    }

    try:
        response = requests.post(chat_with_agent_url, json=data, stream=True)
        if response.status_code == 200:
            chunks = ""
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    chunks += chunk
                    if stream:
                        yield chunks
            if not stream and chunks:
                yield chunks
        else:
            yield f"请求失败（状态码 {response.status_code}），请检查后台服务器是否正常运行。"
    except Exception as e:
        yield f"发生错误：{e}"
