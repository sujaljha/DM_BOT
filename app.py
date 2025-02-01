from flask import Flask, request, jsonify
import requests
import os
from transformers import pipeline
from langdetect import detect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize AI model
chatbot = pipeline("text-generation", model="facebook/mbart-large-50")

# =================================
# Convert Short-Lived to Long-Lived Token
# =================================
@app.route('/convert-token', methods=['GET'])
def convert_token():
    short_token = request.args.get('short_token')
    
    if not short_token:
        return jsonify({"error": "Missing 'short_token' parameter"}), 400
    
    # Facebook API endpoint
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": os.getenv("APP_ID"),
        "client_secret": os.getenv("APP_SECRET"),
        "fb_exchange_token": short_token
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        long_token = response.json().get('access_token')
        return jsonify({
            "long_lived_token": long_token,
            "expires_in": response.json().get('expires_in')  # Usually 5184000 seconds (60 days)
        })
    else:
        return jsonify({"error": "Token conversion failed", "details": response.text}), 400

# ======================
# INSTAGRAM API HANDLERS
# ======================
def send_reply(sender_id: str, message: str) -> dict:
    """Send reply via Instagram API"""
    url = f"https://graph.facebook.com/v18.0/{os.getenv('USER_ID')}/messages"
    params = {"access_token": os.getenv("INSTAGRAM_TOKEN")}
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message}
    }
    return requests.post(url, json=payload, params=params).json()

# ======================
# AI RESPONSE GENERATOR
# ======================
def generate_response(text: str) -> str:
    """Generate multilingual reply"""
    try:
        lang = detect(text)
    except:
        lang = "en"
    
    # Force response in detected language
    response = chatbot(
        text,
        max_length=100,
        num_return_sequences=1,
        forced_bos_token_id=chatbot.tokenizer.lang_code_to_id[f"{lang}_XX"]
    )
    return response[0]['generated_text']

# ======================
# WEBHOOK ENDPOINTS
# ======================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook subscription"""
    if request.args.get("hub.verify_token") == os.getenv("VERIFY_TOKEN"):
        return request.args.get("hub.challenge")
    return "Invalid verification token", 403

@app.route('/webhook', methods=['POST'])
def handle_message():
    """Process incoming DMs"""
    try:
        data = request.json
        message = data['entry'][0]['messaging'][0]['message']['text']
        sender_id = data['entry'][0]['messaging'][0]['sender']['id']
        
        # Generate and send reply
        reply = generate_response(message)
        send_reply(sender_id, reply)
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error"}), 400



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)