from notion_client import Client
import speech_recognition as sr
import pyttsx3

# Initialize the Notion client with your secret token
notion = Client(auth="secret")

recognizer = sr.Recognizer()
engine = pyttsx3.init()

# Set up initial recognizer settings for better performance
recognizer.dynamic_energy_threshold = True  # Enable dynamic adjustment of the energy threshold
recognizer.energy_threshold = 300  # Set a fixed energy threshold after testing, adjust this as needed

def speak(text):
    """Make the assistant speak out the given text."""
    engine.say(text)
    engine.runAndWait()

def listen():
    """Listen to the user's voice input and return the recognized text."""
    with sr.Microphone() as source:
        print("Adjusting for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=2)  # Increase duration to better handle ambient noise
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        print("Recognizing speech...")
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text.lower()  # Convert to lowercase for easier comparison
    except sr.UnknownValueError:
        # Handle the case where speech recognition does not understand the input
        speak("Sorry, I did not understand that. Please repeat.")
        print("Could not understand audio. Asking to repeat.")
        return listen()  # Recursively try listening again for improved interaction
    except sr.RequestError:
        speak("Could not request results; please check your network connection.")
        return None

def add_task_to_notion(name, due_date=None, status="To Do", priority="Low", notes=""):
    """Add a task to Notion with all properties."""
    try:
        response = notion.pages.create(
            parent={"database_id": "1020f3eb4b648073a754f5168f868812"},
            properties={
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": name
                            }
                        }
                    ]
                },
                "Due Date": {
                    "date": {
                        "start": due_date
                    } if due_date else None
                },
                "Status": {
                    "select": {
                        "name": status
                    }
                },
                "Priority": {
                    "select": {
                        "name": priority
                    }
                },
                "Notes": {
                    "rich_text": [
                        {
                            "text": {
                                "content": notes
                            }
                        }
                    ]
                }
            }
        )
        print("Task added to Notion successfully!")
        speak("Task added to Notion successfully!")
    except Exception as e:
        print("Failed to add task:", e)
        speak("Failed to add task.")

def read_tasks_from_notion():
    """Read tasks from the Notion database and speak them out."""
    try:
        # Query the database to get the list of tasks
        response = notion.databases.query(
            database_id="1020f3eb4b648073a754f5168f868812"
        )
        tasks = response.get("results", [])

        if not tasks:
            speak("There are no tasks in your Notion database.")
            return

        speak("Here are your tasks:")
        for task in tasks:
            task_name = task["properties"]["Name"]["title"][0]["text"]["content"]
            task_status = task["properties"]["Status"]["select"]["name"]
            task_priority = task["properties"]["Priority"]["select"]["name"]
            due_date = task["properties"]["Due Date"]["date"]
            task_due_date = due_date["start"] if due_date else "No due date"

            # Construct the task details for reading out loud
            task_details = f"Task: {task_name}, Status: {task_status}, Priority: {task_priority}, Due date: {task_due_date}."
            print(task_details)
            speak(task_details)

    except Exception as e:
        print("Failed to read tasks:", e)
        speak("Failed to read tasks from Notion.")

def main():
    """Main loop to handle user commands."""
    speak("Hello! How can I assist you today?")
    while True:
        command = listen()
        if command and command in ["exit", "quit", "stop"]:
            speak("Exiting assistant. Goodbye!")
            break
        elif command and "add task" in command:
            speak("Please provide the task name.")
            task_name = listen() or "Untitled Task"

            speak("Do you want to add a due date? Please say 'yes' or 'no'.")
            add_due_date_response = listen()
            task_due_date = None
            if add_due_date_response in ["yes", "yeah", "yup"]:
                speak("Please provide the due date in the format YYYY-MM-DD.")
                task_due_date = listen()
            
            speak("Please set the status: To Do, In Progress, or Done.")
            task_status = listen() or "To Do"

            speak("Please set the priority: Low, Medium, or High.")
            task_priority = listen() or "Low"

            speak("Would you like to add any notes?")
            task_notes = listen() or ""

            add_task_to_notion(
                name=task_name,
                due_date=task_due_date,
                status=task_status,
                priority=task_priority,
                notes=task_notes
            )
        elif command and "read task" in command:
            read_tasks_from_notion()
        elif command:
            speak(f"You said: {command}")

if __name__ == "__main__":
    main()
