"""
数据库工具 - 使用SQLAlchemy + SQLite持久化存储
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine, Column, String, Text, Integer, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

DB_PATH = "./data/workflow_history.db"


class WorkflowRecord(Base):
    """AI生成的工作流记录"""
    __tablename__ = "workflow_records"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    requirement = Column(Text, nullable=False)
    workflow_name = Column(String(256), default="")
    workflow_description = Column(Text, default="")
    workflow_json = Column(Text, nullable=False)
    task_count = Column(Integer, default=0)
    services_used = Column(String(512), default="")
    status = Column(String(32), default="generated")
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "requirement": self.requirement,
            "workflow_name": self.workflow_name,
            "workflow_description": self.workflow_description,
            "task_count": self.task_count,
            "services_used": self.services_used,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["workflow_json"] = json.loads(self.workflow_json) if self.workflow_json else {}
        return d


# 全局引擎和会话工厂
_engine = None
_SessionLocal = None


def init_db():
    """初始化数据库，创建表"""
    global _engine, _SessionLocal
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)
    print(f"数据库初始化完成（SQLite: {DB_PATH}）")


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def save_workflow_record(requirement: str, workflow_dict: Dict[str, Any]) -> str:
    """保存AI生成的工作流记录，返回记录ID"""
    tasks = workflow_dict.get("tasks", [])
    services = sorted(set(t.get("service", "") for t in tasks if t.get("service")))

    record = WorkflowRecord(
        requirement=requirement,
        workflow_name=workflow_dict.get("name", ""),
        workflow_description=workflow_dict.get("description", ""),
        workflow_json=json.dumps(workflow_dict, ensure_ascii=False),
        task_count=len(tasks),
        services_used=", ".join(services),
    )

    with get_session() as session:
        session.add(record)
        session.commit()
        return record.id


def list_workflow_records(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """获取工作流记录列表（不含完整JSON）"""
    with get_session() as session:
        records = (
            session.query(WorkflowRecord)
            .order_by(WorkflowRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = session.query(WorkflowRecord).count()
        return {
            "records": [r.to_dict() for r in records],
            "total": total,
        }


def get_workflow_record(record_id: str) -> Optional[Dict[str, Any]]:
    """获取单条工作流记录（含完整JSON）"""
    with get_session() as session:
        record = session.get(WorkflowRecord, record_id)
        return record.to_detail_dict() if record else None


def delete_workflow_record(record_id: str) -> bool:
    """删除工作流记录"""
    with get_session() as session:
        record = session.get(WorkflowRecord, record_id)
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
