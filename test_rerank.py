"""检索质量命令行测试脚本。

用法:
    python test_rerank.py <知识库名> "<问题>"
    python test_rerank.py <知识库名> "<问题>" --raw     # 打印原始 JSON 响应
    python test_rerank.py --help

示例:
    python test_rerank.py 黑悟空 "黑熊精是怎么得到袈裟的？"

说明:
    直接复用 app_server 里 /knowledgebase/search_kb 的同一份实现
    (knowledgebase_server.kb_routes.search_kb),因此结果与界面完全一致,
    无需先启动 FastAPI 服务即可离线观察「混合召回 → 重排」的效果。
"""

import argparse
import asyncio
import json
import os
import sys
import time

# 保证从任意目录运行都能 import 到项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _fmt_score(score):
    if isinstance(score, (int, float)):
        return f"{score:.4f}"
    return "N/A"


async def _run(kb_name: str, query: str, top_n: int, raw: bool) -> int:
    from knowledgebase_server.kb_routes import search_kb

    print("=" * 74)
    print(f"知识库 : {kb_name}")
    print(f"问题   : {query}")
    print("=" * 74)

    t0 = time.time()
    try:
        result = await search_kb(kb_name=kb_name, query=query)
    except Exception as e:
        print(f"[失败] 检索出错:{type(e).__name__}: {e}")
        return 1
    elapsed = time.time() - t0

    if raw:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    items = result.get("results", [])
    if not items:
        print(f"[空] 未召回任何片段(耗时 {elapsed:.2f}s)")
        print("     可能原因:知识库为空、问题与该库内容无关,或索引尚未建立。")
        return 2

    print(f"命中 {len(items)} 条(耗时 {elapsed:.2f}s,展示前 {min(top_n, len(items))} 条)\n")
    for i, item in enumerate(items[:top_n], 1):
        source = item.get("source", "")
        content = (item.get("page_contents") or "").replace("\n", " ")
        print(f"[{i}] score={_fmt_score(item.get('relevance_score'))}")
        print(f"    source : {os.path.basename(source) if source else '(未知)'}")
        print(f"    context: {content[:160]}{'…' if len(content) > 160 else ''}")
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检索质量测试:直接调用 search_kb,观察混合召回与重排结果")
    parser.add_argument("kb_name", nargs="?", help="知识库名称(即 knowledgebases/<名称>.faiss)")
    parser.add_argument("query", nargs="?", help="要检索的问题")
    parser.add_argument("--raw", action="store_true", help="打印原始 JSON 响应")
    parser.add_argument("--top-n", type=int, default=5, help="最多展示多少条(默认 5)")
    parser.add_argument("--list", action="store_true", help="仅列出已有知识库后退出")
    args = parser.parse_args()

    if args.list:
        from db_server.base import session
        from db_server.knowledge_base_repository import list_kb_from_db
        kbs = list_kb_from_db(session)
        print("已有知识库:")
        for kb in kbs:
            print(f"  - {kb['kb_name']}  (简介: {kb['kb_info'] or '无'})")
        if not kbs:
            print("  (无)")
        return 0

    if not args.kb_name or not args.query:
        parser.print_help()
        print("\n示例:python test_rerank.py 黑悟空 \"黑熊精是怎么得到袈裟的？\"")
        return 1

    return asyncio.run(_run(args.kb_name, args.query, args.top_n, args.raw))


if __name__ == "__main__":
    sys.exit(main())