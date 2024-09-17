import os
import sys
import logging
from dotenv import load_dotenv
from notion_client import Client
import speech_recognition as sr
import pyttsx3
import spacy

# Load environment variables from .env file
load_dotenv(dotenv_path='myenv/.env')


# Configure logging
logging.basicConfig(level=logging.ERROR, filename='assistant.log')

# Initialize the Notion client with your secret token from environment variables
notion = Client(auth=os.getenv("NOTION_API_KEY"))

# Initialize speech recognition and text-to-speech engine
recognizer = sr.Recognizer()
engine = pyttsx3.init()

# Load spaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Set up initial recognizer settings for better performance
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300

def speak(text):
    """Make the assistant speak out the given text."""
    engine.say(text)
    engine.runAndWait()

def listen():
    """Listen to the user's voice input and return the recognized text."""
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        print("Recognizing speech...")
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text.lower()
    except sr.UnknownValueError:
        speak("Sorry, I did not understand that. Please repeat.")
        return None
    except sr.RequestError:
        speak("Could not request results; please check your network connection.")
        return None

def add_task_to_notion(task_name, task_type):
    """Add a task to Notion with only name and type as rich text."""
    try:
        notion.pages.create(
            parent={"database_id": os.getenv("NOTION_DATABASE_ID")},
            properties={
                "Name": {"title": [{"text": {"content": task_name}}]},
                "Type": {"rich_text": [{"text": {"content": task_type}}]}
            }
        )
        speak("Task added to Notion successfully!")
    except Exception as e:
        logging.error(f"Failed to add task: {e}")
        speak("Failed to add task due to an error. Please check the logs.")

def read_tasks_from_notion():
    """Read tasks from the Notion database and speak only name and type."""
    try:
        response = notion.databases.query(database_id=os.getenv("NOTION_DATABASE_ID"))
        tasks = response.get("results", [])

        if not tasks:
            speak("There are no tasks in your Notion database.")
            return

        speak("Here are your tasks:")
        for task in tasks:
            name_property = task["properties"]["Name"]["title"]
            type_property = task["properties"]["Type"]["rich_text"]

            task_name = name_property[0]["text"]["content"] if name_property else "Unnamed Task"
            task_type = type_property[0]["text"]["content"] if type_property else "No Type Specified"

            task_details = f"Task: {task_name}, Type: {task_type}."
            speak(task_details)
    except Exception as e:
        logging.error(f"Failed to read tasks from Notion: {e}")
        speak("Failed to read tasks from Notion due to an error. Please check the logs.")

def recognize_intent(command):
    """Recognize the intent of the command using NLP."""
    doc = nlp(command)
    intents = {
        "add_task": ["add", "create", "insert", "new"],
        "read_task": ["read", "show", "list", "get"],
        "exit": ["exit", "quit", "stop", "end"],
    }

    for token in doc:
        for intent, keywords in intents.items():
            if token.lemma_ in keywords:
                return intent
    return "unknown"

def handle_intent(intent):
    """Handle the recognized intent."""
    if intent == "add_task":
        speak("Please provide the task name.")
        task_name = listen()
        if not task_name:
            speak("No task name provided. Operation cancelled.")
            return

        speak("Please provide the task type.")
        task_type = listen()
        if not task_type:
            speak("No task type provided. Defaulting to General.")
            task_type = "General"

        speak(f"Adding task '{task_name}' of type '{task_type}' to Notion.")
        add_task_to_notion(task_name=task_name, task_type=task_type)

    elif intent == "read_task":
        read_tasks_from_notion()

    elif intent == "exit":
        speak("Exiting assistant. Goodbye!")
        sys.exit()

    else:
        speak("Sorry, I didn't understand that command. Please try again.")

def main():
    """Main loop to handle user commands."""
    speak("Adjusting for ambient noise, please wait.")
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

    speak("Hello! How can I assist you today?")
    while True:
        command = listen()
        if command:
            intent = recognize_intent(command)
            handle_intent(intent)

if __name__ == "__main__":
    main()
