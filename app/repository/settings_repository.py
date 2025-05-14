import json
import os
from pathlib import Path
from typing import Dict, Any

from app.models.measurement import MeasurementConfigSchema


class SettingsRepository:
    """
    Repository for application settings operations
    """

    def __init__(self):
        # Create data directory for settings if it doesn't exist
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

        # Define path for measurement config
        self.measurement_config_path = self.data_dir / "measurement_config.json"

        # Ensure measurement config exists
        if not self.measurement_config_path.exists():
            self._create_default_measurement_config()

    def _create_default_measurement_config(self) -> None:
        """
        Create a default measurement config file if it doesn't exist
        """
        default_config = {
            "measurement_frequency": 60,  # 60 minutes default
            "first_measurement": "2023-04-26T08:00:00Z",
            "rgb_camera": True,
            "multispectral_camera": False,
            "number_of_sensors": 1,
            "length_of_ae": 10  # 10 minutes default
        }

        with open(self.measurement_config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

    async def get_measurement_config(self) -> MeasurementConfigSchema:
        """
        Get the current measurement configuration
        """
        with open(self.measurement_config_path, 'r') as f:
            config_data = json.load(f)

        return MeasurementConfigSchema(**config_data)

    async def update_measurement_config(self, config: MeasurementConfigSchema) -> MeasurementConfigSchema:
        """
        Update the measurement configuration
        """
        with open(self.measurement_config_path, 'w') as f:
            f.write(config.json(indent=2))  # Pydantic handles datetime properly
        return config
