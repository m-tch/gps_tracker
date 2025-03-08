import serial
import time
import ssl
import paho.mqtt.client as mqtt
import json
import os
import logging
from datetime import datetime
import pytz

# Configure Logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Configure Serial Port (Update with correct ttyUSB port)
ser = serial.Serial('/dev/ttyUSB2', 115200, timeout=1)

# AWS MQTT Configuration
AWS_ENDPOINT = ""  # Enter your AWS endpoint
MQTT_PORT = 8883
MQTT_TOPIC = "gps/tracker"
MQTT_CLIENT = "gps-tracker-client"

# AWS Certificates (Update paths)
CA_CERT = "./certs/AmazonRootCA1.pem"
CERT_FILE = "./certs/certificate.pem.crt"
KEY_FILE = "./certs/private.pem.key"

for file in [CA_CERT, CERT_FILE, KEY_FILE]:
    if not os.path.isfile(file):
        logger.error(f"Error: {file} not found!")
        exit(1)

# Serial Port Configuration for SIM7600X
SERIAL_PORT = "/dev/ttyUSB2"
BAUD_RATE = 115200

# Function to Convert DMM to Decimal Degrees (DD)
def dmm_to_dd(dmm, direction):
    if not dmm:
        return None

    degrees = int(dmm[:-7])  # Extract degrees (everything before the last 7 chars)
    minutes = float(dmm[-7:]) / 60  # Convert minutes to decimal

    decimal_degrees = degrees + minutes

    # Apply sign for South and West
    if direction in ['S', 'W']:
        decimal_degrees = -decimal_degrees

    return round(decimal_degrees, 6)  # Round to 6 decimal places

# Function to Read GPS Data from SIM7600X
def get_gps(ser):
    ser.write(b'AT+CGPSINFO\r')
    time.sleep(1)
    response = ser.readlines()

    for line in response:
        if b'+CGPSINFO:' in line:
            gps_data = line.decode().strip().split(":")[1].split(",")

            if len(gps_data) >= 8 and gps_data[0] and gps_data[2]:  # Ensure valid GPS data
                latitude = dmm_to_dd(gps_data[0], gps_data[1])
                longitude = dmm_to_dd(gps_data[2], gps_data[3])
                altitude = float(gps_data[6]) if gps_data[6] else None  # Altitude in meters
                speed_knots = float(gps_data[7]) if gps_data[7] else 0.0  # Speed in knots
                speed_kmh = round(speed_knots * 1.852, 2)  # Convert knots to km/h

                return {
                    "lat": latitude,
                    "lon": longitude,
                    "altitude": altitude,
                    "speed_kmh": speed_kmh
                }

    return None

# MQTT Callback Functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to AWS IoT Core")
    else:
        logger.error(f"Failed to connect to AWS IoT Core, return code {rc}")

def on_publish(client, userdata, mid):
    logger.info(f"Message {mid} successfully published")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning(f"Disconnected unexpectedly, return code {rc}")
    else:
        logger.info("Disconnected from AWS IoT Core")

# Setup MQTT Client
client = mqtt.Client(client_id=MQTT_CLIENT)
client.tls_set(CA_CERT, certfile=CERT_FILE, keyfile=KEY_FILE, tls_version=ssl.PROTOCOL_TLSv1_2)
client.on_connect = on_connect
client.on_publish = on_publish
client.on_disconnect = on_disconnect

# Connect to AWS IoT
logger.info("Attempting to connect to AWS IoT...")
client.connect(AWS_ENDPOINT, MQTT_PORT, 60)
client.loop_start()
time.sleep(2)  # Allow time for connection

# Open Serial Connection to SIM7600X
ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=1)

local_timezone = pytz.timezone('Australia/Perth')  # You can change this to your specific local timezone

# Define your device_id (this can be dynamically set if needed)
device_id = "gps-tracker-01"  # Replace with your actual device ID

# Main Loop to Publish GPS Data
try:
    while True:
        gps = get_gps(ser)

        if gps:
            local_time = datetime.now(local_timezone).strftime("%Y-%m-%d %H:%M:%S")  # Format as desired
            gps['timestamp'] = local_time
            gps['device_id'] = device_id  # Add device_id to the data
            
            logger.info(f"Sending GPS data: {gps}")
            # Publish GPS Data to AWS IoT Core
            client.publish(MQTT_TOPIC, json.dumps(gps))
        
        else:
            logger.warning("Failed to get GPS data.")

        time.sleep(5)  # Send data every 5 seconds

except KeyboardInterrupt:
    logger.info("Exiting...")
    ser.close()
    client.loop_stop()
    client.disconnect()
