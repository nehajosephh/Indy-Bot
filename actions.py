from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

class ValidateHazardReportForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_hazard_report_form"

    def validate_location(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate location value."""
        if slot_value and len(slot_value.strip()) > 2:
            return {"location": slot_value}
        else:
            dispatcher.utter_message(text="Please provide a valid location (street name or county).")
            return {"location": None}

    def validate_hazard_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate hazard type value."""
        if slot_value and len(slot_value.strip()) > 0:
            return {"hazard_type": slot_value}
        else:
            dispatcher.utter_message(text="Please specify what type of hazard you're reporting.")
            return {"hazard_type": None}