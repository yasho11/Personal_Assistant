# Voice-Activated Personal Assistant Documentation

## Overview

This project is a **Voice-Activated Personal Assistant** that integrates with various services to help manage tasks, events, and provide weather information. It leverages speech recognition, natural language processing, and GUI components to create an interactive user experience.

## Table of Contents

- [Features](#features)
- [Objectives](#objectives)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
  - [Clone the Repository](#clone-the-repository)
  - [Set Up the Environment](#set-up-the-environment)
  - [Install Dependencies](#install-dependencies)
  - [Configure API Keys and Environment Variables](#configure-api-keys-and-environment-variables)
  - [Set Up Google Calendar Credentials](#set-up-google-calendar-credentials)
- [Running the Assistant](#running-the-assistant)
- [Using the Assistant](#using-the-assistant)
  - [Voice Commands](#voice-commands)
  - [Manual Input (Optional)](#manual-input-optional)
- [Troubleshooting](#troubleshooting)
- [Conclusion](#conclusion)
- [Code](#code)

## Features

- **Task Management with Notion:**
  - Add tasks with names, types, and priorities.
  - Read and list tasks from your Notion database.
- **Event Scheduling with Google Calendar:**
  - Create events with names, times, and priorities.
  - Retrieve and list upcoming events from your calendar.
- **Weather Information:**
  - Get current weather reports for specified locations.
- **Voice Interaction:**
  - Use speech recognition to interact with the assistant.
  - Assistant responds with speech output for a hands-free experience.
- **Graphical User Interface (GUI):**
  - View tasks, events, and weather information in a GUI.
  - Refresh data and interact with the assistant through the GUI.

## Objectives

- **Robust Integration:** Seamlessly integrate speech recognition, natural language processing, Notion API, Google Calendar API, and OpenWeather API.
- **Error Handling:** Implement comprehensive error handling across all integrations to ensure reliability.
- **User Experience:** Provide a user-friendly interface with voice prompts and GUI components.
- **Performance Optimization:** Optimize response times and performance for smooth interaction.
- **Modular Design:** Structure the code in a modular fashion to facilitate maintenance and scalability.

## Prerequisites

- **Python 3.7 or higher**
- **Pip package manager**
- **Internet connection**
- **Microphone and Speakers**
- **Notion Account and API Key**
- **Google Account and API Credentials for Google Calendar**
- **OpenWeather API Key**

## Installation and Setup

### Clone the Repository

```bash
git clone https://github.com/yourusername/voice-assistant.git
cd voice-assistant
```

Alternatively, you can create a new directory and save the code into a file named `assistant.py`.

### Set Up the Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use venv\Scripts\activate
```

### Install Dependencies

Install all required Python packages using `pip`.

```bash
pip install -r requirements.txt
```

If you don't have a `requirements.txt`, install the following packages:

```bash
pip install requests python-dotenv speechrecognition pyttsx3 spacy dateparser notion-client google-api-python-client google-auth-httplib2 google-auth-oauthlib PyQt5
```

**Note:** You may need to install additional system packages depending on your OS, especially for `pyttsx3` and `PyQt5`.

### Configure API Keys and Environment Variables

Create a `.env` file in the root directory of your project to store your API keys and other sensitive information.

```bash
touch .env
```

Add the following variables to your `.env` file:

```env
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
OPENWEATHER_API_KEY=your_openweather_api_key
```

Replace `your_notion_api_key`, `your_notion_database_id`, and `your_openweather_api_key` with your actual keys.

#### Obtaining API Keys:

- **Notion API Key and Database ID:**
  - Sign up for a Notion account and create an integration at [Notion Developers](https://developers.notion.com/).
  - Share your database with the integration.
  - Copy the Internal Integration Token as your `NOTION_API_KEY`.
  - Copy the Database ID from the URL of your Notion database.

- **OpenWeather API Key:**
  - Sign up at [OpenWeatherMap](https://openweathermap.org/api) and obtain an API key.

### Set Up Google Calendar Credentials

#### Enable Google Calendar API:

1. Go to the [Google Developers Console](https://console.developers.google.com/).
2. Create a new project or select an existing one.
3. Enable the Google Calendar API for your project.
4. Create OAuth 2.0 Client Credentials:
   - Go to **APIs & Services** > **Credentials**.
   - Click **Create Credentials** > **OAuth client ID**.
   - Choose **Desktop app** and provide a name.
   - Download the `credentials.json` file and place it in your project directory.

### Install SpaCy Model

Install the English language model for SpaCy.

```bash
python -m spacy download en_core_web_sm
```

## Running the Assistant

Run the assistant using the following command:

```bash
python assistant.py
```

This will launch the GUI and start the assistant in a separate thread.

## Using the Assistant

### Voice Commands

Interact with the assistant using voice commands. Here are some examples:

- **Add a Task:**
  - "Add a task to finish the report."
  - "Create a new task called 'Prepare presentation'."
- **Read Tasks:**
  - "Show me my tasks."
  - "List all my tasks."
- **Add an Event:**
  - "Schedule an event 'Team meeting' tomorrow at 10 AM."
  - "Add an event called 'Doctor's appointment' on Friday at 2 PM."
- **Read Events:**
  - "What is on my schedule?"
  - "Read my events."
- **Get Weather Information:**
  - "What's the weather like today?"
  - "Tell me the weather in New York."
- **Exit the Assistant:**
  - "Exit."
  - "Quit."

**Note:** Speak clearly and at a moderate pace for better recognition.

### Manual Input (Optional)

If you prefer to test the assistant with text input, you can modify the `run` method in the `Assistant` class:

```python
def run(self):
    self.speak("Hello! How can I assist you today?")
    while True:
        command = input("Enter command: ")
        if command:
            intent, entities, priority = self.parse_command(command)
            if intent:
                self.handle_intent(intent, entities, priority)
            else:
                self.speak("I'm sorry, I didn't catch that. Could you please repeat?")
        else:
            self.speak("No command detected. Please try again.")
```

## Troubleshooting

- **Speech Recognition Issues:**
  - Ensure your microphone is properly connected and not muted.
  - Reduce background noise.
- **API Errors:**
  - Verify that your API keys and credentials are correctly set up.
  - Check your internet connection.
- **Module Not Found Errors:**
  - Ensure all dependencies are installed.
  - Activate your virtual environment if using one.
- **Google Calendar Authentication:**
  - Delete the `token.json` file if authentication issues persist and rerun the assistant to reauthenticate.
- **Notion Integration Errors:**
  - Ensure your Notion integration has access to the database.
  - Double-check your `NOTION_API_KEY` and `NOTION_DATABASE_ID`.

## Conclusion

This Voice-Activated Personal Assistant integrates powerful features to help manage your daily tasks and events, as well as provide up-to-date weather information. With robust error handling and optimized performance, it aims to deliver a seamless user experience.

Feel free to explore and customize the assistant to better suit your needs!

