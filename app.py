import os
import sys
import logging
import requests
from dotenv import load_dotenv
import speech_recognition as sr
import pyttsx3
import spacy
import dateparser
from datetime import datetime, timedelta
from notion_client import Client as NotionClient, APIResponseError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QTabWidget, QStatusBar
)
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from spacy.matcher import Matcher
from time import sleep

# Load environment variables from .env file
load_dotenv(dotenv_path='myenv/.env')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level for detailed logs
    filename='assistant.log',
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Initialize spaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Define the scope for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Retry decorator for network requests
def retry(exceptions, tries=3, delay=1, backoff=2):
    def decorator_retry(func):
        def wrapper_retry(*args, **kwargs):
            _tries, _delay = tries, delay
            while _tries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logging.error(f"Error: {e}. Retrying in {_delay} seconds...")
                    sleep(_delay)
                    _tries -= 1
                    _delay *= backoff
            return func(*args, **kwargs)
        return wrapper_retry
    return decorator_retry

class NotionManager:
    def __init__(self):
        self.notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")

    @retry((APIResponseError, requests.exceptions.RequestException))
    def add_task(self, task_name, task_type, priority='normal'):
        """Add a task to Notion with name, type, and priority."""
        try:
            self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "Name": {"title": [{"text": {"content": task_name}}]},
                    "Type": {"rich_text": [{"text": {"content": task_type}}]},
                    "Priority": {"select": {"name": priority.capitalize()}}
                }
            )
            return True, "Task added to Notion successfully!"
        except Exception as e:
            logging.exception("Failed to add task.")
            return False, "Failed to add task due to an error."

    @retry((APIResponseError, requests.exceptions.RequestException))
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
                priority_property = task["properties"].get("Priority", {}).get("select", {})
                task_name = name_property[0]["text"]["content"] if name_property else "Unnamed Task"
                task_type = type_property[0]["text"]["content"] if type_property else "No Type Specified"
                priority = priority_property.get("name", "Normal")
                task_details = f"Task: {task_name}, Type: {task_type}, Priority: {priority}."
                task_list.append(task_details)
            return True, task_list
        except Exception as e:
            logging.exception("Failed to read tasks from Notion.")
            return False, "Failed to read tasks from Notion due to an error."

