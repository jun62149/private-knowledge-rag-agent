"""全局配置：路径、LLM、检索 / 重排参数、超时等。

密钥读取顺序（后者覆盖前者）：
    1. 本文件的默认值（不含任何真实密钥）
    2. 项目根目录下的 .env 文件
    3. 进程已有的环境变量
所以 .env 里配一次即可，也可以用 export / docker -e 注入。
**不要把真实密钥写回本文件** —— .env 已在 .gitignore 中，本文件是要提交的。
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


def _load_dotenv(path: str) -> None:
    """极简 .env 读取器（不引入额外依赖）。

    每行形如 KEY=VALUE，以 # 开头的行为注释；已存在的环境变量不会被覆盖，
    保证「进程环境变量 > .env 文件」的优先级。
    """
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        # 读不到 .env 不应该让服务起不来，交给后续的缺省值 / 校验处理
        pass


_load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
SQLALCHEMY_DATABASE = "./db_server/data/"
SQLALCHEMY_DATABASE_URL = "sqlite:///db_server/data/info.db"

KB_DIR = "./knowledgebases"
FILE_STORAGE_DIR = "./data"
TEMP_FILE_STORAGE_DIR = "./temp/data"
MEDIA_DIR = "./temp/medias"

# 本地 Embedding 模型路径：默认取项目下的 model/ 目录（不再是写死的绝对路径）
embedding_model_path = os.environ.get(
    "EMBEDDING_MODEL_PATH",
    os.path.join(PROJECT_ROOT, "model", "bge-large-zh-v1__5"),
)

# --------------------------------------------------------------------------
# LLM（DeepSeek，OpenAI 兼容接口）
# --------------------------------------------------------------------------
chat_model_name = os.environ.get("CHAT_MODEL_NAME", "deepseek-v4-flash")
api_key = os.environ.get("DEEPSEEK_API_KEY", "")
base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

TIME_OUT = _env_int("TIME_OUT", 60)

# --------------------------------------------------------------------------
# 外部工具 API
# --------------------------------------------------------------------------
# 心知天气（weather check 工具）；在 https://www.seniverse.com 申请
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")

# SerpAPI（web search 工具）；在 https://serpapi.com 申请。留空则工具会返回明确提示而非崩溃
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# --------------------------------------------------------------------------
# Reranker：使用硅基流动 SiliconFlow 的 rerank API
# 模型为在线 API 模型，本地无需下载；在硅基流动控制台申请 API Key 后填入 .env
# --------------------------------------------------------------------------
RERANK_BASE_URL = os.environ.get(
    "RERANK_BASE_URL", "https://api.siliconflow.cn/v1/rerank"
)
RERANK_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
RERANK_MODEL_NAME = os.environ.get("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")

# 先取多少条候选给 reranker 重排，以及最终保留多少条
SEARCH_CANDIDATE_K = _env_int("SEARCH_CANDIDATE_K", 10)
RERANK_TOP_N = _env_int("RERANK_TOP_N", 3)

# 单条文档送入 rerank 接口前截断的最大字符数（防止超出模型输入长度）
RERANK_MAX_DOC_CHARS = _env_int("RERANK_MAX_DOC_CHARS", 2000)
