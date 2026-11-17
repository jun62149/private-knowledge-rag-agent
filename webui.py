import os
import uuid
import gradio as gr
from webui.chat_with_agent_api import chat_with_agent
from webui.Knowledgebase_api import (
    create_kb,
    delete_kb,
    list_kbs,
    upload_docs,
    list_kb_files,
    delete_kb_file,
)



def on_app_load():
    session_id = str(uuid.uuid4())
    return session_id

# 使用 Blocks 创建页面，fill_width/fill_height 让页面自动填满可用空间
with gr.Blocks(fill_width=True, fill_height=True) as demo:
    session_state = gr.State(value=on_app_load)
    print("session_state==================",session_state)
    # 第一个标签页：聊天机器人
    with gr.Tab(" 🤖 聊天机器人"):
        gr.Markdown("## 🤖 聊天机器人")

        with gr.Row():
            # 左侧是聊天参数面板
            with gr.Column(scale=1, variant="panel") as sidebar_left:
                sys_prompt = gr.Textbox(label="系统提示词", value="You are a helpful assistant")
                history_len = gr.Slider(minimum=1, maximum=10, value=1, label="保留历史消息的数量")
                temperature = gr.Slider(minimum=0.01, maximum=2.0, value=0.5, step=0.01, label="temperature")
                top_p = gr.Slider(minimum=0.01, maximum=1.0, value=0.5, step=0.01, label="top_p")
                max_tokens = gr.Slider(minimum=64, maximum=512, value=512, step=8, label="max_tokens")
                stream = gr.Checkbox(label="stream", value=True)

            # 右侧是聊天区域
            with gr.Column(scale=10) as main:
                gr.Markdown(
                    "> 附件直接解析：支持 `.txt` `.md` `.py` `.csv` `.json` `.pdf` `.docx`；"
                    "图片 / 音视频 / 压缩包等二进制格式请改用「知识库管理」上传。\n"
                    ">\n"
                    "> 流式模式下只显示最终答案，ReAct 的推理与工具调用过程打印在后端控制台。"
                )
                chatbot = gr.Chatbot(height=600)
                gr.ChatInterface(
                    fn=chat_with_agent,
                    multimodal=True,
                    chatbot=chatbot,
                    additional_inputs=[
                          sys_prompt,
                          history_len,
                          temperature,
                          top_p,
                          max_tokens,
                          stream,
                          session_state,
                      ],
                      )

    # 第二个标签页：知识库管理（按图片布局修改）
    with gr.Tab("📚 知识库管理"):
        gr.Markdown("## 📚 知识库管理")

        # 第一行：知识库名称
        with gr.Row():
            kb_name = gr.Textbox(label="知识库名称", placeholder="请输入知识库名称")

        # 第二行：知识库描述
        with gr.Row():
            kb_info = gr.Textbox(label="知识库描述", placeholder="请输入知识库描述")

        # 第三行：隐藏的消息框
        with gr.Row():
            message_box = gr.Markdown(visible=False)

        # 第四行：创建和删除按钮（并排）
        with gr.Row():
            create_button = gr.Button("创建知识库")
            delete_button = gr.Button("删除知识库")

        # 第五行：选择知识库下拉框
        # filterable=False：去掉下拉框上的搜索输入框，点击直接弹出选项列表
        with gr.Row():
            kb_name_upload = gr.Dropdown(
                label="选择知识库",
                choices=[],
                filterable=False,
                allow_custom_value=False,
            )

        # 第六行：选中知识库后自动显示该库内已有文件
        with gr.Row():
            kb_file_selector = gr.Dropdown(
                label="知识库内已有文件",
                choices=[],
                filterable=False,
                allow_custom_value=False,
            )

        # 第七行：删除所选文件
        with gr.Row():
            delete_file_button = gr.Button("删除所选文件")

        # 第八行：删除文件结果消息（隐藏）
        with gr.Row():
            delete_file_message_box = gr.Markdown(visible=False)

        # 上传区域：选择文件
        with gr.Row():
            file_upload = gr.Files(label="选择文件")

        # 分块参数（并排）
        with gr.Row():
            chunk_size = gr.Number(label="知识库中单段文本最大长度(chunk_size)", value=128, minimum=1, maximum=800)
            chunk_overlap = gr.Number(label="知识库中相邻文本重叠长度(chunk_overlap)", value=20, minimum=0, maximum=400)

        # 上传按钮
        with gr.Row():
            upload_button = gr.Button("上传并向量化")

        # 上传结果消息（隐藏）
        with gr.Row():
            upload_message_box = gr.Markdown(visible=False)

        # ---------- 辅助函数 ----------
        def scan_local_kbs():
            """扫描 knowledgebases 目录下的 .faiss 文件，作为下拉框选项的兜底。

            即使后端接口暂时不可用或数据库没有记录，只要 .faiss 落盘了，
            下拉框也能正常显示已创建的知识库。
            """
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                kb_dir = os.path.join(base, "knowledgebases")
                if not os.path.isdir(kb_dir):
                    return []
                return sorted(
                    name[: -len(".faiss")]
                    for name in os.listdir(kb_dir)
                    if name.endswith(".faiss")
                )
            except Exception as e:
                print(f"扫描本地知识库失败: {e}")
                return []

        # 更新下拉框
        def update_dropdown():
            """刷新下拉框选项。

            先取后端返回的列表（Gradio 6 中 gr.update 是带 __type__ 的 dict），
            再用本地 knowledgebases 目录里的 .faiss 文件兜底合并，
            保证已创建的知识库一定能显示。
            """
            try:
                result = list_kbs()
                choices = []
                if isinstance(result, dict) and result.get("__type__") == "update":
                    choices = list(result.get("choices") or [])
                elif isinstance(result, dict):
                    raw = result.get("knowledgebases", [])
                    for kb in raw:
                        if isinstance(kb, str):
                            choices.append(kb)
                        elif isinstance(kb, dict):
                            name = kb.get("kb_name") or kb.get("name")
                            if name:
                                choices.append(name)
                elif isinstance(result, (list, tuple)):
                    choices = [str(c) for c in result]

                # 兜底：合并本地已存在的 .faiss 知识库
                for name in scan_local_kbs():
                    if name not in choices:
                        choices.append(name)
                return gr.update(choices=choices)
            except Exception as e:
                print(f"更新下拉框失败: {e}")
                return gr.update(choices=scan_local_kbs())

        # ---------- 事件绑定 ----------
        # 创建知识库
        create_button.click(
            fn=create_kb,
            inputs=[kb_name, kb_info],
            outputs=[message_box, kb_name, kb_info]
        ).then(
            fn=update_dropdown,
            outputs=kb_name_upload
        )

        # 删除知识库
        delete_button.click(
            fn=delete_kb,
            inputs=[kb_name_upload],
            outputs=[message_box, kb_name]
        ).then(
            fn=update_dropdown,
            outputs=kb_name_upload
        ).then(
            fn=lambda: gr.update(choices=[], value=None),
            outputs=kb_file_selector,
        )

        # 上传文件到知识库（直接读取“选择文件”框，避免文件被清掉导致上传失败）
        upload_button.click(
            fn=upload_docs,
            inputs=[kb_name_upload, file_upload, chunk_size, chunk_overlap],
            outputs=[upload_message_box, file_upload]
        ).then(
            fn=list_kb_files,
            inputs=kb_name_upload,
            outputs=kb_file_selector,
        )

        # 切换知识库时刷新文件下拉框
        kb_name_upload.change(
            fn=list_kb_files,
            inputs=kb_name_upload,
            outputs=kb_file_selector,
        )

        # 删除所选文件
        delete_file_button.click(
            fn=delete_kb_file,
            inputs=[kb_name_upload, kb_file_selector],
            outputs=[delete_file_message_box],
        ).then(
            fn=list_kb_files,
            inputs=kb_name_upload,
            outputs=kb_file_selector,
        )

        # 页面加载时自动刷新下拉框
        demo.load(fn=update_dropdown, outputs=kb_name_upload)

demo.launch()
