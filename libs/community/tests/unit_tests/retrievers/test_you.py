import responses

from langchain_community.retrievers.you import YouRetriever

from ..utilities.test_you import (
    LIMITED_PARSED_OUTPUT,
    MOCK_PARSED_OUTPUT,
    MOCK_RESPONSE_RAW,
    NEWS_RESPONSE_PARSED,
    NEWS_RESPONSE_RAW,
    TEST_ENDPOINT,
)


class TestYouRetriever:
    @responses.activate
    def test_get_relevant_documents(self) -> None:
        responses.add(
            responses.GET, 
            f"{TEST_ENDPOINT}/search", 
            json=MOCK_RESPONSE_RAW, 
            status=200
        )
        query = "Test query text"
        you_wrapper = YouRetriever()
        results = you_wrapper.get_relevant_documents(query)
        expected_result = MOCK_PARSED_OUTPUT
        assert results == expected_result

    @responses.activate
    def test_invoke(self) -> None:
        responses.add(
            responses.GET,
            f"{TEST_ENDPOINT}/search",
            json=MOCK_RESPONSE_RAW,
            status=200
        )
        query = "Test query text"
        you_wrapper = YouRetriever()
        results = you_wrapper.invoke(query)
        expected_result = MOCK_PARSED_OUTPUT
        assert results == expected_result

    @responses.activate
    def test_invoke_max_docs(self) -> None:
        responses.add(
            responses.GET,
            f"{TEST_ENDPOINT}/search",
            json=MOCK_RESPONSE_RAW,
            status=200
        )
        query = "Test query text"
        you_wrapper = YouRetriever(k=2)
        results = you_wrapper.invoke(query)
        expected_result = [MOCK_PARSED_OUTPUT[0], MOCK_PARSED_OUTPUT[1]]
        assert results == expected_result

    @responses.activate
    def test_invoke_limit_snippets(self) -> None:
        responses.add(
            responses.GET,
            f"{TEST_ENDPOINT}/search",
            json=MOCK_RESPONSE_RAW,
            status=200
        )

        query = "Test query text"
        you_wrapper = YouRetriever(n_snippets_per_hit=1)
        results = you_wrapper.results(query)
        expected_result = LIMITED_PARSED_OUTPUT
        assert results == expected_result

    @responses.activate
    def test_invoke_news(self) -> None:
        responses.add(
            responses.GET,
            f"{TEST_ENDPOINT}/news",
            json=NEWS_RESPONSE_RAW,
            status=200
        )

        query = "Test news text"
        # ensure limit on number of docs returned
        you_wrapper = YouRetriever(endpoint_type='news')
        results = you_wrapper.results(query)
        expected_result = NEWS_RESPONSE_PARSED
        assert results == expected_result
