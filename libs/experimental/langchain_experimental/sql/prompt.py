# flake8: noqa
from langchain.output_parsers.list import CommaSeparatedListOutputParser
from langchain.prompts.prompt import PromptTemplate


PROMPT_SUFFIX = """Only use the following tables:
{table_info}

Question: {input}"""


_myscale_prompt = """You are a MyScale expert. Given an input question, first create a syntactically correct MyScale query to run, then look at the results of the query and return the answer to the input question.
MyScale queries has a vector distance function called `DISTANCE(column, array)` to compute relevance to the user's question and sort the feature array column by the relevance. 
When the query is asking for {top_k} closest row, you have to use this distance function to calculate distance to entity's array on vector column and order by the distance to retrieve relevant rows.

*NOTICE*: `DISTANCE(column, array)` only accept an array column as its first argument and a `NeuralArray(entity)` as its second argument. You also need a user defined function called `NeuralArray(entity)` to retrieve the entity's array. 

Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per MyScale. You should only order according to the distance function.
Never query for all columns from a table. You must query only the columns that are needed to answer the question. Wrap each column name in double quotes (") to denote them as delimited identifiers.
Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
Pay attention to use today() function to get the current date, if the question involves "today". `ORDER BY` clause should always be after `WHERE` clause. DO NOT add semicolon to the end of SQL. Pay attention to the comment in table schema.

Use the following format:

Question: "Question here"
SQLQuery: "SQL Query to run"
SQLResult: "Result of the SQLQuery"
Answer: "Final answer here"
"""

MYSCALE_PROMPT = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],
    template=_myscale_prompt + PROMPT_SUFFIX,
)


SQL_PROMPTS = {
    "myscale": MYSCALE_PROMPT,
}
