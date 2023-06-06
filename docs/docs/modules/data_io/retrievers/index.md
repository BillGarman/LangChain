# Retrievers


The retriever interface is a generic interface that makes it easy to combine documents with
language models. This interface exposes a `get_relevant_documents` method which takes in a query
(a string) and returns a list of documents.
