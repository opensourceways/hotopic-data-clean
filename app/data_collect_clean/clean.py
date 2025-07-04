import re
import logging
from abc import ABC, abstractmethod
from retrying import retry
from openai import OpenAI
from datetime import datetime
from config.settings import settings
from tqdm import tqdm
from app.db import base

logger = logging.getLogger(__name__)


class Record:
    def __init__(self, base_data, processed):
        self.base_data = base_data
        self.processed = processed


class FormattedRecord:
    def __init__(
        self,
        title,
        body,
        url,
        created_at,
        updated_at,
        topic_closed,
        history,
        clean_data,
        topic_summary,
        source_type,
        source_id,
        source_closed,
    ):
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
            api_key=settings.llm_api_key, base_url=settings.llm_api_url
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
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            raise

    def _basic_clean(self, text):
        text = re.sub(r"<.*?>", "", text)
        return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、]", " ", text).strip()

    def process(self, start_date):
        data_before_clean = self.collector.collect(start_date)
        for raw_data in tqdm(data_before_clean, desc="Processing data"):
            try:
                record = self._build_record(raw_data)
                yield record
            except Exception as e:
                logger.error(f"处理失败: {raw_data.get('id', '未知ID')} - {str(e)}")

    def _is_exist(self, source_id: str) -> bool:
        with base.SessionLocal() as session:
            existing_record = (
                session.query(base.Discussion)
                .filter(base.Discussion.source_id == source_id)
                .first()
            )
            if not existing_record:
                return False
            if not existing_record.clean_data:
                return False
            return True

    @abstractmethod
    def _is_valid(self, title, body):
        return True

    def _build_record(self, raw_data):
        if not all(k in raw_data for k in ("id", "title", "body")):
            raise ValueError("缺失必要字段")
        if not self._is_valid(raw_data["title"], raw_data["body"]):
            raise ValueError(f"本数据无效{raw_data['id']} - {raw_data['title']}")
        created_at = raw_data.get("created_at", datetime.now())
        if isinstance(created_at, datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
        updated_at = raw_data.get("updated_at", None)
        if isinstance(updated_at, datetime):
            updated_at = updated_at.strftime("%Y-%m-%d %H:%M:%S")
        if not self._is_exist(str(raw_data["id"])):
            llm_content = self._llm_process(
                f"标题：{raw_data['title']}\n内容：{raw_data['body']}"
            )
        else:
            llm_content = ""
        return FormattedRecord(
            title=raw_data["title"],
            body=raw_data["body"],
            url=raw_data.get("url", ""),
            created_at=created_at,
            updated_at=updated_at,
            topic_closed=raw_data.get("closed", False),
            history=raw_data.get("history", "[]"),
            clean_data=self._basic_clean(llm_content),
            topic_summary="",
            source_type=self.source_type,
            source_id=raw_data["id"],
            source_closed=raw_data.get("state", "") == "closed",
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
    elif community == "opengauss":
        return OpenGaussIssueCleaner(collector)
    elif community == "mindspore":
        return MindSporeIssueCleaner(collector)
    elif community == "openeuler":
        return OpenEulerIssueCleaner(collector)
    else:
        raise ValueError("未知社区")


def get_mail_cleaner(community, collector):
    if community == "opengauss":
        return OpenGaussMailCleaner(collector)
    elif community == "openeuler":
        return OpenEulerMailCleaner(collector)
    else:
        raise ValueError("未知社区")


def get_forum_cleaner(community, collector):
    if community == "cann":
        return CANNForumCleaner(collector)
    elif community == "openubmc":
        return OpenUBMCForumCleaner(collector)
    elif community == "mindspore":
        return MindSporeForumCleaner(collector)
    elif community == "openeuler":
        return OpenEulerForumCleaner(collector)
    else:
        raise ValueError("未知社区")


class CANNForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.cann_forum_prompt

    def _is_valid(self, title, body):
        if re.search(r"从入门到精通|学习|指导|笔记|分享|训练营", title):
            return False
        return True


class CANNIssueCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.cann_issue_prompt

    def _is_valid(self, title, body):
        return True


class OpenUBMCForumCleaner(BaseCleaner):
    def _is_valid(self, title, body):
        return True

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

    def _is_valid(self, title, body):
        return True


class OpenGaussIssueCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.opengauss_issue_prompt

    def _is_valid(self, title, body):
        if re.search(r"用户数据迁移授权协议|个人信息迁移同意书|normally open", title):
            return False
        return True


class OpenGaussMailCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "mail"

    def _get_system_prompt(self):
        return settings.opengauss_mail_prompt

    def _is_valid(self, title, body):
        if re.search(
            r"例会|公示|公告|纪要|非问题|公式关闭|升级通知|会议|转测试", title
        ):
            return False
        if re.search(r"邀请您参加|会议主题", body):
            return False
        return True


class OpenEulerMailCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "mail"

    def _get_system_prompt(self):
        return settings.openeuler_mail_prompt

    def _is_valid(self, title, body):
        if re.search(
            r"例会|公示|公告|纪要|非问题|公式关闭|升级|会议|转测试|订阅|年报|月报|需求持续收集中|[PATCH]|进度报告|议题申报|提醒|告警|申请|说明|指南|议程|OLK|感谢信",
            title,
        ):
            return False
        if re.search(r"邀请您参加|会议主题", body):
            return False
        return True


class MindSporeForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.mindspore_forum_prompt

    def _is_valid(self, title, body):
        if re.search(r"指南|干货小卖部|开发者说|课程|体验|0day同步！|扩散模型", title):
            return False
        return True


class OpenEulerForumCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "forum"

    def _get_system_prompt(self):
        return settings.openeuler_forum_prompt

    def _is_valid(self, title, body):
        if re.search(
            r"练习|综合实践|test|指南|攻略|探究|问题收集|公告|用户体验提升|分享|基于anaconda的搭建|网赌|【openEuler系列】|贡献报告|加油|新世界",
            title,
        ):
            return False
        if re.search(r"实验介绍|已被社区举报", body):
            return False
        return True


class MindSporeIssueCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.mindspore_issue_prompt

    def _is_valid(self, title, body):
        if re.search(r"开源实习|测试任务|任务", title):
            return False
        return True


class OpenEulerIssueCleaner(BaseCleaner):
    @property
    def source_type(self):
        return "issue"

    def _get_system_prompt(self):
        return settings.openeuler_issue_prompt

    def _is_valid(self, title, body):
        pattern = (
            r"需求征集|English translation|补丁|CVE-|【EulerMaker】|【OEPKG】|【openEuler 25.03】|技术测评|"
            "软件包贡献|【Easysoftware】|公告|技术交流|【22.03-SP4】|OLK|调研|特性|申请|【EUR】|test|【EasySoftware】|"
            "汇总|文档和脚本整理|请忽略|建议升级|探索|开发路线图|迁移至|数据集生成工具|实习|模板|构建流程优化|问题清单"
        )
        if re.search(pattern, title):
            return False
        if re.search(r"openEuler-AutoRepair|特性描述|开源之夏", body):
            return False
        return True
