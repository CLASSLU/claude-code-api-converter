import json
import os
import logging
import requests
import sys
from flask import Flask, request, jsonify

# --- Logging Setup (Basic) ---
# Configure logging as early as possible to capture all messages.
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Configuration Loading ---
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    """Loads configuration from config.json or provides defaults, with robust merging."""
    default_config = {
        "openai": {
            "api_key": "YOUR_ANTHROPIC_TO_OPENAI_API_KEY", # Placeholder for security check
            "base_url": "https://api.openai.com/v1"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8081,  # Designated parallel testing port
            "debug": False,
            "request_timeout": 120 # Default timeout for backend API calls in seconds
        }
    }

    config = default_config.copy() # Start with all defaults

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            logger.info(f"Successfully loaded configuration from {CONFIG_FILE_PATH}")

            # Deep merge strategy: Update default dictionaries with user-provided values
            for key in default_config:
                if key in user_config:
                    if isinstance(config[key], dict) and isinstance(user_config[key], dict):
                        config[key].update(user_config[key])
                    else: # For non-dict items, directly override
                        config[key] = user_config[key]

    except FileNotFoundError:
        logger.warning(f"Config file not found at {CONFIG_FILE_PATH}. Using default configuration.")
        # Attempt to create a default config file for easier setup
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Created a default config file at {CONFIG_FILE_PATH}. Please update 'api_key'.")
        except Exception as e:
            logger.error(f"Could not write default config file to {CONFIG_FILE_PATH}: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding config file {CONFIG_FILE_PATH}: {e}. Using default configuration.")
    except Exception as e: # Catch other potential file errors like permission denied
        logger.error(f"An unexpected error occurred while loading config file {CONFIG_FILE_PATH}: {e}. Using default configuration.")

    # --- Critical Configuration Checks ---
    if config['openai']['api_key'] == default_config['openai']['api_key']:
        logger.critical(
            "API key is still the default placeholder ('YOUR_ANTHROPIC_TO_OPENAI_API_KEY'). "
            "Please update 'openai.api_key' in 'config.json' or set the "
            "ANTHROPIC_TO_OPENAI_API_KEY environment variable. Exiting."
        )
        sys.exit(1)

    return config

# Load configuration at startup
app_config = load_config()

# Extract essential configuration parameters
OPENAI_API_KEY = os.environ.get('ANTHROPIC_TO_OPENAI_API_KEY', app_config['openai']['api_key'])
OPENAI_BASE_URL = app_config['openai']['base_url']
SERVER_HOST = app_config['server']['host']
SERVER_PORT = app_config['server']['port']
SERVER_DEBUG = app_config['server']['debug']
REQUEST_TIMEOUT = app_config['server']['request_timeout']

# --- Flask Application Initialization ---
app = Flask(__name__)

# Import the LightweightConverter (aliased for clarity)
# This assumes lightweight_converter/converter.py exists and contains AnthropicToOpenAIConverter
converter = None
try:
    from .converter import AnthropicToOpenAIConverter as LightweightConverter
    converter = LightweightConverter()
    logger.info("LightweightConverter initialized successfully.")
except ImportError as e:
    logger.critical(f"Failed to import LightweightConverter: {e}. Ensure 'converter.py' is present in lightweight_converter/ directory. Server cannot start.")
    sys.exit(1)
except Exception as e:
    logger.critical(f"An unexpected error occurred during LightweightConverter initialization: {e}. Server cannot start.")
    sys.exit(1)


# --- Endpoints ---

@app.route('/v1/messages', methods=['POST'])
def messages_conversion_endpoint():
    """
    Handles POST requests to /v1/messages.
    Converts Anthropic-style requests to OpenAI, calls OpenAI API,
    and converts the response back to Anthropic format.
    Adheres to "快速失败" and "原始信息返回" principles.
    """
    if converter is None:
        logger.error("Converter is not initialized; this should have been caught at startup.")
        return jsonify({'error': 'Server misconfiguration: Converter not available.'}), 500

    try:
        # 1. Parse incoming Anthropic-style request
        anthropic_request = request.get_json(silent=True) # silent=True returns None on invalid JSON
        if not anthropic_request:
            logger.warning("Received empty or invalid JSON request from client.")
            return jsonify({'error': 'Invalid or empty JSON body.'}), 400

        model_name = anthropic_request.get('model', 'unknown_model')
        logger.info(f"Incoming /v1/messages request for model: {model_name}")

        # 2. Convert to OpenAI format
        openai_request = converter.convert_request(anthropic_request)

        # 3. Call backend OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {OPENAI_API_KEY}'
        }

        backend_url = f'{OPENAI_BASE_URL}/chat/completions'

        logger.debug(f"Calling backend API: {backend_url} with request payload (first 200 chars): {str(openai_request)[:200]}...")
        backend_response = requests.post(
            backend_url,
            headers=headers,
            json=openai_request,
            timeout=REQUEST_TIMEOUT
        )
        backend_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        openai_response_data = backend_response.json()
        logger.debug(f"Received backend response (first 200 chars): {str(openai_response_data)[:200]}...")

        # 4. Convert backend response to Anthropic format
        anthropic_response = converter.convert_response(openai_response_data)

        # The converter is expected to handle model mapping consistently.
        # No additional model field overwrite here as it implies a converter bug if needed.

        logger.info(f"Successfully processed /v1/messages request for model: {model_name}")
        return jsonify(anthropic_response)

    except json.JSONDecodeError:
        # This specific JSONDecodeError is for the *backend response*, not the incoming request
        logger.exception("Failed to decode JSON from backend API response.")
        return jsonify({'error': 'Backend API returned invalid JSON.'}), 502 # Bad Gateway
    except requests.exceptions.Timeout:
        logger.error(f"Backend API call timed out after {REQUEST_TIMEOUT} seconds.")
        return jsonify({'error': 'Backend API connection timed out.'}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as e:
        logger.exception(f"Error communicating with backend API: {e}")
        error_message = f"Backend API error: {e}"
        status_code = 502 # Default Bad Gateway for generic request errors

        if e.response is not None:
            status_code = e.response.status_code
            try:
                error_json = e.response.json()
                # Attempt to extract a more specific error message from the backend
                if 'error' in error_json and 'message' in error_json['error']:
                    error_message = error_json['error']['message']
                elif 'detail' in error_json:
                    error_message = error_json['detail']
                elif 'message' in error_json:
                    error_message = error_json['message']
                # If specific 429 error, pass it directly
                if status_code == 429:
                    logger.warning(f"Backend API returned 429 Rate Limit: {error_message}")
            except json.JSONDecodeError:
                error_message = e.response.text # Fallback to raw text if not JSON
            except Exception as parse_e:
                logger.warning(f"Could not parse backend error response JSON or text: {parse_e}")
                error_message = e.response.text if e.response.text else f"Backend API returned status {status_code} with unparsable error."
        else:
            # No response object, indicating network error or DNS failure before HTTP
            error_message = f"Network or connection error to backend API: {e}"

        return jsonify({'error': error_message}), status_code
    except Exception as e:
        logger.exception(f"An unexpected internal server error occurred: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# --- Server Startup ---
if __name__ == '__main__':
    # The converter check is now done at import time and will exit if failed.
    logger.info(f"Starting Lightweight Converter server on http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Targeting OpenAI API at: {OPENAI_BASE_URL}")
    logger.info(f"Backend API request timeout set to: {REQUEST_TIMEOUT} seconds")
    logger.info("Only '/v1/messages' POST endpoint is active.")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG, use_reloader=False)