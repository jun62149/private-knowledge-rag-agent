from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# 创建 SQLite 数据库引擎。
# echo=True 会把实际执行的 SQL 打印到控制台，方便学习时观察数据库操作。
engine = create_engine("sqlite:///db_server/data/info.db", echo=True)

# 所有模型都继承这个 Base 基类，SQLAlchemy 会把类属性映射成数据库表字段。
Base = declarative_base()


class KnowledgeBases(Base):
    """知识库表对应的模型类。"""

    __tablename__ = "knowledge_bases"  # 数据库中的表名

    id = Column(Integer, primary_key=True, autoincrement=True, comment="知识库ID")
    kb_name = Column(String(50), comment="知识库名称")
    kb_info = Column(String(200), comment="知识库简介")

    def __repr__(self):
        return f"<Knowledge_bases(id='{self.id}', kb_name='{self.kb_name}', kb_info='{self.kb_info}')>"
        


# 第一次运行时会根据模型创建表；表已经存在时不会重复创建。
Base.metadata.create_all(engine)

# sessionmaker 是会话工厂，之后用 session 来执行增删改查。
Session = sessionmaker(bind=engine)
session = Session()
