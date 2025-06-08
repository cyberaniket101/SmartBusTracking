
#!/usr/bin/env python3
import logging
from mqtt_broker import SimpleMQTTBroker

logging.basicConfig(level=logging.INFO)

def main():
    broker = SimpleMQTTBroker()
    
    try:
        print("Starting MQTT broker...")
        broker.start_broker()
    except KeyboardInterrupt:
        print("Shutting down MQTT broker...")
    finally:
        broker.stop_broker()

if __name__ == "__main__":
    main()
