import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define SQLAlchemy base class
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("SESSION_SECRET", Config.SECRET_KEY)

# Use ProxyFix for proper handling of proxied requests
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize database with app
db.init_app(app)

# Import models to ensure they are registered with SQLAlchemy
from models import Bus, Route, Stop, ScheduledStop, ETAPrediction, User, UserBusSubscription

# Import and register routes
from routes import register_routes
register_routes(app)

def init_app():
    """Initialize the application components"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
        # Import and initialize the MQTT client
        from mqtt_client import init_mqtt_client
        init_mqtt_client(app)
        
        logger.info("Application initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False