class CalendarManager:
    def __init__(self):
        self.service = self.get_calendar_service()

    def authenticate_google_calendar(self):
        creds = None
        if os.path.exists('token.json'):
            try:
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            except Exception as e:
                logging.error("Invalid token.json file.")
                creds = None
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logging.exception("Failed to authenticate with Google Calendar.")
                return None
        return creds

    def get_calendar_service(self):
        creds = self.authenticate_google_calendar()
        if creds:
            try:
                service = build('calendar', 'v3', credentials=creds)
                return service
            except Exception as e:
                logging.exception("Failed to build calendar service.")
        return None

    @retry((requests.exceptions.RequestException,))
    def add_event(self, event_name, event_time, priority='normal'):
        """Add an event to Google Calendar."""
        if not self.service:
            return False, "Calendar service is not available."
        try:
            start_time = event_time.isoformat()
            end_time = (event_time + timedelta(hours=1)).isoformat()
            event = {
                'summary': f"[{priority.capitalize()}] {event_name}",
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
            logging.exception("Failed to add event.")
            return False, "Failed to add event to your calendar due to an error."

    @retry((requests.exceptions.RequestException,))
    def read_events(self):
        """Retrieve upcoming events from Google Calendar."""
        if not self.service:
            return False, "Calendar service is not available."
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary', timeMin=now,
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
            logging.exception("Failed to read events.")
            return False, "Failed to read events from your calendar due to an error."

class WeatherManager:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    @retry((requests.exceptions.RequestException,))
    def get_weather(self, location):
        """Fetch weather data for the given location."""
        if not self.api_key:
            logging.error("OpenWeather API key is not set.")
            return False, "Weather service is not configured properly."

        params = {
            'q': location,
            'appid': self.api_key,
            'units': 'metric'
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            weather_description = data['weather'][0]['description'].capitalize()
            temperature = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']

            weather_report = (
                f"The current weather in {location} is {weather_description} with a temperature of "
                f"{temperature}°C, feels like {feels_like}°C. Humidity is at {humidity}% and wind speed is "
                f"{wind_speed} meters per second."
            )
            return True, weather_report

        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred while fetching weather: {http_err}")
            return False, "Could not retrieve weather data. Please check the location and try again."
        except Exception as e:
            logging.exception("Error occurred while fetching weather.")
            return False, "An error occurred while retrieving the weather information."

class Assistant(QObject):
    # Define signals
    update_tasks_signal = pyqtSignal(list)
    update_events_signal = pyqtSignal(list)
    update_weather_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.notion_manager = NotionManager()
        self.calendar_manager = CalendarManager()
        self.weather_manager = WeatherManager()
        self.context = {}
        self.nlp = nlp
        self.matcher = Matcher(self.nlp.vocab)
        self.define_intent_patterns()
        # Removed self.intents as it's not used
        # Set up speech rate for clarity
        self.engine.setProperty('rate', 150)

    def define_intent_patterns(self):
        # Define patterns for intents
        self.intent_patterns = {
            "add_task": [
                [{"LEMMA": "add"}, {"POS": "DET", "OP": "?"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LEMMA": "create"}, {"POS": "DET", "OP": "?"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LOWER": "new"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LEMMA": "need"}, {"LOWER": "to"}, {"LEMMA": "add"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LEMMA": "set"}, {"LOWER": "up"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LEMMA": "make"}, {"LOWER": "task"}, {"OP": "*"}],
                [{"LEMMA": "add"}, {"LOWER": "a"}, {"LOWER": "task"}, {"OP": "*"}],
            ],
            "read_tasks": [
                [{"LEMMA": "read"}, {"LOWER": "tasks"}, {"OP": "*"}],
                [{"LEMMA": "show"}, {"LOWER": "tasks"}, {"OP": "*"}],
                [{"LEMMA": "list"}, {"LOWER": "tasks"}, {"OP": "*"}],
                [{"LOWER": "what"}, {"LEMMA": "be"}, {"LOWER": "my"}, {"LOWER": "tasks"}, {"OP": "*"}],
                [{"LOWER": "do"}, {"LOWER": "i"}, {"LEMMA": "have"}, {"LOWER": "any"}, {"LOWER": "tasks"}, {"OP": "*"}],
            ],
            "add_event": [
                [{"LEMMA": "add"}, {"POS": "DET", "OP": "?"}, {"LOWER": "event"}, {"OP": "*"}],
                [{"LEMMA": "create"}, {"POS": "DET", "OP": "?"}, {"LOWER": "event"}, {"OP": "*"}],
                [{"LEMMA": "schedule"}, {"POS": "DET", "OP": "?"}, {"LOWER": "event"}, {"OP": "*"}],
                [{"LEMMA": "set"}, {"LOWER": "up"}, {"LOWER": "event"}, {"OP": "*"}],
                [{"LEMMA": "make"}, {"LOWER": "appointment"}, {"OP": "*"}],
                [{"LEMMA": "schedule"}, {"LOWER": "meeting"}, {"OP": "*"}],
            ],
            "read_events": [
                [{"LEMMA": "read"}, {"LOWER": "events"}, {"OP": "*"}],
                [{"LEMMA": "show"}, {"LOWER": "events"}, {"OP": "*"}],
                [{"LEMMA": "list"}, {"LOWER": "events"}, {"OP": "*"}],
                [{"LOWER": "what"}, {"LEMMA": "be"}, {"LOWER": "my"}, {"LOWER": "schedule"}, {"OP": "*"}],
                [{"LOWER": "do"}, {"LOWER": "i"}, {"LEMMA": "have"}, {"LOWER": "any"}, {"LOWER": "events"}, {"OP": "*"}],
            ],
            "get_weather": [
                [{"LOWER": "what"}, {"LEMMA": "'s", "OP": "?"}, {"LOWER": "the"}, {"LOWER": "weather"}, {"OP": "*"}],
                [{"LEMMA": "tell"}, {"LOWER": "me"}, {"LOWER": "the"}, {"LOWER": "weather"}, {"OP": "*"}],
                [{"LEMMA": "what"}, {"LOWER": "is", "OP": "?"}, {"LOWER": "the"}, {"LOWER": "weather"}, {"OP": "*"}],
                [{"LEMMA": "how"}, {"LOWER": "is", "OP": "?"}, {"LOWER": "the"}, {"LOWER": "weather"}, {"OP": "*"}],
            ],
            "exit": [
                [{"LEMMA": "exit"}],
                [{"LEMMA": "quit"}],
                [{"LEMMA": "stop"}],
                [{"LEMMA": "end"}],
                [{"LOWER": "goodbye"}],
                [{"LOWER": "bye"}],
            ]
        }
        for intent, patterns in self.intent_patterns.items():
            self.matcher.add(intent, patterns)

    def extract_object(self, doc, verb):
        # Use noun chunks to extract the object related to the verb
        for np in doc.noun_chunks:
            if verb.i < np.start:
                # Exclude patterns like 'a task' or 'an event'
                if np.text.lower() not in ['a task', 'an event', 'the task', 'the event']:
                    return np.text
        return None

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
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=5)
                print("Recognizing speech...")
                text = self.recognizer.recognize_google(audio)
                print(f"Recognized text: {text}")  # Debug statement
                logging.debug(f"Recognized text: {text}")
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

    def parse_command(self, command):
        """Parse the command and extract intent and entities."""
        logging.debug(f"Command received: {command}")
        doc = self.nlp(command)
        matches = self.matcher(doc)
        intent = None
        entities = {}
        if matches:
            # Get the match with the longest span
            match_id, start, end = max(matches, key=lambda x: x[2]-x[1])
            intent = self.nlp.vocab.strings[match_id]
            logging.debug(f"Intent identified: {intent}")
            # Get the span of the matched pattern
            matched_span = doc[start:end]
            # Find the verb in the matched span
            verb = None
            for token in matched_span:
                if token.pos_ == 'VERB':
                    verb = token
                    break
            if verb:
                obj = self.extract_object(doc, verb)
                if obj:
                    if intent == 'add_task':
                        entities['TASK_NAME'] = obj
                    elif intent == 'add_event':
                        entities['EVENT_NAME'] = obj
            # Extract time expressions
            for ent in doc.ents:
                if ent.label_ in ('DATE', 'TIME'):
                    entities['TIME'] = ent.text
            # For get_weather, extract location
            if intent == 'get_weather':
                for ent in doc.ents:
                    if ent.label_ in ('GPE', 'LOC'):
                        entities['LOCATION'] = ent.text
            logging.debug(f"Entities extracted: {entities}")
        else:
            logging.debug("No intent matched.")
            intent = None

        # Check for priority indicators
        priority = 'normal'
        if any(token.lemma_ in ['urgent', 'important', 'high'] for token in doc):
            priority = 'high'
        elif any(token.lemma_ in ['quick', 'low priority', 'low'] for token in doc):
            priority = 'low'

        logging.debug(f"Priority detected: {priority}")

        return intent, entities, priority

    def handle_intent(self, intent, entities, priority):
        """Handle the parsed intent with entities and priority."""
        try:
            logging.debug(f"Handling intent: {intent}")
            logging.debug(f"Entities: {entities}")
            if intent == "add_task":
                task_name = entities.get('TASK_NAME')
                if not task_name:
                    self.speak("What is the name of the task?")
                    task_name = self.listen()
                if not task_name:
                    self.speak("Task name is required to add a task.")
                    return
                task_type = entities.get('TASK_TYPE')
                if not task_type:
                    self.speak("What is the type of the task?")
                    task_type = self.listen()
                    if not task_type:
                        task_type = "General"
                success, message = self.notion_manager.add_task(task_name, task_type, priority)
                if success:
                    # Update context
                    self.context['last_task'] = {'name': task_name, 'type': task_type, 'priority': priority}
                    self.update_tasks_signal.emit([f"Task: {task_name}, Type: {task_type}, Priority: {priority.capitalize()}"])
                self.speak(message)

            elif intent == "read_tasks":
                success, result = self.notion_manager.read_tasks()
                if success:
                    self.update_tasks_signal.emit(result)
                    for task in result:
                        self.speak(task)
                else:
                    self.speak(result)

            elif intent == "add_event":
                event_name = entities.get('EVENT_NAME')
                if not event_name:
                    self.speak("Please provide the event name.")
                    event_name = self.listen()
                if not event_name:
                    self.speak("Event name is required to add an event.")
                    return
                event_time_str = entities.get('TIME')
                if not event_time_str:
                    self.speak("Please provide the event time.")
                    event_time_str = self.listen()
                if not event_time_str:
                    self.speak("Event time is required to add an event.")
                    return
                event_time = dateparser.parse(event_time_str)
                if not event_time:
                    self.speak("Could not understand the date and time. Please try again.")
                    return
                success, message = self.calendar_manager.add_event(event_name, event_time, priority)
                if success:
                    # Store in context
                    self.context['last_event'] = {'name': event_name, 'time': event_time, 'priority': priority}
                    self.update_events_signal.emit([f"Event: {event_name} at {event_time}, Priority: {priority.capitalize()}"])
                self.speak(message)

            elif intent == "read_events":
                success, result = self.calendar_manager.read_events()
                if success:
                    self.update_events_signal.emit(result)
                    for event in result:
                        self.speak(event)
                else:
                    self.speak(result)

            elif intent == "get_weather":
                location = entities.get('LOCATION') or self.context.get('last_location')
                if not location:
                    self.speak("For which location would you like the weather report?")
                    location = self.listen()
                if not location:
                    self.speak("Location is required to fetch weather information.")
                    return
                success, weather_report = self.weather_manager.get_weather(location)
                if success:
                    self.context['last_location'] = location
                    self.update_weather_signal.emit(weather_report)
                self.speak(weather_report)

            elif intent == "exit":
                self.speak("Exiting assistant. Goodbye!")
                sys.exit()

            else:
                self.speak("Sorry, I didn't understand that command. Please try again.")
        except Exception as e:
            logging.exception("Error handling intent.")
            self.speak("An error occurred while processing your request.")

    def run(self):
        """Main loop to handle user commands."""
        self.speak("Hello! How can I assist you today?")
        while True:
            command = self.listen()
            if command:
                intent, entities, priority = self.parse_command(command)
                if intent:
                    self.handle_intent(intent, entities, priority)
                else:
                    self.speak("I'm sorry, I didn't catch that. Could you please repeat?")
            else:
                self.speak("No command detected. Please try again.")

class AssistantGUI(QMainWindow):
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.initUI()
        self.connect_signals()

    def initUI(self):
        self.setWindowTitle('Assistant Dashboard')
        self.setGeometry(100, 100, 800, 600)

        # Create main layout with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tasks Tab
        self.tasks_tab = QWidget()
        self.tasks_layout = QVBoxLayout()
        tasks_label = QLabel('Tasks')
        self.tasks_list = QListWidget()
        refresh_tasks_btn = QPushButton('Refresh Tasks')
        refresh_tasks_btn.clicked.connect(self.refresh_tasks)
        self.tasks_layout.addWidget(tasks_label)
        self.tasks_layout.addWidget(self.tasks_list)
        self.tasks_layout.addWidget(refresh_tasks_btn)
        self.tasks_tab.setLayout(self.tasks_layout)

        # Events Tab
        self.events_tab = QWidget()
        self.events_layout = QVBoxLayout()
        events_label = QLabel('Events')
        self.events_list = QListWidget()
        refresh_events_btn = QPushButton('Refresh Events')
        refresh_events_btn.clicked.connect(self.refresh_events)
        self.events_layout.addWidget(events_label)
        self.events_layout.addWidget(self.events_list)
        self.events_layout.addWidget(refresh_events_btn)
        self.events_tab.setLayout(self.events_layout)

        # Weather Tab
        self.weather_tab = QWidget()
        self.weather_layout = QVBoxLayout()
        weather_label = QLabel('Weather')
        self.weather_info = QLabel('No weather data')
        refresh_weather_btn = QPushButton('Refresh Weather')
        refresh_weather_btn.clicked.connect(self.refresh_weather)
        self.weather_layout.addWidget(weather_label)
        self.weather_layout.addWidget(self.weather_info)
        self.weather_layout.addWidget(refresh_weather_btn)
        self.weather_tab.setLayout(self.weather_layout)

        # Add tabs to main widget
        self.tabs.addTab(self.tasks_tab, "Tasks")
        self.tabs.addTab(self.events_tab, "Events")
        self.tabs.addTab(self.weather_tab, "Weather")

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Start assistant in a separate thread
        self.assistant_thread = AssistantThread(self.assistant)
        self.assistant_thread.start()

    def connect_signals(self):
        self.assistant.update_tasks_signal.connect(self.update_tasks_list)
        self.assistant.update_events_signal.connect(self.update_events_list)
        self.assistant.update_weather_signal.connect(self.update_weather_info)

    def refresh_tasks(self):
        self.status_bar.showMessage("Refreshing tasks...")
        success, result = self.assistant.notion_manager.read_tasks()
        if success:
            self.tasks_list.clear()
            for task in result:
                self.tasks_list.addItem(task)
            self.status_bar.showMessage("Tasks refreshed.", 5000)
        else:
            self.tasks_list.clear()
            self.tasks_list.addItem(result)
            self.status_bar.showMessage("Failed to refresh tasks.", 5000)

    def refresh_events(self):
        self.status_bar.showMessage("Refreshing events...")
        success, result = self.assistant.calendar_manager.read_events()
        if success:
            self.events_list.clear()
            for event in result:
                self.events_list.addItem(event)
            self.status_bar.showMessage("Events refreshed.", 5000)
        else:
            self.events_list.clear()
            self.events_list.addItem(result)
            self.status_bar.showMessage("Failed to refresh events.", 5000)

    def refresh_weather(self):
        self.status_bar.showMessage("Refreshing weather...")
        location = self.assistant.context.get('last_location', 'Your Default Location')
        success, weather_report = self.assistant.weather_manager.get_weather(location)
        if success:
            self.weather_info.setText(weather_report)
            self.status_bar.showMessage("Weather refreshed.", 5000)
        else:
            self.weather_info.setText(weather_report)
            self.status_bar.showMessage("Failed to refresh weather.", 5000)

    def update_tasks_list(self, tasks):
        self.tasks_list.clear()
        for task in tasks:
            self.tasks_list.addItem(task)
        self.status_bar.showMessage("Tasks updated.", 5000)

    def update_events_list(self, events):
        self.events_list.clear()
        for event in events:
            self.events_list.addItem(event)
        self.status_bar.showMessage("Events updated.", 5000)

    def update_weather_info(self, weather_report):
        self.weather_info.setText(weather_report)
        self.status_bar.showMessage("Weather information updated.", 5000)

class AssistantThread(QThread):
    def __init__(self, assistant):
        QThread.__init__(self)
        self.assistant = assistant

    def run(self):
        self.assistant.run()

if __name__ == "__main__":
    assistant = Assistant()
    app = QApplication(sys.argv)
    gui = AssistantGUI(assistant)
    gui.show()
    sys.exit(app.exec_())
