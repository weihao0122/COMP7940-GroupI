from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, 
                CallbackContext, ConversationHandler, CallbackQueryHandler)
from telegram.error import Conflict, TelegramError
from ChatGPT_HKBU import HKBU_ChatGPT
from db_helper import DBHelper
from config_manager import ConfigManager
import configparser
import logging
from datetime import datetime
import json
from bson import ObjectId 
from colorama import init, Fore, Back, Style

# Initialize colorama
init()

# Define custom symbols
SUCCESS = "[ OK ]"
ERROR = "[FAIL]"
INFO = "[INFO]"
BULLET = "-"

# Define conversation states
CHOOSING_ACTION, CREATING_EVENT, SETTING_PREFERENCES = range(3)

def main():
    try:
        print(f"{INFO} Starting Event Management Bot")
        print(f"{INFO} Loading configuration from Azure Key Vault...")
        
        # Initialize config manager
        config_manager = ConfigManager()
        config = config_manager.get_config()
        print(f"{SUCCESS} Configuration loaded from Key Vault")
        
        # Configure logging
        logging.basicConfig(
            format='%(asctime)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        print(f"{SUCCESS} Logging configured")
        
        print(f"{INFO} Initializing components...")
        
        # Initialize bot
        updater = Updater(token=config['TELEGRAM']['ACCESS_TOKEN'], use_context=True)
        dispatcher = updater.dispatcher
        print(f"{SUCCESS} Telegram bot initialized")
        
        # Initialize global objects
        global db_helper, chatgpt
        db_helper = DBHelper(config['DATABASE']['MONGODB_URI'])
        print(f"{SUCCESS} Database helper initialized")
        chatgpt = HKBU_ChatGPT(config)
        print(f"{SUCCESS} ChatGPT client initialized")
        
        print(f"{INFO} Setting up handlers...")
        # Add handlers
        dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_message))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("event", event_command))
        dispatcher.add_handler(CommandHandler("join", join_event_command))
        dispatcher.add_handler(CommandHandler("list", list_events_command))
        dispatcher.add_handler(CommandHandler("preferences", preferences_command))
        dispatcher.add_handler(CallbackQueryHandler(button_click))
        print(f"{SUCCESS} Handlers configured")
        
        # Start the bot
        print(f"{INFO} Starting bot service...")
        updater.start_polling(drop_pending_updates=True)
        print(f"{SUCCESS} Bot is now running")
        print(f"{INFO} Press Ctrl+C to stop")
        updater.idle()
        
    except Exception as e:
        print(f"{ERROR} Startup failed: {e}")
    finally:
        if 'db_helper' in globals():
            db_helper.client.close()
            print(f"{INFO} Database connection closed")

def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle user messages"""
    global chatgpt
    
    try:
        message = update.message.text
        
        # Get ChatGPT response
        reply_message = chatgpt.submit(message)
        
        # Send response
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"{SUCCESS} {reply_message}")
    except Exception as e:
        context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"{ERROR} Failed to process message: {str(e)}"
        )
#/help command
def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    help_text = f"""
{INFO} Welcome to Event Management Bot

Available Commands:
{BULLET} /help - Show help information
{BULLET} /event - Create or manage events
{BULLET} /list - View event list
{BULLET} /join <EventID> <ParticipantName> - Join an event
{BULLET} /preferences - Set your preferences

Example: /join 0001 John

{INFO} Tips:
{BULLET} Send messages to chat with the bot
{BULLET} Each event has a 4-digit ID
{BULLET} Use /list to view all events
"""
    update.message.reply_text(help_text)

def event_command(update: Update, context: CallbackContext) -> None:
    """Handle event creation command"""
    keyboard = [
        [InlineKeyboardButton("Create New Event", callback_data='create_event')],
        [InlineKeyboardButton("View My Events", callback_data='list_events')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please select an action:', reply_markup=reply_markup)

def create_event_flow(update: Update, context: CallbackContext) -> None:
    """Guide user through event creation process"""
    global chatgpt, db_helper
    chat_id = update.effective_chat.id
    user = update.effective_user
    creator_name = f"{user.first_name}"
    if user.last_name:
        creator_name += f" {user.last_name}"
    
    # Get user preferences
    user_prefs = db_helper.get_user_preferences(user.id)
    interests = user_prefs.get('interests', []) if user_prefs else []
    timezone = user_prefs.get('timezone', 'UTC+8') if user_prefs else 'UTC+8'
    preferred_times = user_prefs.get('preferred_times', []) if user_prefs else []
    
    # Build a more detailed and personalized prompt
    prompt = f"""Please generate a virtual event suggestion that matches these specific preferences:

User Preferences:
- Interests: {', '.join(interests) if interests else 'Any'}
- Timezone: {timezone}
- Preferred Times: {', '.join(preferred_times) if preferred_times else 'Any'}

