from langchain_community.document_loaders.parsers.language.cobol import CobolSegmenter

EXAMPLE_CODE = """
IDENTIFICATION DIVISION.
PROGRAM-ID. SampleProgram.
DATA DIVISION.
WORKING-STORAGE SECTION.
01  SAMPLE-VAR         PIC X(20)   VALUE 'Sample Value'.

PROCEDURE DIVISION.
A000-INITIALIZE-PARA.
    DISPLAY 'Initialization Paragraph'.
    MOVE 'New Value' TO SAMPLE-VAR.

A100-PROCESS-PARA.
    DISPLAY SAMPLE-VAR.
    STOP RUN.
"""


def test_extract_functions_classes() -> None:
    """Test that functions and classes are extracted correctly."""
    segmenter = CobolSegmenter(EXAMPLE_CODE)
    extracted_code = segmenter.extract_functions_classes()
    assert extracted_code == [
        "IDENTIFICATION DIVISION.\nPROGRAM-ID. SampleProgram.\nDATA DIVISION.",
        "WORKING-STORAGE SECTION.\n01  SAMPLE-VAR         PIC X(20)   VALUE 'Sample Value'.\n\nPROCEDURE DIVISION.",
        "A000-INITIALIZE-PARA.\n    DISPLAY 'Initialization Paragraph'.\n    MOVE 'New Value' TO SAMPLE-VAR.",
        "A100-PROCESS-PARA.\n    DISPLAY SAMPLE-VAR.\n    STOP RUN.",
    ]


def test_simplify_code() -> None:
    """Test that code is simplified correctly."""
    expected_simplified_code = ""
    segmenter = CobolSegmenter(EXAMPLE_CODE)
    simplified_code = segmenter.simplify_code()
    assert simplified_code.strip() == expected_simplified_code.strip()
