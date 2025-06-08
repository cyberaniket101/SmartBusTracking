import logging
import math
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app
from app import db
from models import Bus, Stop, Route, ETAPrediction, ScheduledStop
from notification_service import send_eta_notifications
from time_series_db import get_average_speed

# Configure logging
logger = logging.getLogger(__name__)

def update_eta_predictions(bus_number):
    """Update ETA predictions for a specific bus"""
    try:
        # Get the bus from the database
        bus = db.session.query(Bus).filter_by(bus_number=bus_number).first()
        
        if not bus:
            logger.warning(f"Bus {bus_number} not found in database")
            return False
        
        # Check if the bus is on an active route
        if not bus.current_route_id:
            logger.debug(f"Bus {bus_number} is not currently on an active route")
            return False
        
        # Get all remaining stops on the bus's current route
        scheduled_stops = db.session.query(ScheduledStop).filter_by(
            route_id=bus.current_route_id
        ).order_by(ScheduledStop.stop_sequence).all()
        
        if not scheduled_stops:
            logger.warning(f"No scheduled stops found for route {bus.current_route_id}")
            return False
        
        # Determine the next stop if not already set
        if not bus.next_stop_id:
            # Find the first stop in the sequence
            bus.next_stop_id = scheduled_stops[0].stop_id
            db.session.commit()
        
        # Find the current stop sequence
        current_stop_index = next(
            (i for i, stop in enumerate(scheduled_stops) if stop.stop_id == bus.next_stop_id), 
            0
        )
        
        # Calculate ETA for each remaining stop
        for i in range(current_stop_index, len(scheduled_stops)):
            stop = scheduled_stops[i]
            stop_info = db.session.query(Stop).get(stop.stop_id)
            
            if not stop_info:
                logger.warning(f"Stop with ID {stop.stop_id} not found")
                continue
            
            # Calculate ETA for this stop
            eta = calculate_eta(bus, stop_info)
            
            # Update or create ETA prediction in database
            update_eta_record(bus, stop_info, eta)
        
        # Trigger notifications for updated ETAs
        send_eta_notifications(bus)
        
        return True
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error updating ETA predictions: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error updating ETA predictions: {e}")
        return False

def calculate_eta(bus, stop):
    """
    Calculate the estimated time of arrival for a bus at a specific stop
    using a rule-based approach.
    """
    try:
        # Get current time
        now = datetime.utcnow()
        
        # If bus doesn't have location data, return None
        if not bus.current_latitude or not bus.current_longitude:
            return None
        
        # Calculate distance between bus and stop (haversine formula)
        distance_km = calculate_distance(
            bus.current_latitude, bus.current_longitude,
            stop.latitude, stop.longitude
        )
        
        # Get average speed from recent telemetry if available
        avg_speed_kmh = get_average_speed(bus.bus_number, minutes=15)
        
        # If no average speed available, use current speed or default
        if avg_speed_kmh is None:
            avg_speed_kmh = bus.current_speed if bus.current_speed else 20.0  # Default 20 km/h
        
        # Avoid division by zero
        if avg_speed_kmh <= 0:
            avg_speed_kmh = 5.0  # Minimum speed assumption
        
        # Calculate travel time in hours
        travel_time_hours = distance_km / avg_speed_kmh
        
        # Convert to minutes and add traffic/stop delay factor (20% additional time)
        travel_time_minutes = (travel_time_hours * 60) * 1.2
        
        # Calculate ETA
        eta = now + timedelta(minutes=travel_time_minutes)
        
        logger.debug(f"Calculated ETA for bus {bus.bus_number} to stop {stop.name}: {eta}")
        return eta
    
    except Exception as e:
        logger.exception(f"Error calculating ETA: {e}")
        return None

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

def update_eta_record(bus, stop, eta_time):
    """Update or create an ETA prediction record in the database"""
    try:
        if not eta_time:
            return False
        
        # Check for existing ETA prediction
        eta_prediction = db.session.query(ETAPrediction).filter_by(
            bus_id=bus.id,
            stop_id=stop.id,
            route_id=bus.current_route_id
        ).first()
        
        # Get delay threshold from config
        delay_threshold = current_app.config.get("DELAY_THRESHOLD", 5)  # default 5 minutes
        
        # Check if this is a new prediction or update
        if eta_prediction:
            # Calculate if the bus is delayed
            time_diff = (eta_time - eta_prediction.predicted_arrival_time).total_seconds() / 60
            
            # Update existing prediction
            eta_prediction.predicted_arrival_time = eta_time
            eta_prediction.prediction_timestamp = datetime.utcnow()
            
            # Update delay status
            if time_diff > delay_threshold:
                eta_prediction.is_delayed = True
                eta_prediction.delay_minutes = int(time_diff)
            else:
                eta_prediction.is_delayed = False
                eta_prediction.delay_minutes = 0
        else:
            # Create new prediction
            eta_prediction = ETAPrediction(
                bus_id=bus.id,
                stop_id=stop.id,
                route_id=bus.current_route_id,
                predicted_arrival_time=eta_time,
                prediction_timestamp=datetime.utcnow(),
                is_delayed=False,
                delay_minutes=0
            )
            db.session.add(eta_prediction)
        
        # Commit changes
        db.session.commit()
        return True
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error updating ETA record: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error updating ETA record: {e}")
        return False
