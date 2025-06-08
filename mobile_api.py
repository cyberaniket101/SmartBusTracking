"""
Mobile API for Smart Bus Tracking App
Provides endpoints specifically designed for mobile app integration
"""

import logging
import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from models import db, Bus, Route, Stop, ETAPrediction, User, UserBusSubscription
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from notification_service import send_approach_notification, send_delay_notification
from time_series_db import get_bus_telemetry_history, get_average_speed

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint for mobile API
mobile_api = Blueprint('mobile_api', __name__, url_prefix='/api/mobile')

# API Versioning
API_VERSION = 'v1'

@mobile_api.route('/version', methods=['GET'])
def api_version():
    """Return API version information"""
    return jsonify({
        'version': API_VERSION,
        'timestamp': datetime.utcnow().isoformat()
    })

@mobile_api.route('/buses', methods=['GET'])
def get_buses():
    """Get all active buses with current location and status"""
    try:
        buses = db.session.query(Bus).filter_by(is_active=True).all()
        
        result = []
        for bus in buses:
            # Skip buses without location data
            if not bus.current_latitude or not bus.current_longitude:
                continue
                
            # Get current route details if available
            route_info = None
            if bus.current_route_id:
                route = db.session.query(Route).get(bus.current_route_id)
                if route:
                    route_info = {
                        'id': route.id,
                        'route_number': route.route_number,
                        'name': route.name
                    }
            
            # Get next stop details if available
            next_stop_info = None
            if bus.next_stop_id:
                stop = db.session.query(Stop).get(bus.next_stop_id)
                if stop:
                    next_stop_info = {
                        'id': stop.id,
                        'name': stop.name,
                        'code': stop.stop_code,
                        'latitude': stop.latitude,
                        'longitude': stop.longitude
                    }
                    
                    # Get ETA for next stop
                    eta = db.session.query(ETAPrediction).filter_by(
                        bus_id=bus.id, 
                        stop_id=stop.id
                    ).order_by(
                        ETAPrediction.prediction_timestamp.desc()
                    ).first()
                    
                    if eta:
                        next_stop_info['eta'] = eta.predicted_arrival_time.isoformat()
                        next_stop_info['is_delayed'] = eta.is_delayed
                        next_stop_info['delay_minutes'] = eta.delay_minutes
            
            # Add bus information
            bus_data = {
                'id': bus.id,
                'bus_number': bus.bus_number,
                'latitude': bus.current_latitude,
                'longitude': bus.current_longitude,
                'speed': bus.current_speed,
                'heading': bus.heading,
                'last_updated': bus.last_updated.isoformat() if bus.last_updated else None,
                'route': route_info,
                'next_stop': next_stop_info,
                'capacity': bus.capacity,
                'license_plate': bus.license_plate
            }
            
            result.append(bus_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error retrieving buses for mobile API: {e}")
        return jsonify({'error': 'Failed to retrieve bus data'}), 500

@mobile_api.route('/buses/<bus_id>/telemetry', methods=['GET'])
def get_bus_telemetry(bus_id):
    """Get historical telemetry data for a specific bus"""
    try:
        # Validate bus exists
        bus = db.session.query(Bus).get(bus_id)
        if not bus:
            return jsonify({'error': 'Bus not found'}), 404
            
        # Get time range parameter (default to last hour)
        hours = request.args.get('hours', default=1, type=int)
        if hours < 1 or hours > 24:
            return jsonify({'error': 'Hours parameter must be between 1 and 24'}), 400
            
        # Get telemetry data from time series database
        telemetry = get_bus_telemetry_history(bus.bus_number, hours)
        
        return jsonify({
            'bus_id': bus.id,
            'bus_number': bus.bus_number,
            'telemetry': telemetry
        })
        
    except Exception as e:
        logger.exception(f"Error retrieving bus telemetry: {e}")
        return jsonify({'error': 'Failed to retrieve telemetry data'}), 500

@mobile_api.route('/routes', methods=['GET'])
def get_routes():
    """Get all active routes with stops"""
    try:
        routes = db.session.query(Route).filter_by(is_active=True).all()
        
        result = []
        for route in routes:
            # Get all stops for this route in correct sequence
            stops_data = []
            for scheduled_stop in route.stops:
                stop = db.session.query(Stop).get(scheduled_stop.stop_id)
                if stop:
                    stops_data.append({
                        'id': stop.id,
                        'stop_code': stop.stop_code,
                        'name': stop.name,
                        'latitude': stop.latitude,
                        'longitude': stop.longitude,
                        'sequence': scheduled_stop.stop_sequence,
                        'scheduled_arrival': scheduled_stop.scheduled_arrival_time,
                        'scheduled_departure': scheduled_stop.scheduled_departure_time,
                        'distance_from_start': scheduled_stop.distance_from_start
                    })
            
            # Add route information
            route_data = {
                'id': route.id,
                'route_number': route.route_number,
                'name': route.name,
                'description': route.description,
                'stops': stops_data
            }
            
            # Get buses currently on this route
            buses_on_route = db.session.query(Bus).filter_by(
                current_route_id=route.id,
                is_active=True
            ).all()
            
            if buses_on_route:
                route_data['active_buses'] = [{
                    'id': bus.id,
                    'bus_number': bus.bus_number,
                    'latitude': bus.current_latitude,
                    'longitude': bus.current_longitude
                } for bus in buses_on_route if bus.current_latitude and bus.current_longitude]
            else:
                route_data['active_buses'] = []
            
            result.append(route_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error retrieving routes for mobile API: {e}")
        return jsonify({'error': 'Failed to retrieve route data'}), 500

@mobile_api.route('/stops/<stop_id>/eta', methods=['GET'])
def get_stop_eta(stop_id):
    """Get ETAs for all buses arriving at a specific stop"""
    try:
        # Validate stop exists
        stop = db.session.query(Stop).get(stop_id)
        if not stop:
            return jsonify({'error': 'Stop not found'}), 404
        
        # Get all ETAs for this stop
        etas = db.session.query(ETAPrediction).filter_by(
            stop_id=stop_id
        ).order_by(
            ETAPrediction.predicted_arrival_time
        ).all()
        
        result = {
            'stop_id': stop.id,
            'stop_name': stop.name,
            'stop_code': stop.stop_code,
            'latitude': stop.latitude,
            'longitude': stop.longitude,
            'arrivals': []
        }
        
        for eta in etas:
            # Only include ETAs for future arrivals
            if eta.predicted_arrival_time > datetime.utcnow():
                # Get bus details
                bus = db.session.query(Bus).get(eta.bus_id)
                if not bus:
                    continue
                
                # Get route details
                route = db.session.query(Route).get(eta.route_id)
                if not route:
                    continue
                
                arrival = {
                    'bus_id': bus.id,
                    'bus_number': bus.bus_number,
                    'route_id': route.id,
                    'route_number': route.route_number,
                    'route_name': route.name,
                    'eta': eta.predicted_arrival_time.isoformat(),
                    'is_delayed': eta.is_delayed,
                    'delay_minutes': eta.delay_minutes,
                    'confidence': eta.confidence_level
                }
                
                # Add current bus position if available
                if bus.current_latitude and bus.current_longitude:
                    arrival['current_position'] = {
                        'latitude': bus.current_latitude,
                        'longitude': bus.current_longitude
                    }
                
                result['arrivals'].append(arrival)
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error retrieving ETAs for stop {stop_id}: {e}")
        return jsonify({'error': 'Failed to retrieve ETA data'}), 500

@mobile_api.route('/user/register', methods=['POST'])
def register_user():
    """Register a new user for the mobile app"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if username or email already exists
        existing_user = db.session.query(User).filter(
            (User.username == data['username']) | (User.email == data['email'])
        ).first()
        
        if existing_user:
            return jsonify({'error': 'Username or email already registered'}), 409
        
        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email']
        )
        new_user.set_password(data['password'])
        
        # Add FCM token if provided
        if 'fcm_token' in data:
            new_user.fcm_token = data['fcm_token']
        
        # Save to database
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'message': 'User registered successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error registering user: {e}")
        return jsonify({'error': 'Failed to register user'}), 500

@mobile_api.route('/user/login', methods=['POST'])
def login():
    """Login user and return authentication token"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Find user by username
        user = db.session.query(User).filter_by(username=data['username']).first()
        
        # Check if user exists and password is correct
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Update FCM token if provided
        if 'fcm_token' in data:
            user.fcm_token = data['fcm_token']
            db.session.commit()
        
        # Login user
        login_user(user)
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.exception(f"Error logging in user: {e}")
        return jsonify({'error': 'Failed to log in'}), 500

@mobile_api.route('/user/subscriptions', methods=['GET'])
@login_required
def get_user_subscriptions():
    """Get all bus subscriptions for the current user"""
    try:
        subscriptions = db.session.query(UserBusSubscription).filter_by(
            user_id=current_user.id
        ).all()
        
        result = []
        for sub in subscriptions:
            # Get bus and stop details
            bus = db.session.query(Bus).get(sub.bus_id)
            stop = db.session.query(Stop).get(sub.stop_id)
            
            if not bus or not stop:
                continue
            
            subscription = {
                'id': sub.id,
                'bus': {
                    'id': bus.id,
                    'bus_number': bus.bus_number
                },
                'stop': {
                    'id': stop.id,
                    'name': stop.name,
                    'code': stop.stop_code
                },
                'notify_on_approach': sub.notify_on_approach,
                'notify_on_delay': sub.notify_on_delay,
                'approach_distance_km': sub.approach_distance_km
            }
            
            result.append(subscription)
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error retrieving user subscriptions: {e}")
        return jsonify({'error': 'Failed to retrieve subscriptions'}), 500

@mobile_api.route('/user/subscribe', methods=['POST'])
@login_required
def subscribe_to_bus():
    """Subscribe user to receive notifications for a bus at a stop"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['bus_id', 'stop_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate bus and stop exist
        bus = db.session.query(Bus).get(data['bus_id'])
        stop = db.session.query(Stop).get(data['stop_id'])
        
        if not bus or not stop:
            return jsonify({'error': 'Invalid bus or stop ID'}), 404
        
        # Check if subscription already exists
        existing_sub = db.session.query(UserBusSubscription).filter_by(
            user_id=current_user.id,
            bus_id=data['bus_id'],
            stop_id=data['stop_id']
        ).first()
        
        if existing_sub:
            return jsonify({'error': 'Subscription already exists', 'id': existing_sub.id}), 409
        
        # Create new subscription
        subscription = UserBusSubscription(
            user_id=current_user.id,
            bus_id=data['bus_id'],
            stop_id=data['stop_id']
        )
        
        # Set optional parameters if provided
        if 'notify_on_approach' in data:
            subscription.notify_on_approach = data['notify_on_approach']
        
        if 'notify_on_delay' in data:
            subscription.notify_on_delay = data['notify_on_delay']
        
        if 'approach_distance_km' in data:
            subscription.approach_distance_km = data['approach_distance_km']
        
        # Save to database
        db.session.add(subscription)
        db.session.commit()
        
        return jsonify({
            'id': subscription.id,
            'message': 'Subscription created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error creating subscription: {e}")
        return jsonify({'error': 'Failed to create subscription'}), 500

@mobile_api.route('/user/unsubscribe/<subscription_id>', methods=['DELETE'])
@login_required
def unsubscribe_from_bus(subscription_id):
    """Unsubscribe user from bus notifications"""
    try:
        # Find subscription
        subscription = db.session.query(UserBusSubscription).get(subscription_id)
        
        # Validate subscription exists and belongs to current user
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        if subscription.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete subscription
        db.session.delete(subscription)
        db.session.commit()
        
        return jsonify({'message': 'Subscription deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error deleting subscription: {e}")
        return jsonify({'error': 'Failed to delete subscription'}), 500

@mobile_api.route('/user/update-token', methods=['POST'])
@login_required
def update_fcm_token():
    """Update FCM token for push notifications"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'fcm_token' not in data:
            return jsonify({'error': 'FCM token is required'}), 400
        
        # Update user's FCM token
        current_user.fcm_token = data['fcm_token']
        db.session.commit()
        
        return jsonify({'message': 'FCM token updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error updating FCM token: {e}")
        return jsonify({'error': 'Failed to update FCM token'}), 500

def register_mobile_api(app):
    """Register the mobile API blueprint with the Flask app"""
    app.register_blueprint(mobile_api)
    logger.info("Mobile API routes registered")