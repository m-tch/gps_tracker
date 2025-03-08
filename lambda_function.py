import json
import decimal
import logging
import boto3
from decimal import Decimal

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB Client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('GPSData')

# Convert Decimal to float for JSON serialization
def decimal_serializer(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError("Type not serializable")

def lambda_handler(event, context):
    try:
        # Extract data from the event (assuming it contains lat, lon, altitude, speed, timestamp, device_id)
        device_id = event.get('device_id')  # Assuming device_id is passed in the event
        lat = event.get('lat')
        lon = event.get('lon')
        altitude = event.get('altitude')
        speed = event.get('speed_kmh', 'N/A')  # Default 'N/A' if speed is not provided
        timestamp = event.get('timestamp')

        # Log the received data
        logger.info(f"Received data: device_id={device_id}, Latitude={lat}, Longitude={lon}, Altitude={altitude}, Speed={speed}, Timestamp={timestamp}")

        # Prepare the item to store in DynamoDB
        item = {
            'device_id': device_id,  # Include the device_id
            'timestamp': timestamp,
            'lat': decimal.Decimal(str(lat)),  # Ensure it's a Decimal for DynamoDB
            'lon': decimal.Decimal(str(lon)),  # Ensure it's a Decimal for DynamoDB
            'altitude': decimal.Decimal(str(altitude)),  # Ensure it's a Decimal for DynamoDB
            'speed': decimal.Decimal(str(speed)) if isinstance(speed, (int, float)) else speed,  # Handle speed safely
        }

        # Log the item to be stored
        logger.info(f"Storing item in DynamoDB: {item}")

        # Store the item in DynamoDB
        table.put_item(Item=item)

        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "GPS data stored successfully!", "data": item}, default=decimal_serializer),
        }

    except Exception as e:
        # Log error if any
        logger.error(f"Error storing data: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Error storing data", "error": str(e)})
        }