Requirements:
1. The event type should match one of the user's interests
2. The event time should be in {timezone} timezone
3. The event should be scheduled during user's preferred times: {', '.join(preferred_times) if preferred_times else 'Any time'}
4. Include detailed agenda with specific times

Return ONLY a JSON object in this format:
{{
    "title": "Event title that matches interests",
    "type": "Event type (should match interests)",
    "duration": "Duration in minutes",
    "description": "Detailed description focusing on user interests",
    "datetime": "YYYY-MM-DD HH:MM in {timezone}",
    "agenda": [
        {{"time": "Start-End", "item": "Agenda item description"}},
        {{"time": "Start-End", "item": "Agenda item description"}},
        {{"time": "Start-End", "item": "Agenda item description"}}
    ]
}}

Example (DO NOT USE DIRECTLY):
{{
    "title": "Tech Innovation Workshop: AI Applications",
    "type": "Technology",
    "duration": "120",
    "description": "An interactive workshop focusing on practical AI applications",
    "datetime": "2024-04-01 14:00",
    "agenda": [
        {{"time": "14:00-14:15", "item": "Welcome and Introduction"}},
        {{"time": "14:15-15:00", "item": "Main Topic Discussion"}},
        {{"time": "15:00-15:15", "item": "Break"}},
        {{"time": "15:15-15:45", "item": "Hands-on Session"}},
        {{"time": "15:45-16:00", "item": "Q&A and Closing"}}
    ]
}}"""
    
    try:
        response = chatgpt.submit(prompt)
        print(f"{INFO} ChatGPT response: {response}")  # Add debug log
        
        # Clean the response - remove any non-JSON text and fix newlines
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
            
        # Fix JSON format issues
        try:
            # First try direct JSON parsing
            event_suggestion = json.loads(response.strip())
        except json.JSONDecodeError:
            # If parsing fails, try cleaning and fixing JSON
            import re
            # Remove all newlines and extra spaces
            response = re.sub(r'\s+', ' ', response).strip()
            # Ensure it's a complete JSON object
            if not response.startswith('{'):
                response = '{' + response
            if not response.endswith('}'):
                response = response + '}'
            event_suggestion = json.loads(response)
        
        # Ensure newline characters are displayed correctly in agenda
        if '\n' in event_suggestion['agenda']:
            event_suggestion['agenda'] = event_suggestion['agenda'].replace('\\n', '\n')
        
        # Ensure all required fields exist
        required_fields = ['title', 'type', 'duration', 'description', 'datetime', 'agenda']
        if not all(field in event_suggestion for field in required_fields):
            raise ValueError("Incomplete response format")
            
        # Validate data types
        if not isinstance(event_suggestion['duration'], (int, str)):
            event_suggestion['duration'] = str(event_suggestion['duration'])
            
        context.user_data['event_draft'] = event_suggestion
        
        message = f"""{INFO} Suggested Event Details:
{BULLET} Event: {event_suggestion['title']}
{BULLET} Type: {event_suggestion['type']}
{BULLET} Time: {event_suggestion['datetime']}
{BULLET} Duration: {event_suggestion['duration']} minutes
{BULLET} Creator: {creator_name}
{BULLET} Current Participants: 1
{BULLET} Participant List: {creator_name}

{INFO} Description: {event_suggestion['description']}

