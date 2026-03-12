import pytest

@pytest.fixture
def empty_stage():
    from cognitive_bridge.models.stage import CompositionStage
    return CompositionStage(project_id="test-project", project_name="Test Project")
