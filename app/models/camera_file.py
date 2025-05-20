import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class CameraFile(Base):
    """Model for tracking files captured by cameras and uploaded to storage."""

    __tablename__ = "camera_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(128), nullable=True)

    # File metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    bit_depth = Column(Integer, nullable=True)

    # Camera metadata
    camera_id = Column(String(255), nullable=True)
    camera_model = Column(String(255), nullable=True)
    camera_vendor = Column(String(255), nullable=True)

    # Capture settings
    pixel_format = Column(String(32), nullable=True)
    exposure_time = Column(Float, nullable=True)
    gain = Column(Float, nullable=True)
    wavelength = Column(Integer, nullable=True)  # For multispectral images

    # For multispectral sets, link related files
    parent_id = Column(String(36), ForeignKey("camera_files.id"), nullable=True)

    # File status
    is_uploaded = Column(Boolean, default=False)
    cloud_url = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    children = relationship(
        "CameraFile", backref="parent", remote_side=[id], cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CameraFile {self.id}: {self.file_name}>"
