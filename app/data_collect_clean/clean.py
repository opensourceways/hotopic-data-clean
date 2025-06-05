import re
import logging
from abc import ABC, abstractmethod
from retrying import retry
from openai import OpenAI
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)


class BaseCleaner(ABC):
    def __init__(self, collector):
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url
        )
        self.collector = collector
        self.model = settings.llm_model
        self.system_prompt = self._get_system_prompt()

    @abstractmethod
    def _get_system_prompt(self):
        pass

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def _llm_process(self, content):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content},
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            raise

    def _basic_clean(self, text):
        text = re.sub(r'<.*?>', '', text)
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、]', ' ', text).strip()

    def process(self):

        for raw_data in self.collector.fetch_data():
            try:
                record = self._build_record(raw_data)
                yield self._format_for_db(record)
            except Exception as e:
                logger.error(f"处理失败: {raw_data.get('id', '未知ID')} - {str(e)}")

    def _build_record(self, raw_data):

        if not all(k in raw_data for k in ('id', 'title', 'body')):
            raise ValueError("缺失必要字段")

        llm_content = self._llm_process(f"标题：{raw_data['title']}\n内容：{raw_data['body']}")

        return {
            'base_data': {
                'id': raw_data['id'],
                'title': raw_data['title'],
                'body': raw_data['body'],
                'url': raw_data.get('url', ''),
                'createdat': raw_data.get('createdat', datetime.now()),
                'topicclosed': raw_data.get('closed', False),
                'history': raw_data.get('history', '[]')
            },
            'processed': {
                'cleandata': self._basic_clean(llm_content),
                'topicsummary': llm_content[:100] + '...' if len(llm_content) > 100 else llm_content
            }
        }

    def _format_for_db(self, record):
        return {
            **record['base_data'],
            'cleandata': record['processed']['cleandata'],
            'topicsummary': record['processed']['topicsummary'],
            'sourcetype': self.source_type,
            'sourceid': record['base_data']['id']
        }

    @property
    @abstractmethod
    def source_type(self):
        pass


class CANNForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.cann_forum_prompt


class CANNIssueCleaner(CANNForumCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.cann_issue_prompt


class OpenUBMCForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.openubmc_forum_prompt


class OpenUBMCIssueCleaner(OpenUBMCForumCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.openubmc_issue_prompt
