from datetime import datetime
from typing import Optional, List, Union, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel
from sqlalchemy import Column, Float, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import BaseOrm, BaseSchema

if TYPE_CHECKING:
    from app.models.measurement_file import MeasurementFileOrm


class MeasurementInfoOrm(BaseOrm):
    """
    Model representing measurement information and configuration
    """
    __tablename__ = "measurement_info"

    date_time = Column(DateTime(timezone=True), nullable=False)
    rgb_camera = Column(Boolean, default=False, nullable=False)
    multispectral_camera = Column(Boolean, default=False, nullable=False)
    number_of_sensors = Column(Integer, nullable=False)
    length_of_ae = Column(Float, nullable=False)
    scheduled = Column(Boolean, default=False, nullable=False)
    
    # Relationship to measurement files
    files: Mapped[List["MeasurementFileOrm"]] = relationship(lazy="selectin")


class MeasurementConfigOrm(BaseOrm):
    """
    Model representing measurement configuration stored in the database
    """
    __tablename__ = "measurement_config"

    measurement_frequency = Column(Integer, nullable=False, default=60)
    first_measurement = Column(DateTime(timezone=True), nullable=False)
    rgb_camera = Column(Boolean, default=False, nullable=False)
    multispectral_camera = Column(Boolean, default=False, nullable=False)
    number_of_sensors = Column(Integer, nullable=False, default=1)
    length_of_ae = Column(Float, nullable=False, default=10)


class MeasurementConfigSchema(BaseSchema):
    """
    Schema for measurement configuration
    """
    __orm__ = MeasurementConfigOrm

    measurement_frequency: int
    first_measurement: datetime
    rgb_camera: bool = False
    multispectral_camera: bool = False
    number_of_sensors: int = 0
    length_of_ae: float


class MeasurementConfigCreateSchema(BaseModel):
    """
    Schema for creating a new measurement configuration
    """
    rgb_camera: bool
    multispectral_camera: bool
    number_of_sensors: int
    length_of_ae: float


class MeasurementInfoSchema(BaseSchema):
    """
    Schema for measurement information
    """
    __orm__ = MeasurementInfoOrm

    date_time: datetime
    rgb_camera: bool = False
    multispectral_camera: bool = False
    number_of_sensors: int
    length_of_ae: float
    scheduled: bool = False
    files: List[Any] = []


class MeasurementLatestSchema(BaseSchema):
    """
    Schema for latest measurement response
    """
    last_backup: Optional[datetime]
    last_measurement: Optional[datetime]
    planned_measurement: Optional[datetime]
    latest_measurement: List[MeasurementInfoSchema]


class MeasurementHistorySchema(BaseSchema):
    """
    Schema for measurement history
    """
    measurements: List[MeasurementInfoSchema]


