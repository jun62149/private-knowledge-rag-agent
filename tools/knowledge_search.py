import os
import json
import requests
from pydantic import Field
from configs.setting import TIME_OUT

KB_API_BASE = os.environ.get("KB_API_BASE", "http://127.0.0.1:6605")


class KnowledgeBaseSearch:
    inputs:str=Field(description="包含知识库名称和需要查询问题的字符串")
    def run(self, inputs):
        # 兼容中英文逗号，只按第一个逗号切分，避免问题本身带逗号时解析失败
        inputs = (inputs or "").strip()
        normalized = inputs.replace("，", ",")
        if "," not in normalized:
            return "knowledge search 的输入应形如：知识库名,问题"
        kb_name, query = normalized.split(",", 1)
        kb_name, query = kb_name.strip(), query.strip()
        if not kb_name or not query:
            return "knowledge search 的输入应形如：知识库名,问题"

        url = f"{KB_API_BASE}/knowledgebase/search_kb"
        data = {
            "kb_name": kb_name,
            "query": query
        }
        json_data = json.dumps(data)
        headers ={
            'Content-Type':'application/json'
            }
        try:
            response = requests.post(url, data=json_data, headers=headers, timeout=TIME_OUT)
        except Exception as e:
            # 工具失败必须返回文本而不是抛异常，否则会打断 Agent 链
            return f"检索知识库失败（{kb_name}）：{e}"

        if response.status_code == 200:
            data = response.json()
            if 'results' not in data or not data['results']:
                return f"服务返回成功，但 results 为空，query: {query}"

            def _format_score(d):
                score = d.get("relevance_score")
                if isinstance(score, (int, float)):
                    return f"{score:.4f}"
                return "N/A"

            res = "".join([
                f"source:\n{d.get('source', '')}\n"
                f"score:\n{_format_score(d)}\n"
                f"context:\n{d.get('page_contents', '')}\n"
                for d in data['results']
            ])
            return res
        else:
            return f"无法获取{query}有关信息，状态码: {response.status_code}"

knowledgebase_search = KnowledgeBaseSearch()
