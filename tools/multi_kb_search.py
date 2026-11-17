"""跨知识库检索工具。

与 knowledge_search 的区别：knowledge_search 需要模型自己指定库名，
当模型不知道问题属于哪个库时容易选错或干脆不检索；本工具直接遍历
所有知识库检索，再按 rerank 分数合并排序，返回全局最相关的片段。
"""

import os

import requests

from configs.setting import TIME_OUT

KB_API_BASE = os.environ.get("KB_API_BASE", "http://127.0.0.1:6605")
TOP_N = int(os.environ.get("MULTI_KB_TOP_N", "5"))


class MultiKnowledgeBaseSearch:
    inputs: str = "需要检索的完整问题"

    def _list_kbs(self):
        response = requests.get(f"{KB_API_BASE}/knowledgebase/list_kbs", timeout=TIME_OUT)
        response.raise_for_status()
        return [
            kb.get("kb_name")
            for kb in response.json().get("knowledgebases", [])
            if kb.get("kb_name")
        ]

    def _search_one(self, kb_name, query):
        response = requests.post(
            f"{KB_API_BASE}/knowledgebase/search_kb",
            json={"kb_name": kb_name, "query": query},
            timeout=TIME_OUT,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        return response.json().get("results", [])

    def run(self, query):
        query = (query or "").strip().strip('"').strip("'")
        if not query:
            return "multi kb search 需要输入一个要检索的问题"

        try:
            kb_names = self._list_kbs()
        except Exception as e:
            return f"获取知识库列表失败，无法跨库检索：{e}"

        if not kb_names:
            return "当前没有任何知识库，无法跨库检索"

        hits, errors = [], []
        for kb_name in kb_names:
            try:
                for item in self._search_one(kb_name, query):
                    hits.append(
                        {
                            "kb_name": kb_name,
                            "source": item.get("source", ""),
                            "content": item.get("page_contents", ""),
                            "score": item.get("relevance_score"),
                        }
                    )
            except Exception as e:
                # 单个库失败不影响其他库，不能抛异常打断 Agent
                errors.append(f"{kb_name}: {e}")

        if not hits:
            message = f"所有知识库都没有检索到与「{query}」相关的内容"
            if errors:
                message += f"（部分知识库检索失败：{'；'.join(errors[:3])}）"
            return message

        # 同一段内容可能被多个库/多个通道返回，按（库名 + 正文）去重
        unique = {}
        for hit in hits:
            unique.setdefault((hit["kb_name"], hit["content"]), hit)

        # 有分数的排前面并按分数降序，没有分数（rerank 降级）的排最后
        ranked = sorted(
            unique.values(),
            key=lambda hit: (
                hit["score"] is not None,
                hit["score"] if isinstance(hit["score"], (int, float)) else 0.0,
            ),
            reverse=True,
        )[:TOP_N]

        lines = []
        for index, hit in enumerate(ranked, 1):
            score = (
                f"{hit['score']:.4f}"
                if isinstance(hit["score"], (int, float))
                else "N/A"
            )
            lines.append(
                f"[{index}] knowledge_base: {hit['kb_name']}\n"
                f"source: {hit['source']}\n"
                f"score: {score}\n"
                f"context:\n{hit['content']}\n"
            )
        result = "".join(lines)
        if errors:
            result += f"\n(部分知识库检索失败：{'；'.join(errors[:3])})\n"
        return result


multi_kb_search = MultiKnowledgeBaseSearch()
