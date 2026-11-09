from sqlalchemy import CheckConstraint, Column, Integer, SmallInteger, String
from sqlalchemy.orm import relationship

from database import Base


class ProcessingStage(Base):
    __tablename__ = "processing_stages"
    __table_args__ = (
        CheckConstraint("stage_order > 0", name="ck_processing_stages_order_positive"),
    )

    stage_id = Column(SmallInteger().with_variant(Integer, "sqlite"), primary_key=True)
    stage_name = Column(String(100), nullable=False, unique=True)
    stage_order = Column(SmallInteger, nullable=False, unique=True)
    history_records = relationship("BatchHistory", back_populates="stage")
    value_calculations = relationship("ValueCalculation", back_populates="stage")
    scenarios = relationship("Scenario", back_populates="assumed_stage")
    batches = relationship("MineralBatch", back_populates="stage")
