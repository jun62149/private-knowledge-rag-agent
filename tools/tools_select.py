from langchain_core.tools import Tool
from tools.knowledge_search import knowledgebase_search
from tools.multi_kb_search import multi_kb_search
from tools.kb_inventory import knowledgebase_list, knowledgebase_files
from tools.weather_check import weather_check
from tools.web_search import web_search
from tools.fetch_url import fetch_url
from tools.calculator import calculator

tools = [
    Tool(
        name="knowledge search",
        func=knowledgebase_search.run,
        description="在指定的本地知识库里检索内容。输入必须是由英文逗号','分割的两个字符串：第一个是知识库名称，第二个是要查询的问题。只有明确知道问题属于哪个知识库时才用这个工具，否则请用 multi kb search"
    ),

    Tool(
        name="multi kb search",
        func=multi_kb_search.run,
        description="当不确定问题属于哪个知识库时使用：会遍历所有本地知识库检索并返回最相关的片段（含来源、分数）。输入就是用户的完整问题，不需要指定知识库"
    ),

    Tool(
        name="list knowledge bases",
        func=knowledgebase_list.run,
        description="列出当前有哪些本地知识库及其简介，无需输入。当用户问“有哪些知识库”或需要确认库名时使用"
    ),

    Tool(
        name="list kb files",
        func=knowledgebase_files.run,
        description="列出某个知识库里已经上传的文件名。输入就是知识库名称。当用户问某个知识库包含哪些文档时使用"
    ),

    Tool(
        name="web search",
        func=web_search.run,
        description="通过网络搜索获取最新资讯或本地知识库中没有的内容，返回标题、链接和摘要"
    ),

    Tool(
        name="fetch url",
        func=fetch_url.run,
        description="抓取指定网页链接的正文内容。通常在 web search 返回链接后，需要阅读某个结果的具体内容时使用，输入是一个完整的网址"
    ),

    Tool(
        name="calculator",
        func=calculator.run,
        description="进行数学计算，支持四则运算、幂、括号和 sqrt/log/round/min/max 等函数。涉及数字运算（金额、比例、汇总）时必须用这个工具，输入是一个数学表达式"
    ),

    Tool(
        name="weather check",
        func=weather_check.run,
        description="获取指定城市或地点的实时天气信息，包括温度和天气状况等"
    )
]
