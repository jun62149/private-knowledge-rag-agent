"""知识库清单类工具：让 Agent 自己查"有哪些库""这个库里有哪些文件"。

之前库清单是硬编码塞进提示词的，模型看不到库里到底有哪些文件；
做成工具后可以按需查询，也避免了提示词随库数量膨胀。
"""

import os

import requests

from configs.setting import TIME_OUT

KB_API_BASE = os.environ.get("KB_API_BASE", "http://127.0.0.1:6605")


class KnowledgeBaseList:
    inputs: str = "无需输入，直接调用即可"

    def run(self, _inputs=""):
        try:
            response = requests.get(f"{KB_API_BASE}/knowledgebase/list_kbs", timeout=TIME_OUT)
            response.raise_for_status()
            knowledgebases = response.json().get("knowledgebases", [])
        except Exception as e:
            return f"获取知识库列表失败：{e}"

        if not knowledgebases:
            return "当前没有任何知识库"

        lines = [
            f"- {kb.get('kb_name', '')}"
            + (f"（简介：{kb.get('kb_info')}）" if kb.get("kb_info") else "")
            for kb in knowledgebases
        ]
        return "现有知识库：\n" + "\n".join(lines)


class KnowledgeBaseFiles:
    inputs: str = "知识库名称"

    def run(self, kb_name):
        kb_name = (kb_name or "").strip().strip('"').strip("'").split("\n")[0].strip()
        if not kb_name:
            return "list kb files 需要输入知识库名称"

        try:
            response = requests.get(
                f"{KB_API_BASE}/knowledgebase/list_files",
                params={"kb_name": kb_name},
                timeout=TIME_OUT,
            )
        except Exception as e:
            return f"获取知识库文件列表失败：{e}"

        if response.status_code == 404:
            return f"知识库「{kb_name}」不存在"
        if response.status_code != 200:
            return f"获取知识库文件列表失败：HTTP {response.status_code}"

        files = response.json().get("files", [])
        if not files:
            return f"知识库「{kb_name}」中还没有上传任何文件"
        return (
            f"知识库「{kb_name}」中的文件：\n"
            + "\n".join(f"- {name}" for name in files)
        )


knowledgebase_list = KnowledgeBaseList()
knowledgebase_files = KnowledgeBaseFiles()
