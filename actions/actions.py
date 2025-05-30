# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests

class ActionReportHazard(Action):
    def name(self) -> Text:
        return "report_hazard"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the location and hazard type from the tracker
        location = tracker.get_slot("location")
        hazard_type = tracker.get_slot("hazard_type")
        
        if location and hazard_type:
            try:
                # This assumes your Flask app is running locally on port 5000
                response = requests.post(
                    "http://localhost:5000/api/issues/bot",
                    json={"description": hazard_type, "location": location}
                )
                if response.status_code == 200 or response.status_code == 201:
                    dispatcher.utter_message("Thank you for reporting the hazard.")
                else:
                    dispatcher.utter_message("There was an error saving your report. Please try again later.")
            except Exception as e:
                dispatcher.utter_message("There was an error saving your report. Please try again later.")
        else:
            dispatcher.utter_message("Please provide both the location and type of hazard.")
        
        return []

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []
