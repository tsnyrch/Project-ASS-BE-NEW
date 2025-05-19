import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

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

    def register_job(self, job_callback: Callable):
        """
        Register a job function that will be called when the schedule triggers
        """
        self.job_callback = job_callback

    async def _job_wrapper(self):
        """
        Wrapper for the actual job function
        """
        while True:
            try:
                now = datetime.now(timezone.utc)
                logger.info(
                    f"Running scheduled measurement at: {now.isoformat()}, interval: {self.minutes_interval} minutes"
                )

                # Update the next scheduled date
                self.next_scheduled_date = now + timedelta(
                    minutes=self.minutes_interval
                )

                # Call the registered callback
                if self.job_callback:
                    await self.job_callback(scheduled=True)

                # Sleep until next run
                logger.info(
                    f"Next scheduled measurement at: {self.next_scheduled_date.isoformat()}"
                )
                await asyncio.sleep(self.minutes_interval * 60)
            except Exception as e:
                logger.error(f"Error in scheduled job: {str(e)}")
                # If there's an error, still try to continue after waiting
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
            logger.info(
                f"Configuration ID {config_id} already active, not rescheduling"
            )
            return

        # Update config_id if provided
        if config_id is not None:
            self.config_id = config_id

        # Cancel existing task if there is one
        if self.task and not self.task.done():
            logger.info("Canceling existing measurement schedule")
            self.task.cancel()
            self.task = None

        if minutes_interval <= 0:
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
                logger.info(
                    f"Waiting {delay} seconds until first measurement at {start_time.isoformat()}"
                )
                await asyncio.sleep(delay)

            # Start the recurring job
            await self._job_wrapper()

        # Create and start the task
        logger.info(
            f"Scheduled measurements every {minutes_interval} minutes, starting at {start_time.isoformat()}"
        )
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(schedule_task())
