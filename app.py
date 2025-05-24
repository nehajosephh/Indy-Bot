import sqlite3
from flask import Flask, render_template, request, jsonify, session
import json
from datetime import datetime
import requests
import logging
import re
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('indiana_chatbot.db')
    c = conn.cursor()
    
    # Hazard reports table
    c.execute('''CREATE TABLE IF NOT EXISTS hazard_reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  location TEXT, 
                  hazard_type TEXT, 
                  description TEXT,
                  contact_info TEXT,
                  status TEXT DEFAULT 'pending',
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Feedback table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  feedback_text TEXT,
                  rating INTEGER,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Chat logs for analytics - check if session_id column exists
    c.execute('''CREATE TABLE IF NOT EXISTS chat_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_message TEXT,
                  bot_response TEXT,
                  intent TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Add session_id column if it doesn't exist (for existing databases)
    try:
        c.execute("ALTER TABLE chat_logs ADD COLUMN session_id TEXT")
        logger.info("Added session_id column to chat_logs table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.debug("session_id column already exists")
        else:
            logger.error(f"Error adding session_id column: {e}")
    
    conn.commit()
    conn.close()

init_db()

# Rasa API endpoint
RASA_API_URL = "http://localhost:5006/webhooks/rest/webhook"

# Indiana-specific safety tips database
SAFETY_TIPS = {
    "winter": [
        "Keep emergency supplies in your car: blankets, water, snacks, and a flashlight.",
        "Check road conditions on INDOT's website before traveling during winter weather.",
        "Clear snow from your vehicle's exhaust pipe to prevent carbon monoxide poisoning.",
        "Dress in layers and cover exposed skin during extreme cold warnings."
    ],
    "tornado": [
        "Indiana's tornado season peaks from April to June. Have a weather radio ready.",
        "Identify the safest room in your home - lowest floor, interior room, away from windows.",
        "If driving during a tornado warning, do not try to outrun it. Seek shelter immediately.",
        "Sign up for emergency alerts through your county's emergency management system."
    ],
    "flooding": [
        "Never drive through flooded roads. Turn around, don't drown.",
        "Indiana rivers can rise quickly during heavy rains. Stay informed about flood warnings.",
        "Keep important documents in waterproof containers.",
        "Know your evacuation routes if you live in a flood-prone area."
    ],
    "fire": [
        "Check smoke detector batteries monthly and replace detectors every 10 years.",
        "Create and practice a fire escape plan with your family.",
        "Keep fire extinguishers in key areas: kitchen, garage, and basement.",
        "During burn bans, avoid outdoor burning and report violations to local authorities."
    ],
    "general": [
        "Know your county's emergency management contact information.",
        "Keep a 3-day emergency supply kit for each family member.",
        "Stay informed through Indiana Emergency Management Agency alerts.",
        "Register for your county's emergency notification system."
    ]
}

# Indiana counties for location validation
INDIANA_COUNTIES = [
    "Adams", "Allen", "Bartholomew", "Benton", "Blackford", "Boone", "Brown", "Carroll",
    "Cass", "Clark", "Clay", "Clinton", "Crawford", "Daviess", "Dearborn", "Decatur",
    "DeKalb", "Delaware", "Dubois", "Elkhart", "Fayette", "Floyd", "Fountain", "Franklin",
    "Fulton", "Gibson", "Grant", "Greene", "Hamilton", "Hancock", "Harrison", "Hendricks",
    "Henry", "Howard", "Huntington", "Jackson", "Jasper", "Jay", "Jefferson", "Jennings",
    "Johnson", "Knox", "Kosciusko", "LaGrange", "Lake", "LaPorte", "Lawrence", "Madison",
    "Marion", "Marshall", "Martin", "Miami", "Monroe", "Montgomery", "Morgan", "Newton",
    "Noble", "Ohio", "Orange", "Owen", "Parke", "Perry", "Pike", "Porter", "Posey",
    "Pulaski", "Putnam", "Randolph", "Ripley", "Rush", "Scott", "Shelby", "Spencer",
    "St. Joseph", "Starke", "Steuben", "Sullivan", "Switzerland", "Tippecanoe", "Tipton",
    "Union", "Vanderburgh", "Vermillion", "Vigo", "Wabash", "Warren", "Warrick",
    "Washington", "Wayne", "Wells", "White", "Whitley"
]

# Conversation state management
class ConversationState:
    def __init__(self):
        self.awaiting_location = False
        self.awaiting_hazard_type = False
        self.awaiting_hazard_description = False
        self.current_hazard_type = None
        self.current_location = None
        self.current_description = None
        self.last_intent = None
        
def get_conversation_state():
    """Get or create conversation state for this session"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    if 'conversation_state' not in session:
        session['conversation_state'] = {
            'awaiting_location': False,
            'awaiting_hazard_type': False,
            'awaiting_hazard_description': False,
            'current_hazard_type': None,
            'current_location': None,
            'current_description': None,
            'last_intent': None
        }
    
    return session['conversation_state']

def update_conversation_state(**kwargs):
    """Update conversation state"""
    state = get_conversation_state()
    for key, value in kwargs.items():
        state[key] = value
    session['conversation_state'] = state

def reset_conversation_state():
    """Reset conversation state"""
    session['conversation_state'] = {
        'awaiting_location': False,
        'awaiting_hazard_type': False,
        'awaiting_hazard_description': False,
        'current_hazard_type': None,
        'current_location': None,
        'current_description': None,
        'last_intent': None
    }

def extract_location_and_hazard(message):
    """Extract location and hazard type from user message"""
    message_lower = message.lower()
    
    # Common hazard keywords
    hazard_types = {
        'pothole': ['pothole', 'potholes', 'road damage', 'street damage', 'hole in road'],
        'power_outage': ['power out', 'power outage', 'electricity', 'blackout', 'no power'],
        'water_main': ['water main', 'water leak', 'flooding', 'burst pipe', 'water problem'],
        'traffic_light': ['traffic light', 'stop light', 'signal', 'intersection', 'light out'],
        'debris': ['debris', 'fallen tree', 'obstruction', 'blocked road', 'tree down'],
        'ice': ['ice', 'icy road', 'slippery', 'black ice', 'icy conditions'],
        'fire': ['fire', 'smoke', 'burning', 'flames'],
        'other': ['hazard', 'danger', 'unsafe', 'problem', 'issue']
    }
    
    detected_hazard = None
    for hazard, keywords in hazard_types.items():
        if any(keyword in message_lower for keyword in keywords):
            detected_hazard = hazard
            break
    
    # Extract location (look for county names, cities, street addresses)
    detected_location = None
    for county in INDIANA_COUNTIES:
        if county.lower() in message_lower:
            detected_location = f"{county} County"
            break
    
    # Look for street patterns
    street_pattern = r'\b\d+\s+[A-Za-z\s]+(?:street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|lane|ln)\b'
    street_match = re.search(street_pattern, message, re.IGNORECASE)
    if street_match:
        detected_location = street_match.group()
    
    # Look for intersection patterns
    intersection_pattern = r'\b[A-Za-z\s]+(?:street|st|avenue|ave|road|rd)\s+(?:and|&|\bat\b)\s+[A-Za-z\s]+(?:street|st|avenue|ave|road|rd)\b'
    intersection_match = re.search(intersection_pattern, message, re.IGNORECASE)
    if intersection_match:
        detected_location = intersection_match.group()
    
    return detected_location, detected_hazard

def handle_emergency_response(message):
    """Handle emergency situations"""
    message_lower = message.lower()
    emergency_keywords = ['emergency', 'urgent', '911', 'help', 'immediate', 'now']
    
    if any(keyword in message_lower for keyword in emergency_keywords):
        if any(fire_word in message_lower for fire_word in ['fire', 'burning', 'smoke', 'flames']):
            return "🚨 EMERGENCY: If this is an active fire emergency, call 911 immediately! Do not delay. If this is a non-emergency fire hazard report, I can help you document it."
        elif any(medical_word in message_lower for medical_word in ['hurt', 'injured', 'accident', 'medical']):
            return "🚨 EMERGENCY: If someone is injured or this is a medical emergency, call 911 immediately! For non-emergency situations, I can help you find local resources."
    
    return None

def handle_hazard_reporting_flow(message):
    """Handle the step-by-step hazard reporting process"""
    state = get_conversation_state()
    message_lower = message.lower()
    
    # Check if user wants to cancel
    if any(word in message_lower for word in ['cancel', 'stop', 'nevermind', 'quit']):
        reset_conversation_state()
        return "Hazard reporting cancelled. How else can I help you today?"
    
    # If we're waiting for location
    if state['awaiting_location']:
        location, _ = extract_location_and_hazard(message)
        if location:
            update_conversation_state(
                current_location=location,
                awaiting_location=False,
                awaiting_hazard_description=True
            )
            return f"Great! I have the location as {location}. Now, can you provide more details about the {state['current_hazard_type'].replace('_', ' ')}? For example, size, severity, or any other important details."
        else:
            return "I couldn't identify a specific location. Could you please provide a street address, intersection, or county name? For example: 'Main Street and 1st Avenue' or 'Marion County'."
    
    # If we're waiting for hazard type
    if state['awaiting_hazard_type']:
        _, hazard_type = extract_location_and_hazard(message)
        if hazard_type:
            update_conversation_state(
                current_hazard_type=hazard_type,
                awaiting_hazard_type=False,
                awaiting_location=True
            )
            return f"Thank you! I understand you're reporting a {hazard_type.replace('_', ' ')}. What's the location? Please provide a street address, intersection, or county name."
        else:
            return "What type of hazard are you reporting? For example: pothole, power outage, debris, traffic light issue, water main break, etc."
    
    # If we're waiting for description
    if state['awaiting_hazard_description']:
        # Save the complete report
        conn = sqlite3.connect('indiana_chatbot.db')
        c = conn.cursor()
        report_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        c.execute("INSERT INTO hazard_reports (location, hazard_type, description) VALUES (?, ?, ?)", 
                 (state['current_location'], state['current_hazard_type'], message))
        conn.commit()
        conn.close()
        
        response = f"✅ Thank you! Your {state['current_hazard_type'].replace('_', ' ')} report has been submitted:\n\n"
        response += f"📍 Location: {state['current_location']}\n"
        response += f"⚠️ Hazard: {state['current_hazard_type'].replace('_', ' ')}\n"
        response += f"📋 Details: {message}\n"
        response += f"🆔 Report ID: {report_id}\n\n"
        response += "Your report will be forwarded to the appropriate local authorities. Is there anything else I can help you with?"
        
        reset_conversation_state()
        return response
    
    return None

def initiate_hazard_report(message):
    """Start the hazard reporting process"""
    location, hazard_type = extract_location_and_hazard(message)
    
    # If we have both location and hazard type from the initial message
    if location and hazard_type:
        update_conversation_state(
            current_location=location,
            current_hazard_type=hazard_type,
            awaiting_hazard_description=True
        )
        return f"I can help you report that {hazard_type.replace('_', ' ')} at {location}. Can you provide more details about the hazard? For example, size, severity, or any other important information."
    
    # If we only have location
    elif location and not hazard_type:
        update_conversation_state(
            current_location=location,
            awaiting_hazard_type=True
        )
        return f"I see this is about {location}. What type of hazard are you reporting? (pothole, power outage, debris, traffic light issue, etc.)"
    
    # If we only have hazard type
    elif hazard_type and not location:
        update_conversation_state(
            current_hazard_type=hazard_type,
            awaiting_location=True
        )
        return f"I can help you report that {hazard_type.replace('_', ' ')}. What's the location? Please provide a street address, intersection, or county name."
    
    # If we have neither
    else:
        update_conversation_state(awaiting_hazard_type=True)
        return "I'd be happy to help you report a hazard. What type of hazard are you reporting? For example: pothole, power outage, debris, traffic light issue, water main break, etc."

def get_safety_tips(category=None):
    """Get safety tips based on category"""
    if category:
        category = category.lower()
        if category in SAFETY_TIPS:
            tips = SAFETY_TIPS[category]
            return f"Here are some {category} safety tips for Indiana residents:\n\n" + "\n\n".join([f"• {tip}" for tip in tips])
    
    # Return general tips if no specific category
    tips = SAFETY_TIPS["general"]
    return "Here are some general safety tips for Indiana residents:\n\n" + "\n\n".join([f"• {tip}" for tip in tips])

def get_indiana_info(query):
    """Provide Indiana-specific information"""
    query_lower = query.lower()
    
    if any(word in query_lower for word in ['weather', 'forecast', 'storm']):
        return "For current weather conditions and forecasts in Indiana, visit weather.gov or download the National Weather Service app. During severe weather, tune to local news or weather radio for updates."
    
    if any(word in query_lower for word in ['road', 'traffic', 'construction', 'indot']):
        return "For current road conditions, construction updates, and traffic information in Indiana, visit INDOT's website at in.gov/indot or call 511. You can also download the INDOT app for real-time updates."
    
    if any(word in query_lower for word in ['county', 'government', 'services']):
        return "Indiana has 92 counties, each with their own local government services. You can find your county's website and contact information through in.gov. What specific service are you looking for?"
    
    return None

def simple_chatbot_response(message):
    """Handle simple conversations and queries with improved state management"""
    state = get_conversation_state()
    message_lower = message.lower()
    
    # Handle emergency situations first
    emergency_response = handle_emergency_response(message)
    if emergency_response:
        return emergency_response
    
    # Check if user wants to switch topics (exit hazard reporting)
    topic_switch_keywords = ['safety tips', 'help', 'weather', 'road conditions', 'government', 'services', 'what can you do']
    if any(keyword in message_lower for keyword in topic_switch_keywords):
        reset_conversation_state()  # Clear any ongoing flows
    
    # Handle ongoing hazard reporting flow ONLY if we're in that flow and user isn't switching topics
    if any([state['awaiting_location'], state['awaiting_hazard_type'], state['awaiting_hazard_description']]):
        # Allow users to break out of hazard reporting flow
        if not any(keyword in message_lower for keyword in topic_switch_keywords):
            flow_response = handle_hazard_reporting_flow(message)
            if flow_response:
                return flow_response
    
    # Indiana-specific queries - EXPLICIT handling
    indiana_response = get_indiana_info(message)
    if indiana_response:
        reset_conversation_state()  # Clear any ongoing flows
        update_conversation_state(last_intent='indiana_info')
        return indiana_response
    
    # Greetings - EXPLICIT handling
    greeting_phrases = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
    if any(phrase in message_lower for phrase in greeting_phrases) and len(message.split()) <= 3:
        reset_conversation_state()  # Clear any ongoing flows
        update_conversation_state(last_intent='greeting')
        return "Hello! I'm the Indiana Citizens Assistant. I can help you report hazards, get safety tips, find government services, or just chat. What can I help you with today?"
    
    # Hazard reporting initiation - ONLY if not already in a flow
    if not any([state['awaiting_location'], state['awaiting_hazard_type'], state['awaiting_hazard_description']]):
        if any(word in message_lower for word in ['report', 'hazard', 'pothole', 'problem', 'issue', 'danger', 'broken']):
            update_conversation_state(last_intent='hazard_report')
            return initiate_hazard_report(message)
    
    # Safety tips requests - EXPLICIT handling
    if any(phrase in message_lower for phrase in ['safety tips', 'safety tip', 'give me safety', 'safety advice', 'safety information']):
        reset_conversation_state()  # Clear any ongoing flows
        update_conversation_state(last_intent='safety_tips')
        if 'winter' in message_lower or 'cold' in message_lower or 'snow' in message_lower:
            return get_safety_tips('winter')
        elif 'tornado' in message_lower or 'twister' in message_lower:
            return get_safety_tips('tornado')
        elif 'flood' in message_lower or 'flooding' in message_lower:
            return get_safety_tips('flooding')
        elif 'fire' in message_lower:
            return get_safety_tips('fire')
        else:
            return get_safety_tips()
    
    # Help requests - EXPLICIT handling
    if any(phrase in message_lower for phrase in ['help', 'what can you do', 'commands', 'options', 'how can you help']):
        reset_conversation_state()  # Clear any ongoing flows
        update_conversation_state(last_intent='help')
        return """I can help you with:

• **Report hazards** - potholes, power outages, debris, traffic issues, etc.
• **Get safety tips** - weather emergencies, fire safety, general preparedness
• **Find Indiana services** - government contacts, road conditions, weather info
• **Emergency guidance** - what to do in various situations

Just tell me what you need help with! For example:
- "I want to report a pothole"
- "Give me tornado safety tips"
- "What's the road conditions?"
"""
    
    # Thank you responses
    if any(word in message_lower for word in ['thank', 'thanks', 'appreciate']):
        return "You're welcome! I'm here whenever you need help with safety information or hazard reporting. Stay safe!"
    
    # Default response based on context
    if state['last_intent'] == 'hazard_report':
        return "If you'd like to report a hazard, just tell me what and where. For example: 'There's a large pothole on Main Street' or 'Power is out in Marion County'."
    elif state['last_intent'] == 'safety_tips':
        return "What type of safety information are you looking for? I can provide tips for winter weather, tornadoes, flooding, fire safety, or general emergency preparedness."
    else:
        return "I'm here to help Indiana residents with safety, hazard reporting, and local information. You can ask me to report a hazard, get safety tips, or find information about Indiana services. What would you like help with?"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_input = request.json.get("message")
        logger.debug(f"Received message: {user_input}")
        
        # Initialize session if needed
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Try Rasa first, fall back to simple chatbot
        bot_response = None
        intent = "unknown"
        
        try:
            logger.debug(f"Sending request to Rasa at {RASA_API_URL}")
            rasa_response = requests.post(
                RASA_API_URL,
                json={"message": user_input},
                timeout=5
            )
            rasa_response.raise_for_status()
            rasa_response_json = rasa_response.json()
            logger.debug(f"Rasa response: {rasa_response_json}")
            
            if rasa_response_json and len(rasa_response_json) > 0:
                bot_response = rasa_response_json[0].get("text", "")
                intent = rasa_response_json[0].get("intent", {}).get("name", "unknown")
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Rasa unavailable, using fallback: {str(e)}")
        
        # Use simple chatbot if Rasa fails or returns empty response
        if not bot_response:
            bot_response = simple_chatbot_response(user_input)
            intent = "fallback"
        
        # Log the conversation
        conn = sqlite3.connect('indiana_chatbot.db')
        c = conn.cursor()
        
        # Check if session_id column exists before using it
        try:
            c.execute("INSERT INTO chat_logs (user_message, bot_response, intent, session_id) VALUES (?, ?, ?, ?)", 
                     (user_input, bot_response, intent, session.get('session_id')))
        except sqlite3.OperationalError:
            # Fallback to old schema if session_id column doesn't exist
            c.execute("INSERT INTO chat_logs (user_message, bot_response, intent) VALUES (?, ?, ?)", 
                     (user_input, bot_response, intent))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Sending response: {bot_response}")
        return jsonify({"response": bot_response})
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"response": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment."}), 500

@app.route("/feedback", methods=["POST"])
def feedback():
    try:
        data = request.json
        feedback_text = data.get("feedback", "")
        rating = data.get("rating", None)
        
        conn = sqlite3.connect('indiana_chatbot.db')
        c = conn.cursor()
        c.execute("INSERT INTO feedback (feedback_text, rating) VALUES (?, ?)", 
                 (feedback_text, rating))
        conn.commit()
        conn.close()
        
        return jsonify({"response": "Thank you for your feedback! It helps us improve our service for Indiana residents."})
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        return jsonify({"response": "Thank you for your feedback!"}), 200

@app.route("/reports", methods=["GET"])
def get_reports():
    """Endpoint for authorities to view hazard reports"""
    try:
        conn = sqlite3.connect('indiana_chatbot.db')
        c = conn.cursor()
        c.execute("SELECT * FROM hazard_reports ORDER BY timestamp DESC LIMIT 50")
        reports = c.fetchall()
        conn.close()
        
        report_list = []
        for report in reports:
            report_list.append({
                'id': report[0],
                'location': report[1],
                'hazard_type': report[2],
                'description': report[3],
                'contact_info': report[4],
                'status': report[5],
                'timestamp': report[6]
            })
        
        return jsonify({"reports": report_list})
    except Exception as e:
        logger.error(f"Error fetching reports: {str(e)}")
        return jsonify({"error": "Unable to fetch reports"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)