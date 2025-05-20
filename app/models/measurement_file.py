from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import TYPE_CHECKING

from app.models.base import BaseOrm, BaseSchema

if TYPE_CHECKING:
    from app.models.measurement import MeasurementInfoOrm


class MeasurementFileOrm(BaseOrm):
    """
    Model representing measurement files stored in Google Drive
    """
    __tablename__ = "measurement_files"

    name = Column(String, nullable=False)
    google_drive_file_id = Column(String, nullable=False)
    measurement_id = Column(Integer, ForeignKey("measurement_info.id"), nullable=False)
    
    # Relationship to the measurement - Using modern Mapped pattern
    measurement: Mapped["MeasurementInfoOrm"] = relationship(back_populates="files")


class MeasurementFileSchema(BaseSchema):
    """
    Schema for measurement files
    """
    __orm__ = MeasurementFileOrm

    name: str
    google_drive_file_id: str
    measurement_id: int