import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings
class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get("SESSION_SECRET", "smart-bus-tracking-secret-key")
    DEBUG = True

    # PostgreSQL database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost/bus_tracking")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # InfluxDB configuration
    INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
    INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "bus_tracking")
    INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "telemetry")

    # MQTT Configuration
    MQTT_BROKER = os.environ.get("MQTT_BROKER", "127.0.0.1")  # Connect to local broker
    MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
    MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "buses/+/telemetry")
    MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "smart_bus_server")
    MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")

    # Firebase configuration for push notifications
    FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "")
    FCM_API_KEY = os.environ.get("FCM_API_KEY", "")

    # Google Maps API configuration
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    # Map settings
    DEFAULT_MAP_CENTER_LAT = float(os.environ.get("DEFAULT_MAP_CENTER_LAT", "20.5937"))  # Default India center
    DEFAULT_MAP_CENTER_LON = float(os.environ.get("DEFAULT_MAP_CENTER_LON", "78.9629"))  # Default India center
    DEFAULT_MAP_ZOOM = int(os.environ.get("DEFAULT_MAP_ZOOM", 5))  # Default zoom level for India

    # Application settings
    BUS_UPDATE_INTERVAL = int(os.environ.get("BUS_UPDATE_INTERVAL", 5))  # seconds
    NOTIFICATION_DISTANCE = float(os.environ.get("NOTIFICATION_DISTANCE", 0.5))  # km
    DELAY_THRESHOLD = int(os.environ.get("DELAY_THRESHOLD", 5))  # minutes