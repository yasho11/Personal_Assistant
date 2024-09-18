import os
import sys
import logging
from dotenv import load_dotenv
import speech_recognition as sr
import pyttsx3
import spacy
import dateparser
from datetime import datetime, timedelta
from notion_client import Client as NotionClient
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables from .env file
load_dotenv(dotenv_path='myenv/.env')

# Configure logging
logging.basicConfig(level=logging.ERROR, filename='assistant.log')

# Initialize spaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Define the scope for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']


class NotionManager:
    def __init__(self):
        self.notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")

    def add_task(self, task_name, task_type):
        """Add a task to Notion with name and type."""
        try:
            self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "Name": {"title": [{"text": {"content": task_name}}]},
                    "Type": {"rich_text": [{"text": {"content": task_type}}]}
                }
            )
            return True, "Task added to Notion successfully!"
        except Exception as e:
            logging.error(f"Failed to add task: {e}")
            return False, "Failed to add task due to an error."


    def read_tasks(self):
        """Retrieve tasks from Notion and return them as a list."""
        try:
            response = self.notion.databases.query(database_id=self.database_id)
            tasks = response.get("results", [])
            if not tasks:
                return False, "There are no tasks in your Notion database."

            task_list = []
            for task in tasks:
                name_property = task["properties"]["Name"]["title"]
                type_property = task["properties"]["Type"]["rich_text"]
                task_name = name_property[0]["text"]["content"] if name_property else "Unnamed Task"
                task_type = type_property[0]["text"]["content"] if type_property else "No Type Specified"
                task_details = f"Task: {task_name}, Type: {task_type}."
                task_list.append(task_details)
            return True, task_list
        except Exception as e:
            logging.error(f"Failed to read tasks from Notion: {e}")
            return False, "Failed to read tasks from Notion due to an error."


class CalendarManager:
    def __init__(self):
        self.service = self.get_calendar_service()

    def authenticate_google_calendar(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logging.error(f"Failed to authenticate with Google Calendar: {e}")
                return None
        return creds

    def get_calendar_service(self):
        creds = self.authenticate_google_calendar()
        if creds:
            try:
                service = build('calendar', 'v3', credentials=creds)
                return service
            except Exception as e:
                logging.error(f"Failed to build calendar service: {e}")
        return None

    def add_event(self, event_name, event_time):
        """Add an event to Google Calendar."""
        if not self.service:
            return False, "Calendar service is not available."
        try:
            start_time = event_time.isoformat()
            end_time = (event_time + timedelta(hours=1)).isoformat()
            event = {
                'summary': event_name,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                }
            }
            self.service.events().insert(calendarId='primary', body=event).execute()
            return True, "Event added to your calendar successfully!"
        except Exception as e:
            logging.error(f"Failed to add event: {e}")
            return False, "Failed to add event to your calendar due to an error."

    def read_events(self):
        """Retrieve upcoming events from Google Calendar."""
        if not self.service:
            return False, "Calendar service is not available."
        try:
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = self.service.events().list(calendarId='primary', timeMin=now,
                                                       maxResults=10, singleEvents=True,
                                                       orderBy='startTime').execute()
            events = events_result.get('items', [])
            if not events:
                return False, "No upcoming events found."

            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_summary = f"Event: {event['summary']} at {start}"
                event_list.append(event_summary)
            return True, event_list
        except Exception as e:
            logging.error(f"Failed to read events: {e}")
            return False, "Failed to read events from your calendar due to an error."


class Assistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.notion_manager = NotionManager()
        self.calendar_manager = CalendarManager()
        self.intents = {
            "add_task": ["add task", "create task", "new task"],
            "read_tasks": ["read task", "show task", "list task"],
            "add_event": ["add event", "create event", "schedule event"],
            "read_events": ["read events", "show events", "list events", "my schedule"],
            "exit": ["exit", "quit", "stop", "end"],
        }

    def speak(self, text):
        """Make the assistant speak out the given text."""
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self, prompt=None):
        """Listen to the user's voice input and return the recognized text."""
        if prompt:
            self.speak(prompt)
        with sr.Microphone() as source:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=5)
                print("Recognizing speech...")
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text.lower()
            except sr.WaitTimeoutError:
                self.speak("Listening timed out. Please try again.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I did not understand that. Please repeat.")
                return None
            except sr.RequestError as e:
                logging.error(f"Speech recognition error: {e}")
                self.speak("Could not request results; please check your network connection.")
                return None

    def recognize_intent(self, command):
        """Recognize the intent of the command using phrase matching."""
        for intent, phrases in self.intents.items():
            for phrase in phrases:
                if phrase in command:
                    return intent
        return "unknown"

    def handle_intent(self, intent):
        """Handle the recognized intent."""
        if intent == "add_task":
            task_name = self.listen("Please provide the task name.")
            if not task_name:
                return
            task_type = self.listen("Please provide the task type.")
            if not task_type:
                task_type = "General"
            success, message = self.notion_manager.add_task(task_name, task_type)
            self.speak(message)

        elif intent == "read_tasks":
            success, result = self.notion_manager.read_tasks()
            if success:
                for task in result:
                    self.speak(task)
            else:
                self.speak(result)

        elif intent == "add_event":
            event_name = self.listen("Please provide the event name.")
            if not event_name:
                return
            event_time_str = self.listen("Please provide the event time.")
            if not event_time_str:
                return
            event_time = dateparser.parse(event_time_str)
            if not event_time:
                self.speak("Could not understand the date and time. Please try again.")
                return
            success, message = self.calendar_manager.add_event(event_name, event_time)
            self.speak(message)

        elif intent == "read_events":
            success, result = self.calendar_manager.read_events()
            if success:
                for event in result:
                    self.speak(event)
            else:
                self.speak(result)

        elif intent == "exit":
            self.speak("Exiting assistant. Goodbye!")
            sys.exit()

        else:
            self.speak("Sorry, I didn't understand that command. Please try again.")

    def run(self):
        """Main loop to handle user commands."""
        self.speak("Hello! How can I assist you today?")
        while True:
            command = self.listen()
            if command:
                intent = self.recognize_intent(command)
                self.handle_intent(intent)


if __name__ == "__main__":
    assistant = Assistant()
    assistant.run()
