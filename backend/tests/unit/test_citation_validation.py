from app.services.citation_validation_service import CitationValidationService


class FakeDB:
    def scalars(self, statement):
        return []


def test_empty_citation_is_not_grounded():
    result = CitationValidationService(FakeDB()).validate([], candidate_chunk_ids=set())
    assert result.citation_valid is False
    assert result.citation_coverage == 0
    assert result.grounded_warning
