#!/usr/bin/env python3
import os
import json
import datetime
import uuid
import logging
from flask import Flask, jsonify, request
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# PostgreSQL connection parameters from environment variables
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')

def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        connection.autocommit = True
        return connection
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

def init_db():
    """Initialize the database by creating the required table if it doesn't exist"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sample_data (
                        id UUID PRIMARY KEY,
                        message TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        data JSONB
                    )
                """)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
        finally:
            conn.close()
    else:
        logger.error("Could not initialize database - connection failed")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes probes"""
    try:
        # Try to connect to the database to verify health
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({"status": "healthy", "database": "connected"}), 200
        else:
            return jsonify({"status": "unhealthy", "database": "disconnected"}), 500
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """API endpoint to retrieve data from the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sample_data ORDER BY created_at DESC LIMIT 100")
            data = cur.fetchall()
            
        conn.close()
        
        # Convert data to list of dicts for JSON serialization
        result = []
        for row in data:
            # Convert datetime objects to ISO format strings
            item = dict(row)
            if 'created_at' in item and isinstance(item['created_at'], datetime.datetime):
                item['created_at'] = item['created_at'].isoformat()
            result.append(item)
            
        return jsonify({"data": result}), 200
    except Exception as e:
        logger.error(f"Error retrieving data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/data', methods=['POST'])
def add_data():
    """API endpoint to add new data to the database"""
    try:
        # Get JSON data from request
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "No data provided"}), 400
        
        message = request_data.get('message', 'No message provided')
        data = request_data.get('data', {})
        
        # Generate a UUID for the new record
        record_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO sample_data (id, message, data) VALUES (%s, %s, %s) RETURNING id, created_at"),
                (record_id, message, json.dumps(data))
            )
            result = cur.fetchone()
            
        conn.close()
        
        # Build the response
        response = {
            "id": record_id,
            "message": message,
            "created_at": result['created_at'].isoformat() if result else None,
            "data": data
        }
        
        logger.info(f"Added new data with ID: {record_id}")
        return jsonify(response), 201
    except Exception as e:
        logger.error(f"Error adding data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Simple root endpoint to verify the application is running"""
    env_info = {
        "app": "Sample EKS PostgreSQL App",
        "version": "1.0.0",
        "db_host": DB_HOST,
        "db_name": DB_NAME,
        "endpoints": {
            "health": "/health",
            "get_data": "/api/data (GET)",
            "add_data": "/api/data (POST)",
        }
    }
    return jsonify(env_info), 200

if __name__ == '__main__':
    # Initialize the database when the application starts
    init_db()
    
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 8080))
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=port) 