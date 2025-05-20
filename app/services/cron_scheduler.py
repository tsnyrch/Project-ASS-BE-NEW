import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, TYPE_CHECKING
import sys

if TYPE_CHECKING:
    from app.services.measurement_service import MeasurementService

    # from app.services.measurement_service_test import MeasurementServiceTest
    from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class CronScheduler:
    """
    Singleton class for scheduling and managing tasks for measurements

    This is a simplified cron-like scheduler that uses asyncio tasks
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of CronScheduler
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        Private constructor to prevent direct instantiation
        """
        self.task = None
        self.minutes_interval = 0
        self.next_scheduled_date = None
        self.job_callback = None
        self.config_id = None  # Track the current config ID to detect changes
        self.measurement_service = None  # type: Optional["MeasurementService"]
        self.settings_service = None  # type: Optional["SettingsService"]

    def register_job(self, job_callback: Callable):
        """
        Register a job function that will be called when the schedule triggers
        """
        print(
            f"[CronScheduler] Registering job callback: {job_callback.__name__ if hasattr(job_callback, '__name__') else str(job_callback)}"
        )
        self.job_callback = job_callback

    async def _job_wrapper(self):
        """
        Wrapper for the actual job function
        """
        while True:
            try:
                now = datetime.now(timezone.utc)
                print(
                    f"[CronScheduler] Running scheduled measurement at: {now.isoformat()}, interval: {self.minutes_interval} minutes"
                )
                logger.info(
                    f"Running scheduled measurement at: {now.isoformat()}, interval: {self.minutes_interval} minutes"
                )

                # Update the next scheduled date
                self.next_scheduled_date = now + timedelta(
                    minutes=self.minutes_interval
                )

                # Initialize services if they haven't been initialized yet
                if self.measurement_service is None:
                    # Import here to avoid circular imports
                    from app.services.measurement_service import MeasurementService

                    self.measurement_service = MeasurementService()
                    print("[CronScheduler] Initializing MeasurementServiceTest")
                    # from app.services.measurement_service_test import MeasurementServiceTest
                    # self.measurement_service = MeasurementServiceTest()

                if self.settings_service is None:
                    # Import here to avoid circular imports
                    print("[CronScheduler] Initializing SettingsService")
                    from app.services.settings_service import SettingsService

                    self.settings_service = SettingsService()

                # Get current measurement configuration
                print("[CronScheduler] Fetching current measurement configuration")
                config = await self.settings_service.get_measurement_config()
                print(f"[CronScheduler] Configuration fetched: {config}")

                # Start the measurement based on the configuration
                print(f"[CronScheduler] Starting measurement with config")
                measurement_result = (
                    await self.measurement_service.start_measurement_by_config(config)
                )

                if measurement_result:
                    print(
                        f"[CronScheduler] Scheduled measurement completed successfully: {measurement_result.id}"
                    )
                    logger.info(
                        f"Scheduled measurement completed successfully: {measurement_result.id}"
                    )
                else:
                    print("[CronScheduler] Scheduled measurement failed")
                    logger.error("Scheduled measurement failed")

                # Call the registered callback (legacy support)
                if self.job_callback:
                    print("[CronScheduler] Calling registered job callback")
                    await self.job_callback(scheduled=True)

                # Sleep until next run
                print(
                    f"[CronScheduler] Next scheduled measurement at: {self.next_scheduled_date.isoformat()}"
                )
                logger.info(
                    f"Next scheduled measurement at: {self.next_scheduled_date.isoformat()}"
                )
                print(f"[CronScheduler] Sleeping for {self.minutes_interval} minutes")
                await asyncio.sleep(self.minutes_interval * 60)
            except Exception as e:
                print(
                    f"[CronScheduler] ERROR in scheduled job: {str(e)}", file=sys.stderr
                )
                print(f"[CronScheduler] Exception type: {type(e)}", file=sys.stderr)
                import traceback

                print(
                    f"[CronScheduler] Traceback: {traceback.format_exc()}",
                    file=sys.stderr,
                )
                logger.error(f"Error in scheduled job: {str(e)}")
                # If there's an error, still try to continue after waiting
                print("[CronScheduler] Waiting 60 seconds before retry")
                await asyncio.sleep(60)

    def set_new_schedule(
        self,
        minutes_interval: int,
        start_time: Optional[datetime] = None,
        config_id: Optional[int] = None,
    ):
        """
        Set a new schedule for measurements

        Args:
            minutes_interval: The interval between measurements in minutes
            start_time: The time to start the first measurement (defaults to now)
            config_id: Optional ID of the configuration being applied
        """
        # If config_id is provided and matches current config, don't reschedule
        if config_id is not None and config_id == self.config_id:
            print(
                f"[CronScheduler] Configuration ID {config_id} already active, not rescheduling"
            )
            logger.info(
                f"Configuration ID {config_id} already active, not rescheduling"
            )
            return

        # Update config_id if provided
        if config_id is not None:
            self.config_id = config_id

        # Cancel existing task if there is one
        if self.task and not self.task.done():
            print("[CronScheduler] Canceling existing measurement schedule")
            logger.info("Canceling existing measurement schedule")
            self.task.cancel()
            self.task = None

        if minutes_interval <= 0:
            print(
                f"[CronScheduler] No automatic measurement scheduled - invalid interval: {minutes_interval}"
            )
            logger.info("No automatic measurement scheduled - invalid interval")
            self.next_scheduled_date = None
            return

        self.minutes_interval = minutes_interval

        # Use UTC now
        now = datetime.now(timezone.utc)

        # If no start time is specified, use now + interval
        if start_time is None:
            start_time = now + timedelta(minutes=minutes_interval)
        else:
            # Ensure start_time is timezone-aware
            if (
                start_time.tzinfo is None
                or start_time.tzinfo.utcoffset(start_time) is None
            ):
                start_time = start_time.replace(tzinfo=timezone.utc)

        # If start time is in the past, calculate the next occurrence
        if start_time < now:
            # Calculate how many intervals have passed since the start time
            time_diff = (now - start_time).total_seconds() / 60  # in minutes
            intervals_passed = int(time_diff / minutes_interval) + 1
            # Calculate the next scheduled time
            start_time = start_time + timedelta(
                minutes=intervals_passed * minutes_interval
            )
            print(
                f"[CronScheduler] Original start time was in the past. Adjusted to next occurrence: {start_time.isoformat()}"
            )
            logger.info(
                f"Original start time was in the past. Adjusted to next occurrence: {start_time.isoformat()}"
            )

        self.next_scheduled_date = start_time

        # Calculate delay until start time
        delay = (start_time - now).total_seconds()
        delay = max(0, delay)  # Ensure delay is not negative

        async def schedule_task():
            # Wait until the start time
            if delay > 0:
                print(
                    f"[CronScheduler] Waiting {delay} seconds until first measurement at {start_time.isoformat()}"
                )
                logger.info(
                    f"Waiting {delay} seconds until first measurement at {start_time.isoformat()}"
                )
                await asyncio.sleep(delay)

            # Start the recurring job
            await self._job_wrapper()

        # Create and start the task
        print(
            f"[CronScheduler] Scheduled measurements every {minutes_interval} minutes, starting at {start_time.isoformat()}"
        )
        logger.info(
            f"Scheduled measurements every {minutes_interval} minutes, starting at {start_time.isoformat()}"
        )
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(schedule_task())
        print(f"[CronScheduler] Task created: {self.task}")
