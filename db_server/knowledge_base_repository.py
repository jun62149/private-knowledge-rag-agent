from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from db_server.base import KnowledgeBases


def add_kb_to_db(session: Session, kb_name: str, kb_info: str):
    """新增一个知识库。

    如果同名知识库已经存在，就不重复添加，并返回提示信息。
    """
    try:
        # ilike 表示不区分大小写，按名称模糊匹配同名知识库
        knowledge_bases = session.query(KnowledgeBases).filter(KnowledgeBases.kb_name.ilike(kb_name)).first()
        if not knowledge_bases:
            # 不存在同名知识库时才创建新记录
            knowledge_bases = KnowledgeBases(kb_name=kb_name, kb_info=kb_info)
            session.add(knowledge_bases)
            session.commit()
            result = f"Knowledge '{kb_name}' created successfully."
        else:
            result = f"Knowledge '{kb_name}' already exists."
    except IntegrityError as e:
        session.rollback()
        result = f"IntegrityError: {e}"
    except Exception as e:
        session.rollback()
        result = f"An error occurred: {e}"

    return result


def del_kb_from_db(session: Session, kb_name: str):
    """按名称删除一个知识库。"""
    try:
        KnowledgeBases_to_delete = session.query(KnowledgeBases).filter_by(kb_name=kb_name).first()
        if KnowledgeBases_to_delete:
            session.delete(KnowledgeBases_to_delete)
            session.commit()
            result = f"Knowledge '{kb_name}' deleted successfully."
        else:
            result = f"Knowledge '{kb_name}' does not exist."
    except IntegrityError as e:
        session.rollback()
        result = f"IntegrityError: {e}"
    except Exception as e:
        session.rollback()
        result = f"An error occurred: {e}"

    return result


def list_kb_from_db(session: Session):
    """查询所有知识库，并整理成方便前端使用的字典列表。"""
    all_KnowledgeBasess = session.query(KnowledgeBases).all()
    KnowledgeBasess_list = [
        {
            "id": knowledge_bases.id,
            "kb_name": knowledge_bases.kb_name,
            "kb_info": knowledge_bases.kb_info,
        }
        for knowledge_bases in all_KnowledgeBasess
    ]
    return KnowledgeBasess_list
