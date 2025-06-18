import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from app.data_collect_clean.clean import (
    BaseCleaner,
    CANNForumCleaner,
    OpenGaussMailCleaner,
    FormattedRecord,
)


# Fixtures
@pytest.fixture
def mock_collector():
    return Mock()


@pytest.fixture
def sample_raw_data():
    return {
        'id': 123,
        'title': 'Test Title',
        'body': 'Test Body',
        'url': 'http://example.com',
        'created_at': datetime.now(),
        'closed': False,
        'history': '[]',
        'state': 'open'
    }


# BaseCleaner Tests
class TestBaseCleaner:
    @pytest.mark.parametrize("input_text,expected", [
        ('<p>Hello</p>', 'Hello'),
        ('中文Test123!@#', '中文Test123  '),
        ('', '')
    ])
    def test_basic_clean(self, input_text, expected):
        class ConcreteCleaner(BaseCleaner):
            def _get_system_prompt(self): return ""

            def _is_valid(self, title, body): return True

            @property
            def source_type(self): return "test"

        cleaner = ConcreteCleaner(Mock())
        assert cleaner._basic_clean(input_text) == expected

    def test_is_exist(self):
        cleaner = CANNForumCleaner(Mock())
        with patch('app.db.base.SessionLocal') as mock_session:
            mock_query = Mock()
            mock_session.return_value.query.return_value.filter.return_value.first.return_value = None
            assert cleaner._is_exist("123") is False


# CANNForumCleaner Tests
class TestCANNForumCleaner:
    @pytest.mark.parametrize("title,expected", [
        ('Valid Title', True),
        ('从入门到精通教程', False),
        ('学习笔记分享', False),
        ('训练营资料', False)
    ])
    def test_is_valid(self, title, expected):
        cleaner = CANNForumCleaner(Mock())
        assert cleaner._is_valid(title, "any body") == expected


# OpenGaussMailCleaner Tests
class TestOpenGaussMailCleaner:
    @pytest.mark.parametrize("title,body,expected", [
        ('正常问题', '详细描述', True),
        ('例会通知', '内容', False),
        ('升级通知', '', False),
        ('测试邮件', '包含会议主题', False)
    ])
    def test_is_valid(self, title, body, expected):
        cleaner = OpenGaussMailCleaner(Mock())
        assert cleaner._is_valid(title, body) == expected


# Integration Tests
class TestIntegration:
    @patch('openai.OpenAI')
    def test_full_processing(self, mock_openai, mock_collector, sample_raw_data):
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "Cleaned content"
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        # Configure collector
        mock_collector.collect.return_value = [sample_raw_data]

        # Test processing
        cleaner = CANNForumCleaner(mock_collector)
        processed = list(cleaner.process(datetime.now()))

        assert len(processed) == 1
        assert isinstance(processed[0], FormattedRecord)
        assert processed[0].clean_data == "Cleaned content"

    def test_invalid_data_handling(self, mock_collector):
        invalid_data = {'id': 456, 'title': '无效标题'}
        mock_collector.collect.return_value = [invalid_data]

        cleaner = CANNForumCleaner(mock_collector)
        with patch.object(cleaner, '_build_record', side_effect=ValueError) as mock_error:
            list(cleaner.process(datetime.now()))
            mock_error.assert_called()


# Exception Handling Tests
def test_api_retry_logic(mock_collector):
    cleaner = CANNForumCleaner(mock_collector)
    with patch.object(cleaner, '_llm_process', side_effect=Exception("API Error")) as mock_llm:
        with pytest.raises(Exception):
            cleaner._llm_process("test content")
        assert mock_llm.call_count == 3


# Helper Tests
def test_formatted_record_initialization(sample_raw_data):
    record = FormattedRecord(
        title=sample_raw_data['title'],
        body=sample_raw_data['body'],
        url=sample_raw_data['url'],
        created_at=sample_raw_data['created_at'],
        updated_at=None,
        topic_closed=False,
        history='[]',
        clean_data='cleaned',
        topic_summary='',
        source_type='test',
        source_id=123,
        source_closed=False
    )
    assert record.source_id == 123
    assert record.clean_data == 'cleaned'
