from typing import Any
from langchain.embeddings.base import Embeddings

from langchain.schema import BaseOutputParser

class VectorSQLOutputParser(BaseOutputParser):
    """Output Parser for Vector SQL
    1. finds for `NeuralArray()` and replace it with the embedding
    2. finds for `DISTANCE()` and replace it with the distance name in backend SQL
    """
    
    model: Embeddings
    """Embedding model to extract embedding for entity"""
    distance_func_name: str = 'distance'
    """Distance name for vector SQL"""
    
    class Config:
        arbitrary_types_allowed = 1
    
    @classmethod
    def from_embeddings(cls, model: Embeddings, distance_func_name: str ='distance', **kwargs: Any):
        return cls(model=model, distance_func_name=distance_func_name, **kwargs)
    
    def parse(self, text: str):
        start = text.find('NeuralArray(')
        if start > 0:
            _matched = text[text.find('NeuralArray(')+len('NeuralArray('):]
            end = _matched.find(')') + start + len('NeuralArray(') + 1
            entity = _matched[:_matched.find(')')]
            vecs = self.model.embed_query(entity)
            vecs_str = '[' + ','.join(map(str, vecs)) + ']'
            _sql_str_compl = text.replace('DISTANCE', self.distance_func_name).replace(text[start:end], vecs_str)
            if _sql_str_compl[-1] == ';':
                _sql_str_compl = _sql_str_compl[:-1]
            text = _sql_str_compl
        return text     