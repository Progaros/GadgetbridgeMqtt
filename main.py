#!/usr/bin/env python3
"""
Gadgetbridge MQTT Step Counter Integration
Extracts sensor data from Gadgetbridge SQLite database and publishes to Home Assistant via MQTT
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import asyncio
import aiomqtt
import re


class GadgetbridgeMQTTPublisher:
    def __init__(self):
        self.setup_logging()
        self.db_path = os.getenv("GADGETBRIDGE_DB_PATH", "/data/Gadgetbridge.db")
        self.device_name = self.get_device_alias()
        self.load_config()
        self.mqtt_client = None
        self.publish_interval = int(os.getenv("PUBLISH_INTERVAL_SECONDS", "300"))
        self.sensors = [
            {
                "name": "Daily Steps",
                "unique_id": "daily_steps",
                "state_topic": f"gadgetbridge/{self.device_name}/steps/daily",
                "unit_of_measurement": "steps",
                "icon": "mdi:walk",
                "state_class": "total_increasing",
                "query": self.query_daily_steps,
            },
            {
                "name": "Weekly Steps",
                "unique_id": "weekly_steps",
                "state_topic": f"gadgetbridge/{self.device_name}/steps/weekly",
                "unit_of_measurement": "steps",
                "icon": "mdi:walk",
                "state_class": "total",
                "query": self.query_weekly_steps,
            },
            {
                "name": "Monthly Steps",
                "unique_id": "monthly_steps",
                "state_topic": f"gadgetbridge/{self.device_name}/steps/monthly",
                "unit_of_measurement": "steps",
                "icon": "mdi:walk",
                "state_class": "total",
                "query": self.query_monthly_steps,
            },
            {
                "name": "Battery Level",
                "unique_id": "battery_level",
                "state_topic": f"gadgetbridge/{self.device_name}/battery",
                "unit_of_measurement": "%",
                "icon": "mdi:battery",
                "device_class": "battery",
                "query": self.query_battery_level,
            },
            {
                "name": "Weight",
                "unique_id": "weight",
                "state_topic": f"gadgetbridge/{self.device_name}/weight",
                "unit_of_measurement": "kg",
                "icon": "mdi:scale-bathroom",
                "state_class": "measurement",
                "query": self.query_latest_weight,
            },
            {
                "name": "Latest Heart Rate",
                "unique_id": "latest_heart_rate",
                "state_topic": f"gadgetbridge/{self.device_name}/heart_rate",
                "unit_of_measurement": "bpm",
                "icon": "mdi:heart-pulse",
                "state_class": "measurement",
                "query": self.query_latest_heart_rate,
            },
            {
                "name": "Resting Heart Rate",
                "unique_id": "hr_resting",
                "state_topic": f"gadgetbridge/{self.device_name}/hr_resting",
                "unit_of_measurement": "bpm",
                "icon": "mdi:heart-pulse",
                "state_class": "measurement",
                "query": self.query_hr_resting,
            },
            {
                "name": "Max Heart Rate",
                "unique_id": "hr_max",
                "state_topic": f"gadgetbridge/{self.device_name}/hr_max",
                "unit_of_measurement": "bpm",
                "icon": "mdi:heart-pulse",
                "state_class": "measurement",
                "query": self.query_hr_max,
            },
            {
                "name": "Average Heart Rate",
                "unique_id": "hr_avg",
                "state_topic": f"gadgetbridge/{self.device_name}/hr_avg",
                "unit_of_measurement": "bpm",
                "icon": "mdi:heart-pulse",
                "state_class": "measurement",
                "query": self.query_hr_avg,
            },
            {
                "name": "Calories",
                "unique_id": "calories",
                "state_topic": f"gadgetbridge/{self.device_name}/calories",
                "unit_of_measurement": "kcal",
                "icon": "mdi:fire",
                "state_class": "total_increasing",
                "query": self.query_calories,
            },
            {
                "name": "Is Awake",
                "unique_id": "is_awake",
                "state_topic": f"gadgetbridge/{self.device_name}/is_awake",
                "icon": "mdi:power-sleep",
                "device_class": "enum",
                "query": self.query_is_awake,
            },
            {
                "name": "Total Sleep Duration",
                "unique_id": "total_sleep_duration",
                "state_topic": f"gadgetbridge/{self.device_name}/total_sleep_duration",
                "unit_of_measurement": "h",
                "icon": "mdi:sleep",
                "state_class": "measurement",
                "query": self.query_total_sleep_duration,
            },
        ]

    def setup_logging(self):
        """Setup logging configuration (console only)"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Load MQTT configuration from environment variables"""
        self.mqtt_config = {
            "broker": os.getenv("MQTT_BROKER", "localhost"),
            "port": int(os.getenv("MQTT_PORT", "1883")),
            "username": os.getenv("MQTT_USERNAME", ""),
            "password": os.getenv("MQTT_PASSWORD", ""),
        }

    async def publish_home_assistant_discovery(
        self, entity_type: str, entity_id: str, config: Dict
    ):
        """Publish Home Assistant MQTT discovery configuration asynchronously"""
        discovery_topic = (
            f"homeassistant/{entity_type}/{self.device_name}_{entity_id}/config"
        )
        try:
            await self.mqtt_client.publish(
                discovery_topic, json.dumps(config), qos=1, retain=True
            )
            self.logger.info(f"Published discovery config for {entity_id}")
        except Exception as e:
            self.logger.error(f"Failed to publish discovery config: {e}")

    async def setup_home_assistant_entities(self):
        """Setup Home Assistant entities via MQTT discovery"""
        device_info = {
            "identifiers": [self.device_name],
            "name": f"Gadgetbridge {self.device_name.replace('_', ' ').title()}",
            "model": "Fitness Tracker",
            "manufacturer": "Gadgetbridge",
        }
        for sensor in self.sensors:
            config = {
                "name": f"{self.device_name.replace('_', ' ').title()} {sensor['name']}",
                "unique_id": f"{self.device_name}_{sensor['unique_id']}",
                "state_topic": sensor["state_topic"],
                "device": device_info,
            }
            # Add optional fields if present
            for key in ["unit_of_measurement", "icon", "state_class", "device_class"]:
                if key in sensor:
                    config[key] = sensor[key]
            await self.publish_home_assistant_discovery(
                "sensor", sensor["unique_id"], config
            )

    def query_daily_steps(self, cursor) -> Any:
        today = datetime.now().date()
        today_start = int(datetime.combine(today, datetime.min.time()).timestamp())
        today_end = int(datetime.combine(today, datetime.max.time()).timestamp())
        cursor.execute(
            "SELECT SUM(STEPS) FROM XIAOMI_ACTIVITY_SAMPLE WHERE TIMESTAMP >= ? AND TIMESTAMP <= ?",
            (today_start, today_end),
        )
        return cursor.fetchone()[0] or 0

    def query_weekly_steps(self, cursor) -> Any:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_start_ts = int(
            datetime.combine(week_start, datetime.min.time()).timestamp()
        )
        cursor.execute(
            "SELECT SUM(STEPS) FROM XIAOMI_ACTIVITY_SAMPLE WHERE TIMESTAMP >= ?",
            (week_start_ts,),
        )
        return cursor.fetchone()[0] or 0

    def query_monthly_steps(self, cursor) -> Any:
        today = datetime.now().date()
        month_start = today.replace(day=1)
        month_start_ts = int(
            datetime.combine(month_start, datetime.min.time()).timestamp()
        )
        cursor.execute(
            "SELECT SUM(STEPS) FROM XIAOMI_ACTIVITY_SAMPLE WHERE TIMESTAMP >= ?",
            (month_start_ts,),
        )
        return cursor.fetchone()[0] or 0

    def query_battery_level(self, cursor) -> Any:
        cursor.execute(
            "SELECT LEVEL FROM BATTERY_LEVEL ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_latest_weight(self, cursor) -> Any:
        cursor.execute(
            "SELECT WEIGHT_KG FROM MI_SCALE_WEIGHT_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_latest_heart_rate(self, cursor) -> Any:
        cursor.execute(
            "SELECT HEART_RATE FROM XIAOMI_ACTIVITY_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_hr_resting(self, cursor) -> Any:
        cursor.execute(
            "SELECT HR_RESTING FROM XIAOMI_DAILY_SUMMARY_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_hr_max(self, cursor) -> Any:
        cursor.execute(
            "SELECT HR_MAX FROM XIAOMI_DAILY_SUMMARY_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_hr_avg(self, cursor) -> Any:
        cursor.execute(
            "SELECT HR_AVG FROM XIAOMI_DAILY_SUMMARY_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_calories(self, cursor) -> Any:
        cursor.execute(
            "SELECT CALORIES FROM XIAOMI_DAILY_SUMMARY_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def query_is_awake(self, cursor) -> Any:
        cursor.execute(
            "SELECT IS_AWAKE FROM XIAOMI_SLEEP_TIME_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        # Return as boolean or string for Home Assistant
        return not bool(row[0]) if row else None  # inverted

    def query_total_sleep_duration(self, cursor) -> Any:
        cursor.execute(
            "SELECT TOTAL_DURATION FROM XIAOMI_SLEEP_TIME_SAMPLE ORDER BY TIMESTAMP DESC LIMIT 1"
        )
        row = cursor.fetchone()
        # Convert minutes to hours, round to 2 decimals
        return round(row[0] / 60, 2) if row and row[0] is not None else None

    def get_sensor_data(self) -> Dict[str, Any]:
        """Query all sensors and return their values as a dict"""
        if not os.path.exists(self.db_path):
            self.logger.error(f"Database file not found: {self.db_path}")
            return {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            data = {}
            for sensor in self.sensors:
                try:
                    data[sensor["unique_id"]] = sensor["query"](cursor)
                except Exception as e:
                    self.logger.error(f"Error querying {sensor['unique_id']}: {e}")
                    data[sensor["unique_id"]] = None
            conn.close()
            return data
        except Exception as e:
            self.logger.error(f"Error querying database: {e}")
            return {}

    async def publish_sensor_data(self, data: Dict[str, Any]):
        """Publish all sensor data to MQTT asynchronously"""
        for sensor in self.sensors:
            value = data.get(sensor["unique_id"])
            if value is not None:
                try:
                    await self.mqtt_client.publish(
                        sensor["state_topic"], str(value), qos=1
                    )
                except Exception as e:
                    self.logger.error(f"Failed to publish {sensor['unique_id']}: {e}")
        self.logger.info(f"Published sensor data: {data}")

    async def run(self):
        """Main execution method (async)"""
        self.logger.info("Starting Gadgetbridge MQTT Publisher")
        try:
            async with aiomqtt.Client(
                hostname=self.mqtt_config["broker"],
                port=self.mqtt_config["port"],
                username=self.mqtt_config["username"] or None,
                password=self.mqtt_config["password"] or None,
            ) as client:
                self.mqtt_client = client
                await self.setup_home_assistant_entities()
                # Publish immediately on startup
                sensor_data = self.get_sensor_data()
                await self.publish_sensor_data(sensor_data)
                self.logger.info(
                    f"Sleeping for {self.publish_interval} seconds before next publish..."
                )
                while True:
                    await asyncio.sleep(self.publish_interval)
                    sensor_data = self.get_sensor_data()
                    await self.publish_sensor_data(sensor_data)
                    self.logger.info(
                        f"Sleeping for {self.publish_interval} seconds before next publish..."
                    )
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")

    def get_device_alias(self) -> str:
        """Fetch ALIAS from DEVICE table for device_name where NAME contains 'band' or 'watch' (case-insensitive)"""
        if not os.path.exists(self.db_path):
            self.logger.error(f"Database file not found: {self.db_path}")
            return "fitness_tracker"
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ALIAS FROM DEVICE
                WHERE LOWER(NAME) LIKE '%band%' OR LOWER(NAME) LIKE '%watch%'
                LIMIT 1
            """
            )
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                # Sanitize alias for MQTT topics
                return re.sub(r"\W+", "_", row[0]).lower()
            else:
                return "fitness_tracker"
        except Exception as e:
            self.logger.error(f"Error fetching device alias: {e}")
            return "fitness_tracker"


# --- Main Entry Point ---
if __name__ == "__main__":
    publisher = GadgetbridgeMQTTPublisher()
    asyncio.run(publisher.run())
