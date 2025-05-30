# Indy Safety Bot

A Python-based public safety chatbot for the Indy Civic Tech Hackathon 2025, designed to serve over 870,000+ residents of Indianapolis. The bot assists users with reporting hazards, receiving emergency alerts, and providing safety tips.

## Features

- **Hazard Reporting**: Users can report hazards by providing location and hazard type, which are stored in a SQLite database.
- **Emergency Alerts**: Provides information on current emergency alerts.
- **Safety Tips**: Offers safety tips to users.
- **Web Interface**: A simple web UI built with Flask for easy interaction.

## Requirements

- Python 3.6+
- Flask
- SQLite3

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/nehajosephh/Indy-Bot
   cd indy-safety-bot
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your web browser and navigate to `http://localhost:5000` to access the bot.

## Usage

- **Chat Interface**: Use the chat interface to interact with the bot. Type messages like "report hazard", "emergency alert", or "safety tip" to get responses.
- **Hazard Reporting**: Fill out the hazard report form on the web page to submit a hazard report.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. 
