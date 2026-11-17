import shutil
import os
from typing import List
import jieba
import requests
from fastapi import APIRouter, Body, HTTPException,UploadFile, File, Form
from langchain_core.documents import Document        
from langchain_core.embeddings import Embeddings            
from langchain_community.vectorstores import FAISS 
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_huggingface import HuggingFaceEmbeddings    
from langchain_text_splitters import RecursiveCharacterTextSplitter
from db_server.base import session
from db_server.knowledge_base_repository import add_kb_to_db, del_kb_from_db, list_kb_from_db
from configs.setting import (
    KB_DIR,
    FILE_STORAGE_DIR,
    embedding_model_path,
    TIME_OUT,
    RERANK_BASE_URL,
    RERANK_API_KEY,
    RERANK_MODEL_NAME,
    SEARCH_CANDIDATE_K,
    RERANK_TOP_N,
    RERANK_MAX_DOC_CHARS,
)
from knowledgebase_server.loader.loader import data_loader

# 知识库相关接口统一挂在 /knowledge 前缀下
kb_router = APIRouter(prefix="/knowledgebase", tags=["Knowledge Bases Management"])

# ③ 修正 os.mkdirs -> os.makedirs
if not os.path.exists(KB_DIR):
    os.makedirs(KB_DIR)   # 注意是 makedirs


# ④ 自定义 Embeddings 类（如果需要的话，这里保留但未使用）
class CustomEmbeddingModel(Embeddings):
    def __init__(self, model, model_name):
        self.model = model
        self.model_name = model_name

    def embed_documents(self, texts):
        return [self.model.client.create(model=self.model_name, input=text).data[0].embedding for text in texts]

    def embed_query(self, text):
        return self.model.client.create(model=self.model_name, input=text).data[0].embedding


# 使用本地下载的模型路径
embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_path)


def _rerank_documents(query: str, documents: List[Document], top_n: int):
    try:
        response = requests.post(
            RERANK_BASE_URL,
            json={
                "model": RERANK_MODEL_NAME,
                "query": query,
                "documents": [doc.page_content[:RERANK_MAX_DOC_CHARS] for doc in documents],
                "top_n": min(top_n, len(documents)),
                "return_documents": False,
            },
            headers={
                "Authorization": f"Bearer {RERANK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=TIME_OUT,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")

        ranked = [
            item
            for item in response.json().get("results", [])
            if isinstance(item.get("index"), int) and 0 <= item["index"] < len(documents)
        ]
        if not ranked:
            raise RuntimeError("rerank 接口返回结果为空")
        ranked.sort(key=lambda item: item.get("relevance_score", 0.0), reverse=True)
        return [
            (documents[item["index"]], item.get("relevance_score"))
            for item in ranked
        ]
    except Exception as e:
        print(f"[rerank] 调用失败，回退为原始顺序前 {top_n} 条: {e}")
        return [(doc, None) for doc in documents[:top_n]]


@kb_router.post("/create_kb")
async def create_kb(
        kb_name: str = Body(..., description="知识库名称"),
        kb_info: str = Body("", description="知识库简介"),
):
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")

    if os.path.exists(kb_path):
        raise HTTPException(status_code=400, detail="知识库已存在")  # ⑥ 修正拼写和参数名

    doc = Document(page_content="init", metadata={})
    # ⑦ FAISS.from_documents 接收文档列表，注意方法名是 documents（复数）
    vector_store = FAISS.from_documents([doc], embedding_model, normalize_L2=True)

    # 清空刚插入的临时文档
    ids = list(vector_store.docstore._dict.keys())
    vector_store.delete(ids)
    vector_store.save_local(kb_path)
    add_kb_to_db(session, kb_name, kb_info)

    return {"message": f"知识库'{kb_name}'创建成功"}


@kb_router.get("/list_files")
async def list_files(kb_name: str):
    """列出指定知识库下已上传的所有文件名。"""
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="知识库不存在")

    kb_files_path = os.path.join(FILE_STORAGE_DIR, kb_name)
    if not os.path.isdir(kb_files_path):
        return {"kb_name": kb_name, "files": []}

    files = sorted(
        name
        for name in os.listdir(kb_files_path)
        if os.path.isfile(os.path.join(kb_files_path, name))
    )
    return {"kb_name": kb_name, "files": files}


