from typing import (
    Any,
    List,
    Tuple,
)


prefixes = {
    "owl": """PREFIX owl: <http://www.w3.org/2002/07/owl#>\n""",
    "rdf": """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n""",
    "rdfs": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n""",
    "xsd": """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n""",
}

cls_query_rdf = prefixes["rdfs"] + (
    """SELECT DISTINCT ?cls ?com\n"""
    """WHERE { \n"""
    """    ?instance a ?cls . \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)

cls_query_rdfs = prefixes["rdfs"] + (
    """SELECT DISTINCT ?cls ?com\n"""
    """WHERE { \n"""
    """    ?instance a/rdfs:subClassOf* ?cls \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)

cls_query_owl = cls_query_rdfs

rel_query_rdf = prefixes["rdfs"] + (
    """SELECT DISTINCT ?rel ?com\n"""
    """WHERE { \n"""
    """    ?subj ?rel ?obj . \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)

rel_query_rdfs = prefixes["rdf"] + prefixes["rdfs"] + (
    """SELECT DISTINCT ?rel ?com\n"""
    """WHERE { \n"""
    """    ?rel a/rdfs:subPropertyOf* rdf:Property . \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)

op_query_owl = prefixes["rdfs"] + prefixes["owl"] + (
    """SELECT DISTINCT ?op ?com\n"""
    """WHERE { \n"""
    """    ?op a/rdfs:subPropertyOf* owl:ObjectProperty . \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)

dp_query_owl = prefixes["rdfs"] + prefixes["owl"] + (
    """SELECT DISTINCT ?dp ?com\n"""
    """WHERE { \n"""
    """    ?dp a/rdfs:subPropertyOf* owl:DatatypeProperty . \n"""
    """    OPTIONAL { ?cls rdfs:comment ?com } \n"""
    """}"""
)


class RdfGraph:
    """
    RDFlib wrapper for graph operations.
    Modes:
    * "local": Local file - can be queried and changed
    * "online": Online file - can only be queried
    * "store": Triple store - can be queried and changed
    """

    def __init__(
        self,
        url: str = None,
        query_endpoint: str = None,
        update_endpoint: str = None,
        standard: str = "rdf",
        local_file: str = None,
    ) -> None:
        self.standard = standard
        self.local_file = local_file

        try:
            import rdflib
            from rdflib.plugins.stores import sparqlstore
            from rdflib.graph import DATASET_DEFAULT_GRAPH_ID as default
        except ImportError:
            raise ValueError(
                "Could not import rdflib python package. "
                "Please install it with `pip install rdflib`."
            )
        if self.standard not in (supported_standards := ("rdf", "rdfs", "owl")):
            raise ValueError(f"Invalid standard. Supported standards are: {supported_standards}.")

        if not url and (not query_endpoint or not update_endpoint) or url and query_endpoint and update_endpoint:
            raise ValueError(
                "Could not unambiguously initialize the graph wrapper. "
                "Specify either a file (local or online) via the url "
                "or a triple store via the endpoints."
            )

        if url:
            _format = None
            if url.endswith('.ttl'):
                _format = 'ttl'
            if 'http' in url:
                self.mode = "local"
            else:
                self.mode = "online"
            self.graph = rdflib.Graph()
            self.graph.parse(url, format=_format)

        if query_endpoint and update_endpoint:
            self.mode = "store"
            self._store = sparqlstore.SPARQLUpdateStore()
            self._store.open((query_endpoint, update_endpoint))
            self.graph = rdflib.Graph(self._store, identifier=default)

        # Verify that the graph was loaded
        if not len(self.graph):
            raise AssertionError(f"The graph is empty.")

        # Set schema
        self.schema = ""
        self.load_schema()

    @property
    def get_schema(self) -> str:
        """
        Returns the schema of the graph database.
        """
        return self.schema

    def query(self, query: str) -> List[Tuple[Any]]:
        """
        Query the graph.
        """
        from rdflib.exceptions import ParserError

        try:
            res = self.graph.query(query)
        except ParserError as e:
            raise ValueError("Generated SPARQL statement is invalid\n" f"{e}")
        return [r for r in res]

    def update(self, query: str) -> None:
        """
        Update the graph.
        """
        from rdflib.exceptions import ParserError

        try:
            self.graph.update(query)
        except ParserError as e:
            raise ValueError("Generated SPARQL statement is invalid\n" f"{e}")
        if self.local_file:
            self.graph.serialize(destination=self.local_file)
        else:
            raise ValueError(f"No target file specified for saving the updated file.")

    @staticmethod
    def _get_local_name(iri: str) -> str:
        if '#' in iri:
            local_name = iri.split('#')[-1]
        elif '/' in iri:
            local_name = iri.split('/')[-1]
        else:
            raise ValueError(f"Unexpected IRI '{iri}', contains neither '#' nor '/'.")
        return local_name

    def _res_to_str(self, res, var: str) -> str:
        return res[var].n3() + ' (' + self._get_local_name(res[var]) + ', ' + str(res["com"]) + ')'

    def load_schema(self) -> None:
        """
        Load the graph schema information.
        """

        def _rdf_s_schema(classes, relationships) -> str:
            return (
                f"""In the following, each IRI is followed by the local name and """
                f"""optionally its description in parentheses. \n"""
                f"""The RDF graph supports the following node types:\n"""
                f"""{", ".join([self._res_to_str(r, "cls") for r in classes])}\n"""
                f"""The RDF graph supports the following relationships:\n"""
                f"""{", ".join([self._res_to_str(r, "rel") for r in relationships])}\n"""
            )

        if self.standard == "rdf":
            clss = self.query(cls_query_rdf)
            rels = self.query(rel_query_rdf)
            self.schema = _rdf_s_schema(clss, rels)
        elif self.standard == "rdfs":
            clss = self.query(cls_query_rdfs)
            rels = self.query(rel_query_rdfs)
            self.schema = _rdf_s_schema(clss, rels)
        elif self.standard == "owl":
            clss = self.query(cls_query_owl)
            ops = self.query(cls_query_owl)
            dps = self.query(cls_query_owl)
            self.schema = (
                f"""In the following, each IRI is followed by the local name and """
                f"""optionally its description in parentheses. \n"""
                f"""The OWL graph supports the following node types:\n"""
                f"""{", ".join([self._res_to_str(r, "cls") for r in clss])}\n"""
                f"""The OWL graph supports the following object properties, """
                f"""i.e., relationships between objects:\n"""
                f"""{", ".join([self._res_to_str(r, "op") for r in ops])}\n"""
                f"""The OWL graph supports the following data properties, """
                f"""i.e., relationships between objects and literals:\n"""
                f"""{", ".join([self._res_to_str(r, "dp") for r in dps])}\n"""
            )
        else:
            raise ValueError(f"Mode '{self.standard}' is currently not supported.")
