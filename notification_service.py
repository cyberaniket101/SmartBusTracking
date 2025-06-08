import logging
import os
import math
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app
import firebase_admin
from firebase_admin import credentials, messaging
from app import db
from models import Bus, Stop, ETAPrediction, UserBusSubscription

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

# Configure logging
logger = logging.getLogger(__name__)

# Global Firebase app
firebase_app = None

def init_firebase(app):
    """Initialize Firebase admin SDK for FCM notifications"""
    global firebase_app
    
    # Skip initialization if already initialized
    if firebase_app:
        return True
    
    try:
        # Get Firebase credentials from environment
        cred_json = app.config.get("FIREBASE_CREDENTIALS")
        
        if not cred_json:
            logger.warning("Firebase credentials not configured, notifications disabled")
            return False
        
        # Initialize Firebase app
        cred = credentials.Certificate(cred_json)
        firebase_app = firebase_admin.initialize_app(cred)
        
        logger.info("Firebase initialized successfully for notifications")
        return True
    
    except Exception as e:
        logger.exception(f"Failed to initialize Firebase: {e}")
        return False

def send_eta_notifications(bus):
    """Send push notifications to users subscribed to this bus"""
    try:
        # Ensure Firebase is initialized
        if not firebase_app:
            with current_app.app_context():
                if not init_firebase(current_app):
                    logger.warning("Firebase not initialized, skipping notifications")
                    return False
        
        # Get notification distance threshold from config
        notification_distance = current_app.config.get("NOTIFICATION_DISTANCE", 0.5)  # km
        
        # Get all ETA predictions for this bus
        eta_predictions = db.session.query(ETAPrediction).filter_by(bus_id=bus.id).all()
        
        for eta in eta_predictions:
            # Get the stop information
            stop = db.session.query(Stop).get(eta.stop_id)
            
            if not stop:
                continue
            
            # Calculate distance to stop
            if bus.current_latitude and bus.current_longitude:
                distance = calculate_distance(
                    bus.current_latitude, bus.current_longitude,
                    stop.latitude, stop.longitude
                )
            else:
                continue
            
            # Find users subscribed to this bus and stop
            subscriptions = db.session.query(UserBusSubscription).filter_by(
                bus_id=bus.id,
                stop_id=stop.id
            ).all()
            
            for subscription in subscriptions:
                # Get user's FCM token
                user = subscription.user
                
                if not user or not user.fcm_token:
                    continue
                
                # Check if bus is nearby for approach notification
                if (subscription.notify_on_approach and 
                    distance <= subscription.approach_distance_km):
                    
                    send_approach_notification(user.fcm_token, bus, stop, distance)
                
                # Check if bus is delayed for delay notification
                if subscription.notify_on_delay and eta.is_delayed:
                    send_delay_notification(user.fcm_token, bus, stop, eta)
        
        return True
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error sending notifications: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error sending notifications: {e}")
        return False

def send_approach_notification(fcm_token, bus, stop, distance):
    """Send notification that a bus is approaching the stop"""
    try:
        # Format distance for display
        distance_str = f"{distance:.1f}" if distance < 1 else f"{int(distance)}"
        
        # Create message
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"Bus {bus.bus_number} Approaching",
                body=f"Bus {bus.bus_number} is {distance_str} km away from {stop.name}"
            ),
            data={
                'bus_id': str(bus.id),
                'bus_number': bus.bus_number,
                'stop_id': str(stop.id),
                'stop_name': stop.name,
                'distance': str(distance),
                'notification_type': 'approach'
            },
            token=fcm_token
        )
        
        # Send message
        response = messaging.send(message)
        logger.debug(f"Sent approach notification, response: {response}")
        return True
    
    except Exception as e:
        logger.exception(f"Error sending approach notification: {e}")
        return False

def send_delay_notification(fcm_token, bus, stop, eta):
    """Send notification that a bus is delayed"""
    try:
        # Format arrival time
        arrival_time = eta.predicted_arrival_time.strftime('%H:%M')
        
        # Create message
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"Bus {bus.bus_number} Delayed",
                body=f"Bus {bus.bus_number} to {stop.name} is delayed by {eta.delay_minutes} minutes. New ETA: {arrival_time}"
            ),
            data={
                'bus_id': str(bus.id),
                'bus_number': bus.bus_number,
                'stop_id': str(stop.id),
                'stop_name': stop.name,
                'delay_minutes': str(eta.delay_minutes),
                'eta': arrival_time,
                'notification_type': 'delay'
            },
            token=fcm_token
        )
        
        # Send message
        response = messaging.send(message)
        logger.debug(f"Sent delay notification, response: {response}")
        return True
    
    except Exception as e:
        logger.exception(f"Error sending delay notification: {e}")
        return False
