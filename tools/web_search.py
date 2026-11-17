"""联网搜索工具(SerpAPI,Baidu 引擎)。

密钥来源:configs/setting.py 的 SERPAPI_KEY(读 .env / 环境变量)。
未配置密钥时不抛异常,而是返回明确提示 —— 保证 ReAct Agent 链不会被打断。
"""

import requests

from configs.setting import TIME_OUT, SERPAPI_KEY


class WebSearch:
    def __init__(self, api_key):
        self.api_key = api_key

    def run(self, query):
        query = (query or "").strip().strip('"').strip("'").split("\n")[0].strip()
        if not query:
            return "web search 需要输入要检索的问题"

        if not self.api_key:
            return (
                "web search 工具未配置 SERPAPI_KEY,无法执行网络搜索"
                "(请在 .env 中配置 SERPAPI_KEY,申请地址 https://serpapi.com)"
            )

        search_url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "baidu",
        }

        # 工具失败必须返回文本而不是抛异常,否则会打断 Agent 链
        try:
            response = requests.get(search_url, params=params, timeout=TIME_OUT)
        except Exception as e:
            return f"网络搜索失败({query}):{e}"

        if response.status_code != 200:
            return f"无法获取{query}的信息,状态码: {response.status_code}"

        data = response.json()
        organic_results = data.get("organic_results", [])
        if not organic_results:
            return f"网络搜索成功,但没有返回结果,query: {query}"

        results = "".join(
            f"title:\n{result.get('title', '')}\n{result.get('link', '')}\n{result.get('snippet', '')}\n"
            for result in organic_results
        )
        return results


# 密钥来自 .env 的 SERPAPI_KEY,不再硬编码空字符串
web_search = WebSearch(SERPAPI_KEY)
