"""Unit tests for Fallacy Removal chain - WIP for proper input"""
# from langchain.chains.fallacy_removal.base import FallacyChain

TEXT_ONE = """ This text is bad.

Fallacy Revision Request: Make it better.

Fallacy Revision:"""

TEXT_TWO = """ This text is bad.\n\n"""

TEXT_THREE = """ This text is bad.

Fallacy Revision request: Make it better.

Fallacy Revision: Better text"""


# def test_fallacy_critique_parsing() -> None:
#     """Test parsing of fallacy critique text."""
#     for text in [TEXT_ONE, TEXT_TWO, TEXT_THREE]:
#         fallacy_critique = FallacyChain._parse_critique(text)
# 
#         assert (
#             fallacy_critique.strip() == "This text is bad."
#        ), f"Failed on {text} with {fallacy_critique}"
