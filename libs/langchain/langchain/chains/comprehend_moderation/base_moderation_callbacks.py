from typing import Any, Dict

class BaseModerationCallbackHandler:
    
    def __init__(self):
        if self._is_method_unchanged(BaseModerationCallbackHandler.on_after_pii, self.on_after_pii) and \
           self._is_method_unchanged(BaseModerationCallbackHandler.on_after_toxicity, self.on_after_toxicity) and \
           self._is_method_unchanged(BaseModerationCallbackHandler.on_after_intent, self.on_after_intent):
            raise NotImplementedError("Subclasses must override at least one of on_after_pii(), on_after_toxicity(), or on_after_intent() functions.")
        
    def _is_method_unchanged(self, base_method, derived_method):
        return base_method.__qualname__ == derived_method.__qualname__
    
    async def on_after_pii(self, 
                           moderation_beacon: Dict[str, Any], 
                           unique_id: str,
                           **kwargs: Any) -> None:
        """Run after PII validation is complete."""
        raise NotImplementedError("Subclasses should implement this async method.")

    async def on_after_toxicity(self, 
                                moderation_beacon: Dict[str, Any], 
                                unique_id: str,
                                **kwargs: Any) -> None:
        """Run after Toxicity validation is complete."""
        raise NotImplementedError("Subclasses should implement this async method.")

    async def on_after_intent(self, 
                              moderation_beacon: Dict[str, Any], 
                              unique_id: str,
                              **kwargs: Any) -> None:
        """Run after Toxicity validation is complete."""
        raise NotImplementedError("Subclasses should implement this async method.")
    
    @property
    def pii_callback(self) -> bool:
        return self.on_after_pii.__func__ is not BaseModerationCallbackHandler.on_after_pii

    @property
    def toxicity_callback(self) -> bool:
        return self.on_after_toxicity.__func__ is not BaseModerationCallbackHandler.on_after_toxicity

    @property
    def intent_callback(self) -> bool:
        return self.on_after_intent.__func__ is not BaseModerationCallbackHandler.on_after_intent