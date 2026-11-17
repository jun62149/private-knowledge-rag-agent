import os
import requests
import gradio as gr


base_url = "http://127.0.0.1:6605"


def create_kb(kb_name, kb_info):
    """调用后端接口新增知识库，并返回更新后的界面状态。"""
    url = base_url + "/knowledgebase/create_kb"
    print("kb_name==============",kb_name)
    print("kb_info==============",kb_info)
    data = {
        "kb_name": kb_name,
        "kb_info": kb_info,
    }

    try:
        response = requests.post(url, json=data)
        print("========================== add knowledge response:", response)
        print("原始响应内容:", response.text)

        if response.status_code == 200:
            # 添加成功后清空输入框，并显示提示信息
            return (
                gr.update(value="知识库创建成功！", visible=True),gr.update(value=""),gr.update(value=""),
            )
        else:
            return (
                gr.update(value=f"知识库创建失败：{response.json().get('detail', '')}", visible=True),gr.update(value=""),gr.update(value=""),
            )
    except Exception as e:
        return (
            gr.update(value=f"请求失败：{e}", visible=True),gr.update(value=""),gr.update(value=""),
        )


def delete_kb(kb_name):
    """调用后端接口删除指定名称的知识库。"""
    url = base_url + "/knowledgebase/delete_kb"

    try:
        response = requests.delete(url, params={"kb_name": kb_name})
        if response.status_code == 200:
            return gr.update(value="知识库删除成功！", visible=True), gr.update(value="")
        else:
            return (
                gr.update(value=f"删除失败：{response.json().get('detail', '')}", visible=True),gr.update(value=""),
            )
    except Exception as e:
        return gr.update(value=f"请求失败：{e}", visible=True), gr.update(value="")


def list_kbs():
    lsit_kbs_url = base_url + "/knowledgebase/list_kbs"
    try:
        response = requests.get(lsit_kbs_url)
        if response.status_code == 200:
            kb_list = response.json()
            return gr.update(choices=[kb['kb_name'] for kb in kb_list["knowledgebases"]])
        else:
            return gr.update(choices=[])
    except Exception as e:
        print("查询知识库列表失败:", e)
        return gr.update(choices=[])


def list_kb_files(kb_name):
    """按知识库列出其中已上传的所有文件。"""
    if not kb_name:
        return gr.update(choices=[], value=None)

    list_files_url = base_url + "/knowledgebase/list_files"
    try:
        response = requests.get(list_files_url, params={"kb_name": kb_name})
        if response.status_code == 200:
            return gr.update(choices=response.json().get("files", []), value=None)
        print("列出知识库文件失败:", response.status_code, response.text)
        return gr.update(choices=[], value=None)
    except Exception as e:
        print("列出知识库文件失败:", e)
        return gr.update(choices=[], value=None)


def delete_kb_file(kb_name, file_name):
    """调用后端接口删除知识库下的单个文件。"""
    delete_file_url = base_url + "/knowledgebase/delete_file"

    if not kb_name:
        return gr.update(value="请先选择知识库", visible=True)
    if not file_name:
        return gr.update(value="请先选择要删除的文件", visible=True)

    try:
        response = requests.delete(
            delete_file_url,
            params={"kb_name": kb_name, "file_name": file_name},
        )
        if response.status_code == 200:
            data = response.json()
            message = data.get("message", "文件删除成功！")
            removed_chunks = data.get("removed_chunks", 0)
            return gr.update(
                value=f"{message}（已同步清理 {removed_chunks} 条向量）",
                visible=True,
            )
        else:
            detail = response.json().get("detail", "") if response.content else ""
            return gr.update(
                value=f"文件删除失败：{detail or response.text}",
                visible=True,
            )
    except Exception as e:
        return gr.update(value=f"请求失败：{e}", visible=True)


selected_files = []
def update(file):
    if file:
        for f in file:
            if f not in selected_files:
                selected_files.append(f)
    return gr.update(value= selected_files, visible=True),gr.update(value = [])

def upload_docs(kb_name_upload, file_upload, chunk_size, chunk_overlap):
    """上传文件到知识库。

    返回两个界面更新：上传结果消息、选择文件框（成功后清空）。
    """
    upload_docs_url = base_url + "/knowledgebase/upload_docs"

    if not file_upload:
        return (
            gr.update(value="请先选择要上传的文件", visible=True),
            gr.update(value=None),
        )

    # 兼容 Gradio 返回的两种格式：文件路径字符串 / FileData 字典
    file_paths = []
    for item in file_upload:
        if isinstance(item, str):
            file_paths.append(item)
        elif isinstance(item, dict):
            path = item.get("path") or item.get("data")
            if path:
                file_paths.append(path)
    file_names = [os.path.basename(p) for p in file_paths]

    files = []
    for file_path in file_paths:
        try:
            if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                files.append(("files", (open(file_path, "rb"))))
        except Exception as e:
            print(f"跳过文件 {file_path}: {e}")

    if not files:
        return (
            gr.update(value="上传所有文件，全部内容为空或文件不存在", visible=True),
            gr.update(value=None),
        )

    data = {
        "kb_name": kb_name_upload,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }

    try:
        response = requests.post(upload_docs_url, files=files, data=data)
        if response.status_code == 200:
            return (
                gr.update(value=f"文件上传成功：{'，'.join(file_names)}", visible=True),
                gr.update(value=None),
            )
        else:
            return (
                gr.update(
                    value=f"文件上传失败，状态码：{response.status_code}。错误信息: {response.json().get('detail', '')}",
                    visible=True,
                ),
                gr.update(value=None),
            )
    except Exception as e:
        return (
            gr.update(value=f"请求失败: {e}", visible=True),
            gr.update(value=None),
        )
