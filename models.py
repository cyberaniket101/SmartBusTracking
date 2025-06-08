from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import ForeignKey, Float, String, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import relationship

class User(UserMixin, db.Model):
    """User model for authentication and notification preferences"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    fcm_token = db.Column(db.String(256), nullable=True)  # Firebase Cloud Messaging token
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subscriptions = relationship("UserBusSubscription", back_populates="user")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Bus(db.Model):
    """Bus model to store information about each bus"""
    __tablename__ = 'buses'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(20), unique=True, nullable=False)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    
    # Current location and status
    current_latitude = db.Column(db.Float, nullable=True)
    current_longitude = db.Column(db.Float, nullable=True)
    current_speed = db.Column(db.Float, nullable=True)  # km/h
    heading = db.Column(db.Float, nullable=True)  # degrees
    last_updated = db.Column(db.DateTime, nullable=True)
    current_route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    next_stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=True)
    
    # Relationships
    current_route = relationship("Route", foreign_keys=[current_route_id])
    next_stop = relationship("Stop", foreign_keys=[next_stop_id])
    eta_predictions = relationship("ETAPrediction", back_populates="bus")
    subscriptions = relationship("UserBusSubscription", back_populates="bus")
    
    def __repr__(self):
        return f"<Bus {self.bus_number}>"

class Route(db.Model):
    """Route model to define bus routes"""
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    stops = relationship("ScheduledStop", back_populates="route", order_by="ScheduledStop.stop_sequence")
    
    def __repr__(self):
        return f"<Route {self.route_number}: {self.name}>"

class Stop(db.Model):
    """Bus stop model to store information about each stop"""
    __tablename__ = 'stops'
    
    id = db.Column(db.Integer, primary_key=True)
    stop_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    route_stops = relationship("ScheduledStop", back_populates="stop")
    eta_predictions = relationship("ETAPrediction", back_populates="stop")
    
    def __repr__(self):
        return f"<Stop {self.stop_code}: {self.name}>"

class ScheduledStop(db.Model):
    """Junction table to define stops in a route with their sequence and scheduled times"""
    __tablename__ = 'scheduled_stops'
    
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=False)
    stop_sequence = db.Column(db.Integer, nullable=False)  # Order of stops in the route
    scheduled_arrival_time = db.Column(db.String(8), nullable=True)  # HH:MM:SS format
    scheduled_departure_time = db.Column(db.String(8), nullable=True)  # HH:MM:SS format
    distance_from_start = db.Column(db.Float, nullable=True)  # Distance in km from route start
    
    # Relationships
    route = relationship("Route", back_populates="stops")
    stop = relationship("Stop", back_populates="route_stops")
    
    def __repr__(self):
        return f"<ScheduledStop {self.route.route_number} - {self.stop.name} ({self.stop_sequence})>"

class ETAPrediction(db.Model):
    """Model to store ETA predictions for buses arriving at stops"""
    __tablename__ = 'eta_predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=False)
    
    # Prediction details
    predicted_arrival_time = db.Column(db.DateTime, nullable=False)
    prediction_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    confidence_level = db.Column(db.Float, nullable=True)  # 0-1 scale if ML-based
    is_delayed = db.Column(db.Boolean, default=False)
    delay_minutes = db.Column(db.Integer, default=0)
    
    # Relationships
    bus = relationship("Bus", back_populates="eta_predictions")
    stop = relationship("Stop", back_populates="eta_predictions")
    route = relationship("Route")
    
    def __repr__(self):
        arrival_time = self.predicted_arrival_time.strftime('%H:%M:%S')
        return f"<ETAPrediction Bus:{self.bus.bus_number} to {self.stop.name} at {arrival_time}>"

class UserBusSubscription(db.Model):
    """Model to track user subscriptions to specific buses for notifications"""
    __tablename__ = 'user_bus_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bus_id = db.Column(db.Integer, db.ForeignKey('buses.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('stops.id'), nullable=False)
    
    # Notification preferences
    notify_on_approach = db.Column(db.Boolean, default=True)
    notify_on_delay = db.Column(db.Boolean, default=True)
    approach_distance_km = db.Column(db.Float, default=0.5)  # km
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    bus = relationship("Bus", back_populates="subscriptions")
    stop = relationship("Stop")
    
    def __repr__(self):
        return f"<UserBusSubscription User:{self.user.username} - Bus:{self.bus.bus_number}>"
