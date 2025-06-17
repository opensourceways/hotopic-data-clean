import re
import logging
from abc import ABC, abstractmethod
from retrying import retry
from openai import OpenAI
from datetime import datetime
from config.settings import settings
from tqdm import tqdm


logger = logging.getLogger(__name__)


class Record:
    def __init__(self, base_data, processed):
        self.base_data = base_data
        self.processed = processed


class FormattedRecord:
    def __init__(self, id, title, body, url, created_at, updated_at, topic_closed, history, clean_data, topic_summary,
                 source_type, source_id, source_closed):
        self.id = id
        self.title = title
        self.body = body
        self.url = url
        self.created_at = created_at
        self.updated_at = updated_at
        self.topic_closed = topic_closed
        self.history = history
        self.clean_data = clean_data
        self.topic_summary = topic_summary
        self.source_type = source_type
        self.source_id = source_id
        self.source_closed = source_closed


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

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
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

    def process(self, start_date):
        data_before_clean = self.collector.collect(start_date)
        with open('html_urls.txt', 'w', encoding='utf-8') as f:
            for data in data_before_clean:
                if url := data.get('html_url'):
                    f.write(f"{url}\n")
        for raw_data in tqdm(data_before_clean, desc="Processing data"):
            try:
                record = self._build_record(raw_data)
                yield record
            except Exception as e:
                logger.error(f"处理失败: {raw_data.get('id', '未知ID')} - {str(e)}")

    def _build_record(self, raw_data):
        if 'uuid' in raw_data:
            raw_data['id'] = raw_data['uuid'].split('-')[-1]
        if not all(k in raw_data for k in ('id', 'title', 'body')):
            raise ValueError("缺失必要字段")
        # if re.search(r'从入门到精通|学习|指导|笔记|分享|训练营', raw_data['title']):
        #     raise ValueError("标题包含无效关键词")
        created_at = raw_data.get('created_at', datetime.now())
        if isinstance(created_at, datetime):
            created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
        updated_at = raw_data.get('updated_at', datetime.now())
        if isinstance(updated_at, datetime):
            updated_at = updated_at.strftime('%Y-%m-%d %H:%M:%S')
        llm_content = self._llm_process(f"标题：{raw_data['title']}\n内容：{raw_data['body']}")
        url = raw_data.get('html_url', '') if self.source_type == "issue" else raw_data.get('url', '')
        return FormattedRecord(
            id=raw_data['id'],
            title=raw_data['title'],
            body=raw_data['body'],
            url=url,
            created_at=created_at,
            updated_at=updated_at,
            topic_closed=raw_data.get('closed', False),
            history=raw_data.get('history', '[]'),
            clean_data=self._basic_clean(llm_content),
            topic_summary='',
            source_type=self.source_type,
            source_id=raw_data['id'],
            source_closed=raw_data.get('state', '') == 'closed'
        )

    @property
    @abstractmethod
    def source_type(self):
        pass


def get_issue_cleaner(community, collector):
    if community == "cann":
        return CANNIssueCleaner(collector)
    elif community == "openubmc":
        return OpenUBMCIssueCleaner(collector)
    else:
        raise ValueError("未知社区")


def get_forum_cleaner(community, collector):
    if community == "cann":
        return CANNForumCleaner(collector)
    elif community == "openubmc":
        return OpenUBMCForumCleaner(collector)
    else:
        raise ValueError("未知社区")


class CANNForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.cann_forum_prompt


class CANNIssueCleaner(BaseCleaner):
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


class OpenUBMCIssueCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.openubmc_issue_prompt
