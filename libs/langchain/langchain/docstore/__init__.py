"""**Docstores** are classes to store and load Documents.

The **Docstore** is a simplified version of the Document Loader.

**Class hierarchy:**

.. code-block::

    Docstore --> <name> # Examples: InMemoryDocstore, Wikipedia

**Main helpers:**

.. code-block::

    Document, AddableMixin
"""
from typing import Any

from langchain_core._api import caller_aware_warn

from langchain.utils.interactive_env import is_interactive_env


def __getattr__(name: str) -> Any:
    from langchain_community import docstore

    # If not in interactive env, raise warning.
    if not is_interactive_env():
        caller_aware_warn(
            "Importing docstores from langchain is deprecated. Importing from "
            "langchain will no longer be supported as of langchain==0.2.0. "
            "Please import from langchain-community instead:\n\n"
            f"`from langchain_community.docstore import {name}`.\n\n"
            "To install langchain-community run `pip install -U langchain-community`.",
        )

    return getattr(docstore, name)


__all__ = ["DocstoreFn", "InMemoryDocstore", "Wikipedia"]
