import asyncio
import logging
from datetime import UTC
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor


class BackgroundTaskManagerService:
    """Manager for background tasks."""

    def __init__(self):
        self.scheduler = None
        self.job_stores = {"default": MemoryJobStore()}
        self.job_defaults = {}

        # logging config
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the background task manager."""
        if not self.scheduler:
            self.scheduler = AsyncIOScheduler(
                jobstores=self.job_stores,
                timezone=UTC,
            )
            self.scheduler.start()

        self.logger.info("Starting background tasks...")

        # self.scheduler.add_job(
        #     self.job_import_wdac_events,
        #     trigger=CronTrigger(hour=0),
        #     id="job_import_wdac_events ",
        #     name="Import WDAC events daily at midnight",
        #     replace_existing=True,
        # )

        self.logger.info(
            "Background task manager started with update checker scheduled"
        )

    async def stop(self):
        """Stop the background task manager."""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        self.logger.info("Background task manager stopped")

    ### Jobs ###
    async def job_import_wdac_events(self):
        """Import WDAC events from wdac_events.json and store them in the WdacEvents database table."""
        import json
        from datetime import datetime
        from app.graph.entra_id.entraid_api import get_user
        from app.db_models.tables.table_wdacevents import create_wdac_event

        try:
            self.logger.info("Starting scheduled WDAC event import...")

            # Wipe existing data and re-create tables
            self.db_service.dropAllTables()
            self.db_service.create_tables()

            with open("test_data/wdac_events.json", "r") as f:
                data = json.load(f)

            for result in data["results"]:
                user = await get_user(result["InitiatingProcessAccountUpn"])

                event_data = {
                    "date_time": datetime.fromisoformat(
                        result["Timestamp"].replace("Z", "+00:00")
                    ),
                    "folder_path": result["FolderPath"],
                    "file_name": result["FileName"],
                    "file_path": result["FolderPath"] + result["FileName"],
                    "initiating_process_version_info_internal_fileName": result[
                        "InitiatingProcessVersionInfoInternalFileName"
                    ],
                    "action_type": result["ActionType"],
                    "device_name": result["DeviceName"],
                    "sha_256": result["SHA256"],
                    "initiating_process_account_upn": result[
                        "InitiatingProcessAccountUpn"
                    ],
                    "job_title": user.job_title,
                }

                await create_wdac_event(event_data, self.db_service.engine)

                self.logger.info("WDAC event import completed")
        except Exception as e:
            self.logger.error(f"WDAC event import failed: {e}")