{INFO} Detailed Agenda:"""

        # Add detailed agenda
        for agenda_item in event_suggestion['agenda']:
            message += f"\n{BULLET} {agenda_item['time']}: {agenda_item['item']}"

        message += f"\n\n{INFO} Would you like to create this event?"
        
        keyboard = [
            [InlineKeyboardButton("Confirm", callback_data='confirm_event')],
            [InlineKeyboardButton("Generate Another", callback_data='regenerate_event')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
        else:
            context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
        
    except json.JSONDecodeError as e:
        error_message = f"{ERROR} Error parsing event suggestion: {str(e)}. Please try again."
        print(f"{ERROR} JSON decode error: {str(e)}")  # Add debug log
        if update.callback_query:
            update.callback_query.edit_message_text(text=error_message)
        else:
            context.bot.send_message(chat_id=chat_id, text=error_message)
    except Exception as e:
        error_message = f"{ERROR} Error occurred: {str(e)}"
        print(f"{ERROR} General error: {str(e)}")  # Add debug log
        if update.callback_query:
            update.callback_query.edit_message_text(text=error_message)
        else:
            context.bot.send_message(chat_id=chat_id, text=error_message)

def preferences_command(update: Update, context: CallbackContext) -> None:
    """Set user preferences"""
    global db_helper
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("Set Interests", callback_data='set_interests')],
        [InlineKeyboardButton("Set Timezone", callback_data='set_timezone')],
        [InlineKeyboardButton("Set Preferred Times", callback_data='set_preferred_times')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(f'{INFO} Please select a preference to set:', reply_markup=reply_markup)

def set_user_preferences(update: Update, context: CallbackContext, pref_type) -> None:
    """Handle setting specific preferences"""
    global db_helper
    user_id = update.effective_user.id
    
    # Create different options buttons for each preference type
    if pref_type == 'interests':
        keyboard = [
            [InlineKeyboardButton("Sports", callback_data='interest_sports'),
             InlineKeyboardButton("Music", callback_data='interest_music')],
            [InlineKeyboardButton("Technology", callback_data='interest_tech'),
             InlineKeyboardButton("Art", callback_data='interest_art')],
            [InlineKeyboardButton("Save", callback_data='save_interests')]
        ]
        message = f"{INFO} Please select your interests (multiple choices allowed):"
    elif pref_type == 'timezone':
        keyboard = [
            [InlineKeyboardButton("UTC+8 (HK)", callback_data='tz_utc8'),
             InlineKeyboardButton("UTC+0 (London)", callback_data='tz_utc0')],
            [InlineKeyboardButton("UTC-5 (NY)", callback_data='tz_utc-5'),
             InlineKeyboardButton("UTC+9 (Tokyo)", callback_data='tz_utc9')]
        ]
        message = f"{INFO} Please select your timezone:"
    elif pref_type == 'preferred_times':
        keyboard = [
            [InlineKeyboardButton("Morning (9-12)", callback_data='time_morning'),
             InlineKeyboardButton("Afternoon (13-17)", callback_data='time_afternoon')],
            [InlineKeyboardButton("Evening (18-22)", callback_data='time_evening'),
             InlineKeyboardButton("Night (23-8)", callback_data='time_night')],
            [InlineKeyboardButton("Save", callback_data='save_times')]
        ]
        message = f"{INFO} Please select your preferred meeting times:"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)
    else:
        update.message.reply_text(message, reply_markup=reply_markup)

def list_events_command(update: Update, context: CallbackContext):
    """List all events for the user"""
    try:
        user_id = update.effective_user.id
        events = db_helper.get_user_events(user_id)
        
        if not events:
            update.message.reply_text(f"{INFO} No events found.\nUse /event to create a new event!")
            return
        
        # Split events into multiple messages, each showing 5 events
        events_per_page = 5
        for i in range(0, len(events), events_per_page):
            message = f"{SUCCESS} Your Events\n\n"
            page_events = events[i:i + events_per_page]
            
            for event in page_events:
                message += f"{BULLET} Event {event['_id']}\n"
                message += f"{BULLET} {event['title']}\n"
                message += "-------------------------\n"
                message += f"{BULLET} Type: {event['type']}\n"
                message += f"{BULLET} Time: {event['datetime']}\n"
                message += f"{BULLET} Duration: {event['duration']} minutes\n"
                message += f"{BULLET} Status: {event['status']}\n"
                message += "-------------------------\n\n"
            
            update.message.reply_text(message)
        
        # Add usage instructions on the last page
        help_message = f"{INFO} Join an Event\n"
        help_message += "Use command: /join <EventID> <Your Name>\n"
        help_message += "Example: /join 0001 John"
        update.message.reply_text(help_message)
            
    except Exception as e:
        print(f"{ERROR} List events error: {str(e)}")
        update.message.reply_text(f"{ERROR} Error getting event list. Please try again.")

def button_click(update: Update, context: CallbackContext) -> None:
    """Handle button click events"""
    global db_helper
    query = update.callback_query
    query.answer()
    
    if query.data == 'create_event':
        create_event_flow(update, context)
    elif query.data == 'regenerate_event':
        create_event_flow(update, context)
    elif query.data == 'list_events':
        try:
            events = db_helper.get_user_events(query.from_user.id)
            if not events:
                query.message.reply_text(f"{INFO} No events found.\nUse /event to create a new event!")
                return
                
            message = f"{SUCCESS} Your Events\n\n"
            for event in events:
                participants = event.get('participant_names', [])
                
                message += f"{BULLET} Event {event['_id']}\n"
                message += f"{BULLET} {event['title']}\n"
                message += "-------------------------\n"
                message += f"{BULLET} Type: {event['type']}\n"
                message += f"{BULLET} Time: {event['datetime']}\n"
                message += f"{BULLET} Participants: {len(participants)}\n"
                message += f"{BULLET} Names: {', '.join(participants) if participants else 'No participants yet'}\n"
                message += f"{BULLET} Status: {event['status']}\n\n"
                message += f"{INFO} Description: {event['description']}\n"
                message += "-------------------------\n\n"
            
            message += f"{INFO} Join an Event\n"
            message += "Use command: /join <EventID> <Your Name>\n"
            message += "Example: /join 0001 John"
            
            query.message.reply_text(message)
        except Exception as e:
            query.message.reply_text(f"{ERROR} Error getting event list: {str(e)}")
    elif query.data == 'confirm_event':
        try:
            event_data = context.user_data.get('event_draft')
            if event_data:
                user = query.from_user
                creator_name = f"{user.first_name}"
                if user.last_name:
                    creator_name += f" {user.last_name}"
                    
                result = db_helper.create_event(
                    query.from_user.id, 
                    event_data,
                    creator_name=creator_name
                )
                
                query.edit_message_text(f"""{SUCCESS} Event created successfully!

