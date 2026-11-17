"""快速冒烟脚本:不启动服务,直接验证「知识库检索工具」链路是否可用。

用途:
    在演示/答辩前跑一次,3 秒内确认环境没坏(索引在、嵌入模型能加载、
    BM25 与 FAISS 双通道能召回、Reranker 在线接口能返回分数)。

用法:
    python test1.py                          # 用第一个可用知识库跑默认问题
    python test1.py 黑悟空 "问题文本"

与 test_rerank.py 的区别:
    test_rerank.py 关注「检索质量」(看 Top-N 与分数);
    test1.py       关注「链路是否通」(只看通过/失败)。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_QUERY = "这个知识库里讲了什么？"


def _fail(msg, hint=""):
    print(f"  [FAIL] {msg}")
    if hint:
        print(f"         {hint}")
    return False


def main() -> int:
    print("=" * 70)
    print("知识库检索链路冒烟测试")
    print("=" * 70)
    ok = True

    # ---------- 1. 配置 ----------
    print("\n[1/5] 读取配置")
    try:
        from configs.setting import (KB_DIR, embedding_model_path,
                                     RERANK_MODEL_NAME, SEARCH_CANDIDATE_K,
                                     RERANK_TOP_N)
        print(f"  KB_DIR               = {KB_DIR}")
        print(f"  嵌入模型             = {embedding_model_path}")
        print(f"  Reranker 模型        = {RERANK_MODEL_NAME}")
        print(f"  召回 K / 精排 Top-N  = {SEARCH_CANDIDATE_K} / {RERANK_TOP_N}")
    except Exception as e:
        return _fail(f"配置导入失败:{e}") or 1

    # ---------- 2. 嵌入模型目录 ----------
    print("\n[2/5] 检查本地嵌入模型")
    if os.path.isdir(embedding_model_path):
        n = len(os.listdir(embedding_model_path))
        print(f"  [OK] 模型目录存在,{n} 个文件")
    else:
        ok = _fail("嵌入模型目录不存在",
                   "先运行:python utils/downloader.py")

    # ---------- 3. 知识库清单与索引 ----------
    print("\n[3/5] 检查知识库与索引文件")
    kbs = []
    try:
        from db_server.base import session
        from db_server.knowledge_base_repository import list_kb_from_db
        kbs = [k["kb_name"] for k in list_kb_from_db(session)]
        print(f"  元数据中知识库: {kbs or '(无)'}")
    except Exception as e:
        ok = _fail(f"读取元数据失败:{e}")

    if os.path.isdir(KB_DIR):
        idx = [f[:-6] for f in os.listdir(KB_DIR) if f.endswith(".faiss")]
        print(f"  索引文件: {idx or '(无)'}")
        if not idx:
            ok = _fail("没有任何 .faiss 索引", "先在界面「知识库管理」里上传文档并向量化")
    else:
        ok = _fail(f"索引目录不存在:{KB_DIR}")

    # ---------- 4. 选定目标知识库 ----------
    print("\n[4/5] 选定测试目标")
    kb_name = sys.argv[1] if len(sys.argv) > 2 else (kbs[0] if kbs else None)
    query = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_QUERY
    if not kb_name:
        return _fail("没有可用于测试的知识库") or 1
    print(f"  知识库 = {kb_name}")
    print(f"  问题   = {query}")

    # ---------- 5. 实跑检索 ----------
    print("\n[5/5] 执行检索(混合召回 + 重排)")
    import asyncio
    try:
        from knowledgebase_server.kb_routes import search_kb
        t0 = time.time()
        res = asyncio.run(search_kb(kb_name=kb_name, query=query))
        dt = time.time() - t0
        items = res.get("results", [])
        print(f"  耗时 {dt:.2f}s,召回 {len(items)} 条")
        for i, it in enumerate(items[:3], 1):
            s = it.get("relevance_score")
            s = f"{s:.4f}" if isinstance(s, (int, float)) else "N/A"
            print(f"    [{i}] score={s}  {(it.get('page_contents') or '')[:60]!r}")
        if not items:
            ok = _fail("检索返回为空", "确认该知识库已上传文档且内容与问题相关")
        else:
            print("  [OK] 检索链路正常")
    except Exception as e:
        ok = _fail(f"检索异常:{type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("结论:" + ("全部通过,可以演示" if ok else "存在失败项,请先修复"))
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())