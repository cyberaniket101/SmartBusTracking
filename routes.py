import logging
import json
from datetime import datetime
from flask import render_template, request, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError
from app import db
from models import Bus, Route, Stop, ETAPrediction, User, UserBusSubscription

# Configure logging
logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all routes with the Flask application"""
    # Import and register mobile API routes
    from mobile_api import register_mobile_api
    register_mobile_api(app)
    
    @app.route('/')
    def index():
        """Render the dashboard page"""
        return render_template('index.html')
        
    @app.route('/api-docs')
    def api_docs():
        """Render the API documentation page"""
        return render_template('api_docs.html')
    
    @app.route('/buses')
    def buses():
        """Render the buses management page"""
        buses = db.session.query(Bus).all()
        return render_template('buses.html', buses=buses)
    
    @app.route('/routes')
    def routes():
        """Render the routes management page"""
        routes = db.session.query(Route).all()
        return render_template('routes.html', routes=routes)
    
    @app.route('/stops')
    def stops():
        """Render the stops management page"""
        stops = db.session.query(Stop).all()
        return render_template('stops.html', stops=stops, config=app.config)
    
    @app.route('/passengers')
    def passengers():
        """Render the passenger management page"""
        return render_template('passengers.html')
    
    @app.route('/schedule')
    def schedule():
        """Render the schedule management page"""
        return render_template('schedule.html')
    
    @app.route('/notifications')
    def notifications():
        """Render the notifications page"""
        return render_template('notifications.html')
    
    @app.route('/devices')
    def devices():
        """Render the device management page"""
        return render_template('devices.html')
    
    # Export functionality
    @app.route('/api/export/buses', methods=['GET'])
    def export_buses():
        """Export bus data as CSV"""
        from flask import make_response
        import csv
        import io
        
        buses = db.session.query(Bus).all()
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Bus Number', 'License Plate', 'Capacity', 'Status', 'Current Route', 'Last Updated'])
        
        # Write data
        for bus in buses:
            writer.writerow([
                bus.id,
                bus.bus_number,
                bus.license_plate,
                bus.capacity,
                'Active' if bus.is_active else 'Inactive',
                bus.current_route.route_number if bus.current_route else 'None',
                bus.last_updated.strftime('%Y-%m-%d %H:%M:%S') if bus.last_updated else 'Never'
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=buses_export.csv'
        return response
    
    @app.route('/api/export/routes', methods=['GET'])
    def export_routes():
        """Export route data as CSV"""
        from flask import make_response
        import csv
        import io
        
        routes = db.session.query(Route).all()
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Route Number', 'Name', 'Description', 'Status', 'Total Stops'])
        
        # Write data
        for route in routes:
            writer.writerow([
                route.id,
                route.route_number,
                route.name,
                route.description or '',
                'Active' if route.is_active else 'Inactive',
                len(route.stops)
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=routes_export.csv'
        return response
    
    # Stop Management API
    @app.route('/api/stops/add', methods=['POST'])
    def add_stop():
        """Add a new stop"""
        from flask import request, jsonify
        
        try:
            data = request.get_json()
            
            # Create new stop
            new_stop = Stop(
                stop_code=data['stop_code'],
                name=data['name'],
                address=data.get('address', ''),
                latitude=float(data['latitude']),
                longitude=float(data['longitude']),
                is_active=data.get('is_active', True)
            )
            
            db.session.add(new_stop)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Stop added successfully',
                'stop_id': new_stop.id
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Error adding stop: {str(e)}'
            }), 400
    
    # API Routes for Mobile App
    
    @app.route('/api/buses', methods=['GET'])
    def api_buses():
        """Get all active buses"""
        try:
            buses = db.session.query(Bus).filter_by(is_active=True).all()
            
            result = []
            for bus in buses:
                bus_data = {
                    'id': bus.id,
                    'bus_number': bus.bus_number,
                    'latitude': bus.current_latitude,
                    'longitude': bus.current_longitude,
                    'speed': bus.current_speed,
                    'heading': bus.heading,
                    'last_updated': bus.last_updated.isoformat() if bus.last_updated else None,
                    'route_id': bus.current_route_id,
                    'next_stop_id': bus.next_stop_id
                }
                result.append(bus_data)
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving buses: {e}")
            return jsonify({'error': 'Failed to retrieve buses'}), 500
    
    @app.route('/api/bus/<bus_id>', methods=['GET'])
    def api_bus_status(bus_id):
        """Get status for a specific bus"""
        try:
            bus = db.session.query(Bus).filter_by(id=bus_id).first()
            
            if not bus:
                return jsonify({'error': 'Bus not found'}), 404
            
            # Get the current route and next stop info
            route = db.session.query(Route).get(bus.current_route_id) if bus.current_route_id else None
            next_stop = db.session.query(Stop).get(bus.next_stop_id) if bus.next_stop_id else None
            
            # Get all ETAs for this bus
            etas = db.session.query(ETAPrediction).filter_by(bus_id=bus.id).all()
            eta_data = []
            
            for eta in etas:
                stop = db.session.query(Stop).get(eta.stop_id)
                eta_data.append({
                    'stop_id': eta.stop_id,
                    'stop_name': stop.name if stop else 'Unknown',
                    'predicted_arrival': eta.predicted_arrival_time.isoformat(),
                    'is_delayed': eta.is_delayed,
                    'delay_minutes': eta.delay_minutes
                })
            
            result = {
                'id': bus.id,
                'bus_number': bus.bus_number,
                'latitude': bus.current_latitude,
                'longitude': bus.current_longitude,
                'speed': bus.current_speed,
                'heading': bus.heading,
                'last_updated': bus.last_updated.isoformat() if bus.last_updated else None,
                'route': {
                    'id': route.id,
                    'route_number': route.route_number,
                    'name': route.name
                } if route else None,
                'next_stop': {
                    'id': next_stop.id,
                    'name': next_stop.name,
                    'latitude': next_stop.latitude,
                    'longitude': next_stop.longitude
                } if next_stop else None,
                'eta_predictions': eta_data
            }
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving bus status: {e}")
            return jsonify({'error': 'Failed to retrieve bus status'}), 500
    
    @app.route('/api/eta', methods=['GET'])
    def api_eta():
        """Get ETA for a specific bus and stop"""
        try:
            bus_id = request.args.get('bus_id')
            stop_id = request.args.get('stop_id')
            
            if not bus_id or not stop_id:
                return jsonify({'error': 'Missing required parameters'}), 400
            
            # Get the ETA prediction
            eta = db.session.query(ETAPrediction).filter_by(
                bus_id=bus_id,
                stop_id=stop_id
            ).first()
            
            if not eta:
                return jsonify({'error': 'No ETA prediction found'}), 404
            
            # Get bus and stop info
            bus = db.session.query(Bus).get(bus_id)
            stop = db.session.query(Stop).get(stop_id)
            
            result = {
                'bus_id': bus_id,
                'bus_number': bus.bus_number if bus else 'Unknown',
                'stop_id': stop_id,
                'stop_name': stop.name if stop else 'Unknown',
                'predicted_arrival': eta.predicted_arrival_time.isoformat(),
                'prediction_timestamp': eta.prediction_timestamp.isoformat(),
                'is_delayed': eta.is_delayed,
                'delay_minutes': eta.delay_minutes
            }
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving ETA: {e}")
            return jsonify({'error': 'Failed to retrieve ETA'}), 500
    
    @app.route('/api/routes', methods=['GET'])
    def api_routes():
        """Get all active routes"""
        try:
            routes = db.session.query(Route).filter_by(is_active=True).all()
            
            result = []
            for route in routes:
                # Get all stops for this route
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
                            'scheduled_departure': scheduled_stop.scheduled_departure_time
                        })
                
                route_data = {
                    'id': route.id,
                    'route_number': route.route_number,
                    'name': route.name,
                    'description': route.description,
                    'stops': stops_data
                }
                result.append(route_data)
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving routes: {e}")
            return jsonify({'error': 'Failed to retrieve routes'}), 500
            
    @app.route('/api/routes/<route_id>/traffic', methods=['GET'])
    def api_route_traffic(route_id):
        """Get traffic analysis data for a specific route"""
        try:
            # Import necessary modules
            import random
            from datetime import datetime
            
            # Validate the route exists
            route = db.session.query(Route).get(route_id)
            
            if not route:
                return jsonify({'error': 'Route not found'}), 404
                
            # In a real implementation, this would call an external traffic API
            # or use historical data to predict current traffic conditions
            # For this example, we'll generate simulated traffic data
                
            # Get the route stops
            from models import ScheduledStop
            scheduled_stops = db.session.query(ScheduledStop).filter_by(
                route_id=route_id
            ).order_by(ScheduledStop.stop_sequence).all()
            
            if not scheduled_stops or len(scheduled_stops) < 2:
                return jsonify({'error': 'Route has insufficient stops for traffic analysis'}), 400
                
            # Create congestion points along the route
            congestion_points = []
            
            # Get the stops for interpolation
            stops = []
            for ss in scheduled_stops:
                stop = db.session.query(Stop).get(ss.stop_id)
                if stop:
                    stops.append({
                        'latitude': stop.latitude,
                        'longitude': stop.longitude,
                        'sequence': ss.stop_sequence
                    })
            
            # Generate congestion points between stops
            for i in range(len(stops) - 1):
                start_stop = stops[i]
                end_stop = stops[i + 1]
                
                # Create several points between stops with random congestion levels
                points_between = 5  # Number of points to generate between stops
                
                for j in range(points_between):
                    # Interpolate position
                    ratio = (j + 1) / (points_between + 1)
                    lat = start_stop['latitude'] + ratio * (end_stop['latitude'] - start_stop['latitude'])
                    lng = start_stop['longitude'] + ratio * (end_stop['longitude'] - start_stop['longitude'])
                    
                    # Cities in India with typically higher traffic
                    major_cities = [
                        {'name': 'Delhi', 'lat': 28.7041, 'lng': 77.1025},
                        {'name': 'Mumbai', 'lat': 19.0760, 'lng': 72.8777},
                        {'name': 'Bangalore', 'lat': 12.9716, 'lng': 77.5946},
                        {'name': 'Chennai', 'lat': 13.0827, 'lng': 80.2707},
                        {'name': 'Kolkata', 'lat': 22.5726, 'lng': 88.3639},
                        {'name': 'Hyderabad', 'lat': 17.3850, 'lng': 78.4867},
                        {'name': 'Ahmedabad', 'lat': 23.0225, 'lng': 72.5714},
                        {'name': 'Pune', 'lat': 18.5204, 'lng': 73.8567},
                        {'name': 'Aurangabad', 'lat': 19.8762, 'lng': 75.3433}
                    ]
                    
                    # Check proximity to major cities to increase congestion probability
                    congestion_level = random.randint(1, 4)  # Base congestion level
                    
                    for city in major_cities:
                        city_proximity = (lat - city['lat'])**2 + (lng - city['lng'])**2
                        if city_proximity < 0.01:  # Closer to a major city
                            congestion_level = random.randint(5, 10)  # Higher congestion near cities
                            break
                    
                    # Add time-based variation (rush hours)
                    current_hour = datetime.now().hour
                    
                    # Rush hours typically 8-10 AM and 5-7 PM
                    if (8 <= current_hour <= 10) or (17 <= current_hour <= 19):
                        congestion_level = min(congestion_level + random.randint(2, 4), 10)
                    
                    congestion_points.append({
                        'latitude': lat,
                        'longitude': lng,
                        'congestion_level': congestion_level,
                        'segment': i
                    })
            
            # Return the traffic analysis
            return jsonify({
                'route_id': int(route_id),
                'route_name': route.name,
                'congestion_points': congestion_points,
                'analysis_timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.exception(f"Error retrieving traffic data for route {route_id}: {e}")
            return jsonify({'error': 'Failed to retrieve traffic data'}), 500
    
    @app.route('/api/stops', methods=['GET'])
    def api_stops():
        """Get all active stops"""
        try:
            stops = db.session.query(Stop).filter_by(is_active=True).all()
            
            result = []
            for stop in stops:
                stop_data = {
                    'id': stop.id,
                    'stop_code': stop.stop_code,
                    'name': stop.name,
                    'latitude': stop.latitude,
                    'longitude': stop.longitude,
                    'address': stop.address
                }
                result.append(stop_data)
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving stops: {e}")
            return jsonify({'error': 'Failed to retrieve stops'}), 500
    
    @app.route('/api/user/subscribe', methods=['POST'])
    def api_subscribe():
        """Subscribe a user to receive notifications for a bus at a stop"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Extract required fields
            user_id = data.get('user_id')
            bus_id = data.get('bus_id')
            stop_id = data.get('stop_id')
            fcm_token = data.get('fcm_token')
            
            if not all([user_id, bus_id, stop_id, fcm_token]):
                return jsonify({'error': 'Missing required fields'}), 400
            
            # Find or create the user
            user = db.session.query(User).get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Update FCM token
            user.fcm_token = fcm_token
            
            # Check if subscription already exists
            subscription = db.session.query(UserBusSubscription).filter_by(
                user_id=user_id,
                bus_id=bus_id,
                stop_id=stop_id
            ).first()
            
            if not subscription:
                # Create new subscription
                subscription = UserBusSubscription(
                    user_id=user_id,
                    bus_id=bus_id,
                    stop_id=stop_id,
                    notify_on_approach=data.get('notify_on_approach', True),
                    notify_on_delay=data.get('notify_on_delay', True),
                    approach_distance_km=data.get('approach_distance_km', 0.5)
                )
                db.session.add(subscription)
            else:
                # Update existing subscription
                subscription.notify_on_approach = data.get('notify_on_approach', subscription.notify_on_approach)
                subscription.notify_on_delay = data.get('notify_on_delay', subscription.notify_on_delay)
                subscription.approach_distance_km = data.get('approach_distance_km', subscription.approach_distance_km)
            
            # Commit changes
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Subscription updated'})
        
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating subscription: {e}")
            return jsonify({'error': 'Database error'}), 500
        except Exception as e:
            logger.exception(f"Error updating subscription: {e}")
            return jsonify({'error': 'Failed to update subscription'}), 500
    
    @app.route('/api/devices', methods=['GET'])
    def api_devices():
        """Get all registered devices/buses"""
        try:
            buses = db.session.query(Bus).all()
            
            result = []
            for bus in buses:
                device_data = {
                    'id': bus.id,
                    'bus_number': bus.bus_number,
                    'license_plate': bus.license_plate,
                    'is_active': bus.is_active,
                    'last_updated': bus.last_updated.isoformat() if bus.last_updated else None,
                    'current_position': {
                        'latitude': bus.current_latitude,
                        'longitude': bus.current_longitude,
                        'speed': bus.current_speed,
                        'heading': bus.heading
                    } if bus.current_latitude else None
                }
                result.append(device_data)
            
            return jsonify(result)
        
        except Exception as e:
            logger.exception(f"Error retrieving devices: {e}")
            return jsonify({'error': 'Failed to retrieve devices'}), 500
    
    @app.route('/api/devices/register', methods=['POST'])
    def api_register_device():
        """Register a new ESP32 device/bus"""
        try:
            data = request.get_json()
            
            if not data or 'bus_number' not in data:
                return jsonify({'error': 'bus_number is required'}), 400
            
            # Check if bus already exists
            existing_bus = db.session.query(Bus).filter_by(
                bus_number=data['bus_number']
            ).first()
            
            if existing_bus:
                return jsonify({'error': 'Bus already registered'}), 409
            
            # Create new bus
            new_bus = Bus(
                bus_number=data['bus_number'],
                license_plate=data.get('license_plate', ''),
                capacity=data.get('capacity', 50),
                is_active=True
            )
            
            db.session.add(new_bus)
            db.session.commit()
            
            return jsonify({
                'id': new_bus.id,
                'bus_number': new_bus.bus_number,
                'message': 'Device registered successfully',
                'mqtt_topic': f"buses/{new_bus.bus_number}/telemetry"
            }), 201
        
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error registering device: {e}")
            return jsonify({'error': 'Failed to register device'}), 500

    @app.route('/api/user/unsubscribe', methods=['POST'])
    def api_unsubscribe():
        """Unsubscribe a user from notifications for a bus at a stop"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Extract required fields
            user_id = data.get('user_id')
            bus_id = data.get('bus_id')
            stop_id = data.get('stop_id')
            
            if not all([user_id, bus_id, stop_id]):
                return jsonify({'error': 'Missing required fields'}), 400
            
            # Find the subscription
            subscription = db.session.query(UserBusSubscription).filter_by(
                user_id=user_id,
                bus_id=bus_id,
                stop_id=stop_id
            ).first()
            
            if not subscription:
                return jsonify({'error': 'Subscription not found'}), 404
            
            # Delete the subscription
            db.session.delete(subscription)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Subscription removed'})
        
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error removing subscription: {e}")
            return jsonify({'error': 'Database error'}), 500
        except Exception as e:
            logger.exception(f"Error removing subscription: {e}")
            return jsonify({'error': 'Failed to remove subscription'}), 500