{BULLET} Event ID: {result.inserted_id}
{BULLET} Creator: {creator_name}
{BULLET} Current Participants: 1
{BULLET} Participant List: {creator_name}""")
            else:
                query.edit_message_text(f"{ERROR} Creation failed: No event data found")
        except Exception as e:
            query.edit_message_text(f"{ERROR} Error creating event: {str(e)}")
    elif query.data == 'set_interests':
        set_user_preferences(update, context, 'interests')
    elif query.data == 'set_timezone':
        set_user_preferences(update, context, 'timezone')
    elif query.data == 'set_preferred_times':
        set_user_preferences(update, context, 'preferred_times')
    elif query.data.startswith('interest_'):
        interest = query.data.split('_')[1]
        if 'selected_interests' not in context.user_data:
            context.user_data['selected_interests'] = set()
        context.user_data['selected_interests'].add(interest)
        query.answer(f"Added {interest} to your interests")
        
    elif query.data.startswith('tz_'):
        timezone = query.data.split('_')[1]
        preferences = {'timezone': f"UTC{timezone}"}
        db_helper.save_user_preferences(query.from_user.id, preferences)
        query.edit_message_text(f"{SUCCESS} Timezone set to UTC{timezone}")
        
    elif query.data.startswith('time_'):
        time_pref = query.data.split('_')[1]
        if 'selected_times' not in context.user_data:
            context.user_data['selected_times'] = set()
        context.user_data['selected_times'].add(time_pref)
        query.answer(f"Added {time_pref} to your preferred times")
        
    elif query.data == 'save_interests':
        interests = list(context.user_data.get('selected_interests', []))
        preferences = {'interests': interests}
        db_helper.save_user_preferences(query.from_user.id, preferences)
        query.edit_message_text(f"{SUCCESS} Saved interests: {', '.join(interests)}")
        
    elif query.data == 'save_times':
        times = list(context.user_data.get('selected_times', []))
        preferences = {'preferred_times': times}
        db_helper.save_user_preferences(query.from_user.id, preferences)
        query.edit_message_text(f"{SUCCESS} Saved preferred times: {', '.join(times)}")

def join_event_command(update: Update, context: CallbackContext) -> None:
    """Handle joining an event command"""
    global db_helper
    try:
        # Check command parameters
        if not context.args or len(context.args) < 2:
            update.message.reply_text("Usage: /join <EventID> <Your Name>")
            return

        event_id = context.args[0]  # Get event ID
        joiner_name = ' '.join(context.args[1:])  # Get participant name, supports spaces
        
        # Handle leading zeros (e.g., convert "1" to "0001")
        if event_id.isdigit():
            event_id = event_id.zfill(4)
        
        # Validate ID format
        if not (len(event_id) == 4 and event_id.isdigit()):
            update.message.reply_text("Invalid event ID format. Please enter a number between 1-9999")
            return

        user_id = update.effective_user.id
        
        # Check if event exists
        event = db_helper.db.events.find_one({'_id': event_id})
        if not event:
            update.message.reply_text(f"Event {event_id} does not exist")
            return
            
        # Check if user is already a participant by name
        if joiner_name in (event.get('participant_names') or []):
            update.message.reply_text(f"{joiner_name} is already a participant in this event")
            return
        
        # Try to join the event
        result = db_helper.update_event_participants(event_id, user_id, join=True, joiner_name=joiner_name)
        if result and result.modified_count > 0:
            # Get updated event information
            updated_event = db_helper.db.events.find_one({'_id': event_id})
            participants = updated_event.get('participant_names', [])
            
            update.message.reply_text(f"""{SUCCESS} {joiner_name} successfully joined the event!

{BULLET} Event ID: {event_id}
{BULLET} Event Name: {updated_event['title']}
{BULLET} Current Participants: {len(participants)}
{BULLET} Participant List: {', '.join(participants)}""")
        else:
            update.message.reply_text(f"{ERROR} {joiner_name} failed to join the event. Please try again later")
            
    except Exception as e:
        update.message.reply_text(f"Error joining event: {str(e)}")

if __name__ == '__main__':
 main()
