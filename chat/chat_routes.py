import asyncio
from typing import Any, AsyncIterable, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from pydantic import BaseModel, Field

from tools.tools_select import tools
from configs.prompt import PROMPT_TEMPLATES
from configs.setting import chat_model_name, api_key, base_url, TIME_OUT
from utils.callback import CustomAsyncIteratorCallbackHandler
from db_server.base import session
from db_server.knowledge_base_repository import list_kb_from_db


# 聊天接口统一挂在 /chat 前缀下，最终路径是 /chat/chatbot
chat_router = APIRouter(prefix="/chat", tags=["chat 对话"])


class AgentChatRequest(BaseModel):
    """聊天请求体（与 webui 前端保持一致，JSON 格式）。"""

    query: str = Field(..., description="用户输入")
    documents: str = Field("", description="随对话上传的文件解析出的文本内容")
    sys_prompt: str = Field("You are a helpful assistant.", description="系统提示")
    history_len: int = Field(-1, description="保留历史消息的数量，<=0 表示全部保留")
    history: List[Any] = Field(default_factory=list, description="历史对话，支持 [{'role','content'}] 或 [(role, content)]")
    temperature: float = Field(0.5, description="LLM 采样温度")
    top_p: float = Field(0.5, description="LLM 核采样参数")
    max_tokens: int = Field(1024, description="LLM 最大 token 数")
    session_id: str | None = Field(None, description="会话标识")


def _content_to_text(content: Any) -> str:
    """把历史消息里的 content 统一转成文本。

    Gradio 多模态消息的 content 可能是字符串、{"path": ...} 或它们的列表。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        path = content.get("path")
        return path if path else str(content)
    if isinstance(content, (list, tuple)):
        return "".join(_content_to_text(item) for item in content)
    return str(content)


def build_histories(req: AgentChatRequest) -> str:
    """把历史消息拼成传给模型的文本。"""
    history = list(req.history or [])
    if req.history_len > 0:
        history = history[-2 * req.history_len:]

    lines = []
    for msg in history:
        if isinstance(msg, dict):
            lines.append(f"{msg.get('role')}:\n{_content_to_text(msg.get('content'))}\n\n")
        elif isinstance(msg, (list, tuple)) and len(msg) >= 2:
            lines.append(f"{msg[0]}:{msg[1]}\n\n")
    return "".join(lines)


async def agent_chat_iterator(req: AgentChatRequest) -> AsyncIterable[str]:
    callback = CustomAsyncIteratorCallbackHandler()
    chat_model = ChatOpenAI(
        model=chat_model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
        streaming=True,
        callbacks=[callback],
    )

    system_prompt = SystemMessagePromptTemplate.from_template(req.sys_prompt)
    human_prompt = HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATES["agent"])
    chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])

    agent = create_react_agent(chat_model, tools, chat_prompt, stop_sequence=["\nObserv"])
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )

    knowledgebases = list_kb_from_db(session)
    kbs = "".join(f"{kb['kb_name']} - {kb['kb_info']}\n" for kb in knowledgebases)

    task = asyncio.create_task(
        agent_executor.acall(
            inputs={
                "input": req.query,
                "history": build_histories(req),
                "knowledgebases": kbs,
                "documents": req.documents,
            }
        )
    )

    async def stream_tokens():
        """把最终答案的 token 流出来。

        如果 agent 任务先结束（解析失败等），也正常收尾，绝不无限等待；
        外层再套一个整体超时兜底。
        """
        while not callback.done.is_set() or not callback.queue.empty():
            if task.done() and callback.queue.empty():
                return
            try:
                token = await asyncio.wait_for(callback.queue.get(), timeout=0.5)
                yield token
            except asyncio.TimeoutError:
                continue

    try:
        async with asyncio.timeout(TIME_OUT):
            async for token in stream_tokens():
                yield token
    except asyncio.TimeoutError:
        task.cancel()
        return

    # 正常收尾：等待 agent 结束，任务异常会在这里抛给客户端
    if not task.done():
        try:
            await asyncio.wait_for(task, TIME_OUT)
        except asyncio.TimeoutError:
            task.cancel()


@chat_router.post("/agent_chat")
async def agent_chat(req: AgentChatRequest):
    return StreamingResponse(agent_chat_iterator(req), media_type="text/plain; charset=utf-8")
