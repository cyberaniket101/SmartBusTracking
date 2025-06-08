import logging
from datetime import datetime, timedelta
from flask import current_app
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Configure logging
logger = logging.getLogger(__name__)

# Global InfluxDB client
influx_client = None
write_api = None
query_api = None

def init_influxdb(app):
    """Initialize the InfluxDB client with application context"""
    global influx_client, write_api, query_api
    
    try:
        url = app.config["INFLUXDB_URL"]
        token = app.config["INFLUXDB_TOKEN"]
        org = app.config["INFLUXDB_ORG"]
        
        # Create InfluxDB client
        influx_client = InfluxDBClient(url=url, token=token, org=org)
        
        # Create API clients
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        query_api = influx_client.query_api()
        
        logger.info("InfluxDB client initialized successfully")
        return True
    except Exception as e:
        logger.exception(f"Failed to initialize InfluxDB client: {e}")
        return False

def store_telemetry(bus_number, telemetry):
    """Store bus telemetry data in InfluxDB"""
    global write_api
    
    try:
        # Ensure InfluxDB client is initialized
        if not write_api:
            with current_app.app_context():
                if not init_influxdb(current_app):
                    logger.error("Failed to initialize InfluxDB client")
                    return False
        
        # Get bucket name from config
        bucket = current_app.config["INFLUXDB_BUCKET"]
        
        # Create a data point
        point = Point("bus_telemetry")
        point.tag("bus_number", bus_number)
        
        # Add all telemetry fields
        for key, value in telemetry.items():
            if key == 'timestamp':
                # Convert timestamp to datetime if needed
                if isinstance(value, (int, float)):
                    point.time(datetime.fromtimestamp(value))
                continue
            
            # Add fields based on their data type
            if isinstance(value, bool):
                point.field(key, value)
            elif isinstance(value, (int, float)):
                point.field(key, float(value))
            elif isinstance(value, str):
                point.tag(key, value)
        
        # Write to InfluxDB
        write_api.write(bucket=bucket, record=point)
        logger.debug(f"Stored telemetry for bus {bus_number} in InfluxDB")
        return True
    
    except Exception as e:
        logger.exception(f"Error storing telemetry in InfluxDB: {e}")
        return False

def get_bus_telemetry_history(bus_number, hours=1):
    """Query InfluxDB for historical telemetry data for a specific bus"""
    global query_api
    
    try:
        # Ensure InfluxDB client is initialized
        if not query_api:
            with current_app.app_context():
                if not init_influxdb(current_app):
                    logger.error("Failed to initialize InfluxDB client")
                    return []
        
        # Get bucket name from config
        bucket = current_app.config["INFLUXDB_BUCKET"]
        org = current_app.config["INFLUXDB_ORG"]
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Build Flux query
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
          |> filter(fn: (r) => r._measurement == "bus_telemetry")
          |> filter(fn: (r) => r.bus_number == "{bus_number}")
        '''
        
        # Execute query
        result = query_api.query(query=query, org=org)
        
        # Process and return results
        telemetry_history = []
        for table in result:
            for record in table.records:
                # Extract record data
                record_data = {
                    'time': record.get_time(),
                    'field': record.get_field(),
                    'value': record.get_value()
                }
                telemetry_history.append(record_data)
        
        return telemetry_history
    
    except Exception as e:
        logger.exception(f"Error querying telemetry from InfluxDB: {e}")
        return []

def get_average_speed(bus_number, minutes=15):
    """Calculate the average speed of a bus over the last specified minutes"""
    global query_api
    
    try:
        # Ensure InfluxDB client is initialized
        if not query_api:
            with current_app.app_context():
                if not init_influxdb(current_app):
                    logger.error("Failed to initialize InfluxDB client")
                    return None
        
        # Get bucket name from config
        bucket = current_app.config["INFLUXDB_BUCKET"]
        org = current_app.config["INFLUXDB_ORG"]
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)
        
        # Build Flux query to calculate average speed
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
          |> filter(fn: (r) => r._measurement == "bus_telemetry")
          |> filter(fn: (r) => r.bus_number == "{bus_number}")
          |> filter(fn: (r) => r._field == "speed")
          |> mean()
        '''
        
        # Execute query
        result = query_api.query(query=query, org=org)
        
        # Extract average speed
        if result and len(result) > 0 and len(result[0].records) > 0:
            return result[0].records[0].get_value()
        else:
            logger.warning(f"No speed data found for bus {bus_number} in the last {minutes} minutes")
            return None
    
    except Exception as e:
        logger.exception(f"Error calculating average speed from InfluxDB: {e}")
        return None
