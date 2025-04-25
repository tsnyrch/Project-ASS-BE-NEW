from datetime import datetime
from typing import Optional, List, Union, Dict, Any
from sqlalchemy import Column, Float, Boolean, Integer, DateTime

from app.models.base import BaseOrm, BaseSchema


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


class MeasurementConfigSchema(BaseSchema):
    """
    Schema for measurement configuration
    """
    measurement_frequency: int
    first_measurement: datetime
    rgb_camera: bool = False
    multispectral_camera: bool = False
    number_of_sensors: int = 0
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