@kb_router.delete("/delete_file")
async def delete_file(kb_name: str, file_name: str):
    """删除知识库中的某个文件，并同步删除该文件对应的 FAISS 向量。"""
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="知识库不存在")

    if os.path.basename(file_name) != file_name:
        raise HTTPException(status_code=400, detail="文件名称不合法")

    kb_files_path = os.path.join(FILE_STORAGE_DIR, kb_name)
    file_path = os.path.join(kb_files_path, file_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在于该知识库")

    removed_chunks = 0
    try:
        vector_store = FAISS.load_local(
            kb_path, embedding_model, allow_dangerous_deserialization=True
        )
        expected_sources = {
            file_name,
            os.path.normpath(file_path),
            os.path.normpath(os.path.abspath(file_path)),
        }
        # 只删除仍然存在于向量索引中的 doc，避免误删无效 id
        indexed_doc_ids = set(vector_store.index_to_docstore_id.values())
        ids_to_delete = []
        for doc_id, doc in vector_store.docstore._dict.items():
            if doc_id not in indexed_doc_ids:
                continue
            source = str(doc.metadata.get("source", ""))
            if (
                os.path.normpath(source) in expected_sources
                or os.path.basename(source) == file_name
            ):
                ids_to_delete.append(doc_id)

        if ids_to_delete:
            vector_store.delete(ids_to_delete)
            vector_store.save_local(kb_path)
            removed_chunks = len(ids_to_delete)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"从向量索引中删除对应内容失败，文件未被删除：{e}",
        )

    os.remove(file_path)
    return {
        "message": f"文件'{file_name}'删除成功",
        "removed_chunks": removed_chunks,
    }


@kb_router.delete("/delete_kb")
async def delete_kb(kb_name: str):
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    kb_files_path = os.path.join(FILE_STORAGE_DIR, kb_name)

    if not os.path.exists(kb_path):  # ⑧ 逻辑修正：不存在才报错，原来写反了
        raise HTTPException(status_code=404, detail="知识库找不到")
    shutil.rmtree(kb_path)
    if os.path.exists(kb_files_path):
        shutil.rmtree(kb_files_path)

    del_kb_from_db(session, kb_name)

    return {"message": f"知识库'{kb_name}'删除成功"}


@kb_router.get("/list_kbs")
async def list_kbs():
    return {"knowledgebases": list_kb_from_db(session)}

@kb_router.post("/upload_docs")
async def upload_docs(
    files: List[UploadFile] = File(...),
    kb_name: str = Form(..., description="知识库名称"),
    chunk_size: int = Form(128, description="知识库中单段文本最大长度"),
    chunk_overlap: int = Form(20, description="知识库中相邻文本重合长度"),
):
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")  
    kb_file_storage_path = os.path.join(FILE_STORAGE_DIR, kb_name)

    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database not found")

    os.makedirs(kb_file_storage_path, exist_ok=True)
    updated_file = []
    for file in files:
        file_path = os.path.join(kb_file_storage_path, file.filename)
        file_content = file.file.read()

        with open(file_path, "wb") as f:
            f.write(file_content)

        loader = data_loader().get_loader(file_path)
        docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n\n", "\n", " ", ".", ",", "，", "。", ""])
        chunks = text_splitter.split_documents(docs)
        vectorstore = FAISS.load_local(kb_path, embedding_model, allow_dangerous_deserialization=True)
        vectorstore.add_documents(chunks)
        vectorstore.save_local(kb_path)
        updated_file.append(file.filename)
    return {"message": f"File '{updated_file}' added to database '{kb_name}' successfully"}

@kb_router.post("/search_kb")
async def search_kb(
    kb_name:str = Body(...,description="知识库名称"),
    query:str = Body(...,description="问题")
):
    kb_path = os.path.join(KB_DIR,f"{kb_name}.faiss")
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database Not Found")
    vector_store = FAISS.load_local(kb_path,embedding_model,allow_dangerous_deserialization=True)

    # 知识库内还没有可检索内容时直接返回空结果，避免后续 BM25 对空文档报错
    if not vector_store.index_to_docstore_id:
        return {"results": []}

    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": SEARCH_CANDIDATE_K})

    docs = list(vector_store.docstore._dict.values())

    bm25_retriever = BM25Retriever.from_documents(
        docs,
        preprocess_func=jieba.lcut_for_search
    )
    bm25_retriever.k = SEARCH_CANDIDATE_K
    ensemble_retriever = EnsembleRetriever(
        retrievers = [bm25_retriever,faiss_retriever],
        weights=[0.5,0.5]
    )

    candidates = ensemble_retriever.invoke(query)

    # 去重：同一文本可能同时被 BM25 和 FAISS 召回
    unique_candidates = []
    seen = set()
    for doc in candidates:
        key = (doc.page_content, str(doc.metadata))
        if key not in seen:
            seen.add(key)
            unique_candidates.append(doc)

    # 用 reranker 对候选结果二次重排，只保留最相关的前 N 条
    reranked = _rerank_documents(query, unique_candidates, RERANK_TOP_N)

    contexts = {
        "results":[{"source":context.metadata.get("source",""),
                    "page_contents":context.page_content,
                    "relevance_score": score} for context, score in reranked
                    ]
    }
    return contexts
