from app import app, init_app
import logging

# Initialize the application
if not init_app():
    logging.error("Failed to initialize application. Exiting.")
    exit(1)

if __name__ == "__main__":
    logging.info("Starting Smart Bus Tracking Server")
    app.run(host="0.0.0.0", port=5000, debug=True)
