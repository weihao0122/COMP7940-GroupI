from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import os
from pymongo.errors import ConfigurationError
import warnings
from colorama import init, Fore, Back, Style

# Initialize colorama
init()

# Define custom symbols
SUCCESS = "[ OK ]"
ERROR = "[FAIL]"
INFO = "[INFO]"
BULLET = "*"

# Ignore CosmosDB warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pymongo')

load_dotenv()

# Use environment variable for URI, fallback to default if not set
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://f4477680:3O76I4LOiuxZPHTZWpmNED5NYgxEC1OSxYs7zmFMQmqXd07AB5imyRkmks64fknHFSEye0z9MQ6BACDbR4fd4Q%3D%3D@f4477680.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&maxIdleTimeMS=120000&appName=@f4477680@')

class DBHelper:
    def __init__(self, mongodb_uri=None):
        """Initialize database connection"""
        # Use provided URI or environment variable
        self.client = MongoClient(mongodb_uri or MONGODB_URI)
        self.db = self.client['comp7940']
        
        try:
            # First ensure counters collection exists and has initial data
            if 'counters' not in self.db.list_collection_names():
                print(f"{INFO} Creating counters collection")
                self.db.create_collection('counters')
            
            # Always check and initialize event_id counter
            counter = self.db.counters.find_one({'_id': 'event_id'})
            if not counter:
                print(f"{INFO} Initializing event_id counter")
                self.db.counters.insert_one({'_id': 'event_id', 'seq': 0})
            
            # Ensure other collections exist
            required_collections = ['events', 'user_preferences']
            for collection in required_collections:
                if collection not in self.db.list_collection_names():
                    print(f"{INFO} Creating collection: {collection}")
                    self.db.create_collection(collection)
            
            print(f"{SUCCESS} All collections initialized")
        except Exception as e:
            print(f"{ERROR} Database initialization error: {str(e)}")
            raise
    
    def get_next_sequence(self, name):
        """Get next sequence number for IDs"""
        print(f"{INFO} Getting next sequence for: {name}")
        try:
            result = self.db.counters.find_one_and_update(
                {'_id': name},
                {'$inc': {'seq': 1}},
                return_document=True
            )
            
            if not result:
                print(f"{ERROR} Counter {name} not found")
                # Initialize the counter if it doesn't exist
                self.db.counters.insert_one({'_id': name, 'seq': 1})
                return 1
            
            print(f"{SUCCESS} Next sequence number: {result['seq']}")
            return result['seq']
        except Exception as e:
            print(f"{ERROR} Error getting sequence: {str(e)}")
            raise

    def create_event(self, creator_id, event_data, creator_name=None):
        """Create a new event in database"""
        print(f"{INFO} Creating new event for creator: {creator_name}")
        collection = self.db.events
        # Get simple numeric ID
        simple_id = str(self.get_next_sequence('event_id')).zfill(4)
        event = {
            '_id': simple_id,
            'creator_id': creator_id,
            'title': event_data['title'],
            'description': event_data['description'],
            'datetime': event_data['datetime'],
            'duration': event_data['duration'],
            'type': event_data['type'],
            'participants': [creator_id],
            'participant_names': [creator_name] if creator_name else [],
            'agenda': event_data['agenda'],
            'created_at': datetime.now(),
            'status': 'pending'
        }
        result = collection.insert_one(event)
        print(f"{SUCCESS} Event created with ID: {simple_id}")
        return result

    def get_user_events(self, user_id):
        """Get all events where user is creator or participant"""
        try:
            collection = self.db.events
            print(f"{INFO} Searching events for user: {user_id}")
            
            collection.create_index([('creator_id', 1)])
            collection.create_index([('participants', 1)])
            
            events = list(collection.find({
                '$or': [
                    {'creator_id': user_id},
                    {'participants': user_id}
                ]
            }))
            
            print(f"{SUCCESS} Found {len(events)} events for user")
            return events
        except Exception as e:
            print(f"{ERROR} Error getting user events: {str(e)}")
            return []

    def update_event_participants(self, event_id, user_id, join=True, joiner_name=None):
        """Update event participants list"""
        collection = self.db.events
        print(f"{INFO} Attempting to update event: ID={event_id}, user_id={user_id}, join={join}, joiner={joiner_name}")
        
        # Check if event exists
        event = collection.find_one({'_id': event_id})
        if not event:
            print(f"{ERROR} Event {event_id} not found")
            return None
        
        # Check if user is already a participant
        participant_names = event.get('participant_names', [])
        if join and joiner_name in participant_names:
            print(f"{INFO} User {joiner_name} is already a participant in event {event_id}")
            return None
        
        # Update participants
        if join:
            result = collection.update_one(
                {'_id': event_id},
                {
                    '$addToSet': {
                        'participants': user_id,
                        'participant_names': joiner_name
                    }
                }
            )
        else:
            result = collection.update_one(
                {'_id': event_id},
                {
                    '$pull': {
                        'participants': user_id,
                        'participant_names': joiner_name
                    }
                }
            )
        
        print(f"{SUCCESS} Update result: {result.modified_count}")
        return result

    def save_user_preferences(self, user_id, preferences):
        """Save or update user preferences"""
        collection = self.db.user_preferences
        return collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'interests': preferences.get('interests', []),
                'timezone': preferences.get('timezone', 'UTC+8'),
                'preferred_times': preferences.get('preferred_times', []),
                'updated_at': datetime.now()
            }},
            upsert=True
        )

    def get_user_preferences(self, user_id):
        """Get user preferences"""
        try:
            collection = self.db.user_preferences
            return collection.find_one({'user_id': user_id})
        except Exception as e:
            print(f"{ERROR} Error getting user preferences: {str(e)}")
            return None 