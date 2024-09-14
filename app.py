import speech_recognition as sr
import pyttsx3

recognizer = sr.Recognizer()
engine = pyttsx3.init()

def speak(text):
    engine.say(text)
    engine.runAndWait()

def listen():
    with sr.Microphone() as source:
        print("Adjusting for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        print("Recognizing speech...")
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        text = "Sorry, I did not understand that."
        print(text)
        speak(text)
        return ""
    except sr.RequestError:
        text = "Could not request results; check your network connection."
        print(text)
        speak(text)
        return ""

def main():
    speak("Hello! How can I assist you today?")
    while True:
        command = listen()
        if command.lower() in ["exit", "quit", "stop"]:
            speak("Exiting assistant. Goodbye!")
            print("Exiting assistant.")
            break
        elif command:
            # Handle your commands here
            # For example:
            speak(f"You said: {command}")
            # You can add more functionality as needed

if __name__ == "__main__":
    main()