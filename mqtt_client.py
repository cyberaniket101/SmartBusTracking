import json
import logging
from datetime import datetime
import paho.mqtt.client as mqtt
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import db
from models import Bus
from time_series_db import store_telemetry
from eta_predictor import update_eta_predictions

# Configure logging
logger = logging.getLogger(__name__)

# Global MQTT client and app reference
mqtt_client = None
flask_app = None

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker"""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        # Subscribe to the topic for all buses
        topic = "buses/+/telemetry"  # Use wildcard pattern for all buses
        client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")
    else:
        logger.error(f"Failed to connect to MQTT broker with result code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the broker"""
    try:
        # Parse the message payload as JSON
        payload = json.loads(msg.payload.decode())
        
        # Extract bus ID from the topic (format: buses/{bus_id}/telemetry)
        topic_parts = msg.topic.split('/')
        if len(topic_parts) != 3:
            logger.warning(f"Invalid topic format: {msg.topic}")
            return
        
        bus_number = topic_parts[1]
        
        # Log received telemetry
        logger.debug(f"Received telemetry from bus {bus_number}: {payload}")
        
        # Check if payload contains required fields
        required_fields = ['latitude', 'longitude', 'speed', 'timestamp']
        if not all(field in payload for field in required_fields):
            logger.warning(f"Missing required fields in payload: {payload}")
            return
        
        # Store telemetry in InfluxDB
        store_telemetry(bus_number, payload)
        
        # Update bus position in PostgreSQL
        update_bus_position(bus_number, payload)
        
        # Update ETA predictions based on new position
        update_eta_predictions(bus_number)
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in message payload: {msg.payload}")
    except Exception as e:
        logger.exception(f"Error processing MQTT message: {e}")

def update_bus_position(bus_number, telemetry):
    """Update the bus position in the PostgreSQL database"""
    global flask_app
    
    if not flask_app:
        logger.error("Flask app not available for database operations")
        return
        
    try:
        with flask_app.app_context():
            # Get current timestamp or use the one from telemetry
            if 'timestamp' in telemetry:
                timestamp = datetime.fromtimestamp(telemetry['timestamp'])
            else:
                timestamp = datetime.utcnow()
            
            # Find the bus in the database
            bus = db.session.query(Bus).filter_by(bus_number=bus_number).first()
            
            if bus:
                # Update bus location and status
                bus.current_latitude = telemetry['latitude']
                bus.current_longitude = telemetry['longitude']
                bus.current_speed = telemetry['speed']
                bus.last_updated = timestamp
                
                # Update heading if provided
                if 'heading' in telemetry:
                    bus.heading = telemetry['heading']
                
                # Commit changes to database
                db.session.commit()
                logger.debug(f"Updated position for bus {bus_number}")
            else:
                logger.warning(f"Bus {bus_number} not found in database")
    
    except SQLAlchemyError as e:
        if flask_app:
            with flask_app.app_context():
                db.session.rollback()
        logger.error(f"Database error updating bus position: {e}")
    except Exception as e:
        logger.exception(f"Error updating bus position: {e}")

def init_mqtt_client(app):
    """Initialize the MQTT client with the application context"""
    global mqtt_client, flask_app
    
    # Store app reference for use in callbacks
    flask_app = app
    
    with app.app_context():
        # Create MQTT client
        client_id = app.config["MQTT_CLIENT_ID"]
        mqtt_client = mqtt.Client(client_id=client_id)
        
        # Set credentials if provided
        username = app.config["MQTT_USERNAME"]
        password = app.config["MQTT_PASSWORD"]
        if username and password:
            mqtt_client.username_pw_set(username, password)
        
        # Set callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        
        # Connect to broker
        broker = app.config["MQTT_BROKER"]
        port = app.config["MQTT_PORT"]
        
        try:
            logger.info(f"Connecting to MQTT broker at {broker}:{port}")
            mqtt_client.connect(broker, port, 60)
            
            # Start the MQTT client loop in a background thread
            mqtt_client.loop_start()
            logger.info("MQTT client started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            logger.info("Continuing without MQTT connection - bus data will need to be added manually")

def stop_mqtt_client():
    """Stop the MQTT client"""
    global mqtt_client
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client stopped")
