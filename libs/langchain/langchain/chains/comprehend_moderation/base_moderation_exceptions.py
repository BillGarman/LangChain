class ModerationPiiError(Exception):
    """Exception raised if PII entities are detected.

    Attributes:
        message -- explanation of the error
    """
    def __init__(self, message="The prompt contains PII entities and cannot be processed"):
        self.message = message
        super().__init__(self.message)
        
class ModerationToxicityError(Exception):
    """Exception raised if Toxic entities are detected.

    Attributes:
        message -- explanation of the error
    """
    def __init__(self, message="The prompt contains toxic content and cannot be processed"):
        self.message = message
        super().__init__(self.message)
        
class ModerationIntentionError(Exception):
    """Exception raised if Intention entities are detected.

    Attributes:
        message -- explanation of the error
    """
    def __init__(self, message="The prompt indicates an un-desired intent and cannot be processed"):
        self.message = message
        super().__init__(self.message)
