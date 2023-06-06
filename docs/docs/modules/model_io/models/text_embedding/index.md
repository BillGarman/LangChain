---
sidebar_position: 2
---
# Text embedding models

This documentation goes over how to use the Embedding class in LangChain.

The Embedding class is a class designed for interfacing with embeddings. There are lots of Embedding providers (OpenAI, Cohere, Hugging Face, etc) - this class is designed to provide a standard interface for all of them.

Embeddings create a vector representation of a piece of text. This is useful because it means we can think about text in the vector space, and do things like semantic search where we look for pieces of text that are most similar in the vector space.

The base Embedding class in LangChain exposes two methods: `embed_documents` and `embed_query`. The largest difference is that these two methods have different interfaces: one works over multiple documents, while the other works over a single document. Besides this, another reason for having these as two separate methods is that some embedding providers have different embedding methods for documents (to be searched over) vs queries (the search query itself).
