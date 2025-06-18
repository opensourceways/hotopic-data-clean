import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import requests
from app.data_collect_clean.collector import (
    BaseCollector,
    IssueCollector,
    CANNForumCollector,
    OpenUBMCForumCollector,
    get_forum_collector
)


# Fixtures
@pytest.fixture
def mock_session(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("requests.Session", lambda: mock)
    return mock


@pytest.fixture
def sample_issue_data():
    return {
        "uuid": "issue-123",
        "html_url": "http://issue.example.com",
        "title": "Test Issue",
        "created_at": "2024-01-01 12:00:00",
        "updated_at": "2024-01-02 12:00:00",
        "body": "Issue content",
        "state": "open"
    }


@pytest.fixture
def sample_forum_data():
    return {
        "topicId": "456",
        "title": "Test Topic",
        "createTime": "20240101120000",
        "lastPostTime": "20240102120000",
        "solved": 0
    }


# Base Tests
class TestBaseCollector:
    def test_request_success(self, mock_session):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.request.return_value = mock_response

        collector = BaseCollector()
        response = collector._request("GET", "http://test.com")
        assert response == mock_response

    def test_request_failure(self, mock_session):
        mock_session.request.side_effect = requests.exceptions.Timeout()

        collector = BaseCollector()
        response = collector._request("GET", "http://test.com")
        assert response is None


# IssueCollector Tests
class TestIssueCollector:
    @patch("your_module.validator.IssueValidator.validate", return_value=True)
    def test_collect_flow(self, mock_validate, mock_session, sample_issue_data):
        # Mock API responses
        mock_response = Mock()
        mock_response.json.return_value = {"data": [sample_issue_data]}
        mock_session.post.return_value = mock_response

        collector = IssueCollector("test", "dws_test")
        result = collector.collect(datetime(2024, 1, 1))

        assert len(result) == 1
        assert result[0]["id"] == "123"

    def test_data_processing(self, sample_issue_data):
        collector = IssueCollector("test", "dws_test")
        processed = collector._process_data([sample_issue_data])

        assert processed[0]["title"] == "Test Issue"
        assert processed[0]["state"] == "open"


# CANNForumCollector Tests
class TestCANNForumCollector:
    @patch.object(CANNForumCollector, "_fetch_page")
    def test_pagination(self, mock_fetch, mock_session):
        # Mock pagination responses
        mock_page1 = Mock()
        mock_page1.json.return_value = {
            "data": {
                "totalCount": 250,
                "resultList": [{"topicId": "1"}]
            }
        }
        mock_page2 = Mock()
        mock_page2.json.return_value = {
            "data": {
                "resultList": [{"topicId": "2"}]
            }
        }
        mock_fetch.side_effect = [mock_page1, mock_page2]

        collector = CANNForumCollector()
        result = collector.collect(datetime(2024, 1, 1))

        assert mock_fetch.call_count == 3  # 2 sections * (1 + 2 pages)

    def test_time_validation(self):
        collector = CANNForumCollector()
        valid = collector._is_valid_time("20240101120000", datetime(2024, 1, 1))
        assert valid is True

        invalid = collector._is_valid_time("20231231120000", datetime(2024, 1, 1))
        assert invalid is False


# OpenUBMCForumCollector Tests
class TestOpenUBMCForumCollector:
    @patch.object(OpenUBMCForumCollector, "_fetch_page")
    def test_category_filtering(self, mock_fetch):
        mock_fetch.return_value = {
            "topics": [
                {"category_id": 40, "created_at": "2024-01-01T12:00:00.000Z"},
                {"category_id": 30, "created_at": "2024-01-01T12:00:00.000Z"}
            ]
        }

        collector = OpenUBMCForumCollector()
        result = collector.collect(datetime(2024, 1, 1))

        assert len(result) == 1
        assert result[0]["category_id"] == 30


# Integration Tests
class TestIntegration:
    @patch("requests.Session")
    def test_full_collect_flow(self, mock_session):
        # Setup mock responses
        login_response = Mock()
        login_response.cookies.get.return_value = "fake_token"

        data_response = Mock()
        data_response.json.return_value = {
            "data": [
                {"uuid": "issue-123", "html_url": "valid_url", "title": "Test"}
            ]
        }

        mock_session.return_value.post.side_effect = [login_response, data_response]

        collector = IssueCollector("test", "dws_test")
        result = collector.collect(datetime(2024, 1, 1))

        assert len(result) == 1
        assert result[0]["title"] == "Test"


# Factory Tests
def test_forum_collector_factory():
    cann = get_forum_collector("cann")
    assert isinstance(cann, CANNForumCollector)

    with pytest.raises(ValueError):
        get_forum_collector("unknown")


# Validator Tests
def test_validator_integration():
    collector = CANNForumCollector()
    with patch.object(collector._validator, "validate", return_value=False):
        result = collector._is_valid("invalid_url")
        assert result is False


# Error Handling Tests
def test_login_failure_handling(mock_session):
    mock_session.post.return_value = Mock(status_code=401)

    collector = IssueCollector("test", "dws_test")
    with pytest.raises(ValueError):
        collector.collect(datetime(2024, 1, 1))


# Timing Tests
def test_rate_limiting(mock_session):
    mock_session.post.return_value = Mock(json=Mock(return_value={"data": []}))

    collector = IssueCollector("test", "dws_test")
    collector.collect(datetime(2024, 1, 1))

    calls = mock_session.post.call_args_list
    assert 0.4 <= (calls[1].kwargs.get('timeout', 30))
