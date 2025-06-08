
#!/usr/bin/env python3
import logging
import threading
import time
import socket
from paho.mqtt import client as mqtt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMQTTBroker:
    def __init__(self):
        self.running = False
        self.clients = []
        self.server_socket = None
        
    def start_broker(self):
        """Start a simple MQTT broker"""
        try:
            # Create a simple TCP server to act as MQTT broker
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', 1883))
            self.server_socket.listen(5)
            
            self.running = True
            logger.info("MQTT Broker started on 0.0.0.0:1883")
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"MQTT client connected from {addr}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logger.error(f"Socket error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Failed to start MQTT broker: {e}")
        
    def handle_client(self, client_socket, addr):
        """Handle individual MQTT client connections"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                # Simple MQTT packet handling
                # For now, just acknowledge connection
                if len(data) > 0:
                    logger.info(f"Received MQTT data from {addr}: {len(data)} bytes")
                    
                    # Send CONNACK (Connection Acknowledgment)
                    connack = b'\x20\x02\x00\x00'  # MQTT CONNACK packet
                    client_socket.send(connack)
                    
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()
            logger.info(f"Client {addr} disconnected")
        
    def stop_broker(self):
        """Stop the MQTT broker"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info("MQTT Broker stopped")

if __name__ == "__main__":
    broker = SimpleMQTTBroker()
    
    try:
        broker.start_broker()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        broker.stop_broker()
