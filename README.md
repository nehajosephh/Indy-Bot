# Indy-Bot

A Rasa-based conversational AI assistant built in Python and HTML.

---

## Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Project Structure](#project-structure)
* [Installation](#installation)
* [Usage](#usage)
* [Training](#training)
* [Custom Actions](#custom-actions)
* [Configuration](#configuration)
* [Troubleshooting](#troubleshooting)
* [Contributing](#contributing)
* [License](#license)

---

## Overview

**Indy-Bot** is a chatbot built with the Rasa framework. It leverages intent recognition, dialogue management, and customizable actions to engage with users in a conversational experience.

---

## Features

* **Intent-driven conversations** powered via Rasa NLU (see `domain.yml`)
* **Stories** or conversation flows defined to guide dialogs (see `config.yml`)
* **Custom actions** implemented in `actions.py` to integrate dynamic functionality or backend logic
* **HTML templates** for crafting response messages (folder: `templates/`)
* Pre-trained or sample models stored in the `models/` directory

---

## Project Structure

```
Indy-Bot/
├── .rasa/             # Rasa internal caching (auto-generated)
├── data/              # Training data (e.g., NLU and Stories)
├── models/            # Saved Rasa model files
├── templates/         # HTML or response templates
├── actions.py         # Custom action code
├── app.py             # Main application file to run the bot
├── config.yml         # Rasa configuration (pipeline & policies)
├── domain.yml         # Intents, entities, slots, responses, actions
├── indiana_chatbot.db # Optional: sample or persistent database
├── LICENSE            # MIT open-source license
└── README.md          # Placeholder — to be replaced with this version
```

---

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/nehajosephh/Indy-Bot.git
   cd Indy-Bot
   ```

2. **Set up a Python virtual environment (recommended):**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install rasa
   ```

   Add any other required packages as needed (e.g., `rasa-sdk`, database drivers, etc.).

---

## Usage

### Training the Model

If training data exists in `data/`:

```bash
rasa train
```

This generates a new model inside the `models/` directory.

### Running the Bot

To launch the Rasa server with the action server:

```bash
rasa run actions &
rasa shell
```

Alternatively, use `app.py` if it provides a custom interface:

```bash
python app.py
```

---

## Training

Training configurations are defined in `config.yml`:

* **Pipeline**: Defines NLU components (e.g., tokenizers, intent classifiers)
* **Policies**: Dictates dialog management behavior

Make sure to adjust hyperparameters or components as needed for your use case.

---

## Custom Actions

Custom logic goes in `actions.py`. Typical structure:

```python
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class YourCustomAction(Action):
    def name(self):
        return "action_name"

    def run(self, dispatcher, tracker, domain):
        # Your action logic here
        dispatcher.utter_message(text="Your response")
        return []
```

To register actions:

* Ensure `domain.yml` lists the action in the `actions:` section.
* Run the action server alongside the Rasa server (`rasa run actions`).

---

## Configuration

Key files:

* **domain.yml**: Defines intents, responses, slots, entities, and actions.
* **config.yml**: Setup of NLU pipeline and dialog policies.
* **templates/**: Stores HTML or rich response templates.

Make any necessary edits to align with your conversational goals.

---

## Troubleshooting

* **Training errors**: Ensure training data formats and domain definitions are correct.
* **Actions not working**: Double-check naming, ensure action server is running.
* **Template issues**: Confirm proper paths and template syntax.

---

## Contributing

Contributions are welcome! Feel free to:

* Add new intents, stories, or responses
* Enhance custom actions
* Improve conversational flows or integrations
* Submit pull requests or file issues for improvements

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more details.

---
