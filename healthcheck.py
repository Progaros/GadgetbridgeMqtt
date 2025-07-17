#!/usr/bin/env python3
"""
Health check script for Gadgetbridge MQTT integration
"""

import os
import sqlite3
import socket


def check_database():
    """Check if Gadgetbridge database is accessible"""
    db_path = os.getenv("GADGETBRIDGE_DB_PATH", "/data/Gadgetbridge.db")

    if not os.path.exists(db_path):
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='XIAOMI_ACTIVITY_SAMPLE'"
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


def check_mqtt_connection():
    """Check MQTT broker TCP connectivity (no paho)"""
    host = os.getenv("MQTT_BROKER", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except Exception:
        return False


def main():
    db_ok = check_database()
    mqtt_ok = check_mqtt_connection()
    if db_ok and mqtt_ok:
        print("Health check passed")
        exit(0)
    else:
        print(f"Health check failed - DB: {db_ok}, MQTT: {mqtt_ok}")
        exit(1)


if __name__ == "__main__":
    main()
