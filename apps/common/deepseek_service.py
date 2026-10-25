"""DeepSeek（OpenAI 兼容接口）封装服务。

设计原则：
- 服务层独立于视图，便于单元测试和扩展（组卷、证书文案等都复用同一 client）。
- 所有对外方法在 API Key 未配置时抛 ApiException，由全局异常处理器转译。
- 同步实现（Django 默认同步），如需高并发可换 AsyncOpenAI。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings

from apps.common.exceptions import ApiException
from apps.common.response import ErrorCode

logger = logging.getLogger("django")


class DeepSeekService:
    """对 DeepSeek OpenAI 兼容接口的薄封装，提供项目内统一的调用入口。"""

    def __init__(self) -> None:
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.model = settings.DEEPSEEK_MODEL
        self.max_tokens = settings.DEEPSEEK_MAX_TOKENS
        self.timeout = settings.DEEPSEEK_TIMEOUT
        self._client: Optional[Any] = None

    # ---------- 懒加载 client ---------- #
    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise ApiException(
                    "未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek。请在 .env 中设置。",
                    code=ErrorCode.CONFLICT,
                    status=503,
                )
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ApiException(
                    "未安装 openai SDK，请执行: pip install openai",
                    code=ErrorCode.SERVER_ERROR,
                    status=500,
                ) from exc

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    # ---------- 基础消息 ---------- #
    def send_message(
        self,
        user_prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """发送单轮消息并返回 DeepSeek 文本响应。"""
        if not user_prompt.strip():
            raise ApiException("prompt 不能为空", code=ErrorCode.INVALID_PARAM, status=400)

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — SDK 可能抛出多种异常
            logger.error("DeepSeek API 调用失败: %s", exc)
            raise ApiException(
                f"DeepSeek API 调用失败: {exc}",
                code=ErrorCode.SERVER_ERROR,
                status=502,
            ) from exc

        content = ""
        choices = getattr(resp, "choices", None) or []
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", "") or ""
        return content.strip()

    # ---------- 业务：主观题评分 ---------- #
    # 评分结果数据结构
    @dataclass
    class GradeResult:
        score: float          # 0 ~ max_score
        feedback: str         # AI 评语
        suggestions: str = "" # 改进建议（可选）

    # 评分 System Prompt 模板（纯函数，方便测试覆盖）
    @staticmethod
    def _grade_system_prompt() -> str:
        return (
            "你是一名艺术素质测评的专业阅卷老师。"
            "请根据题目要求和参考答案，对学生的作答进行评分。\n"
            "评分标准：0 分为完全错误或未作答，满分表示全部符合要求。\n"
            "请客观公正，先分析再给分。\n"
            "你的回答必须是严格的 JSON，格式如下，不要输出任何其它文字：\n"
            '{"score": 数字, "feedback": "简短评语", "suggestions": "改进建议（可选）"}'
        )

    def grade_answer(
        self,
        *,
        question_content: str,
        reference_answer: str,
        student_answer: str,
        max_score: float = 10.0,
    ) -> GradeResult:
        """调用 DeepSeek 对一道主观题进行 AI 评分。

        :param question_content: 题干
        :param reference_answer: 参考答案
        :param student_answer:  学生作答
        :param max_score:       该题满分
        """
        prompt = (
            f"【题目】\n{question_content}\n\n"
            f"【参考答案】\n{reference_answer or '（无）'}\n\n"
            f"【学生作答】\n{student_answer or '（未作答）'}\n\n"
            f"【满分】{max_score}\n"
            "请按要求评分，返回 JSON。"
        )

        raw = self.send_message(
            prompt,
            system_prompt=self._grade_system_prompt(),
            temperature=0.3,  # 评分要客观，降低随机性（deepseek-reasoner 不支持 temperature，评分请用 deepseek-chat）
            max_tokens=512,
        )

        # 解析 JSON 结果
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("DeepSeek 返回非 JSON，原始响应: %s", raw)
            raise ApiException(
                "AI 返回格式异常，无法解析评分结果",
                code=ErrorCode.SERVER_ERROR,
                status=502,
            ) from exc

        try:
            score = float(data.get("score", 0))
            # 限制在 [0, max_score]
            score = max(0.0, min(max_score, score))
        except (TypeError, ValueError):
            score = 0.0

        feedback = str(data.get("feedback", "")).strip()
        suggestions = str(data.get("suggestions", "")).strip()

        return self.GradeResult(score=score, feedback=feedback, suggestions=suggestions)


# 单例：全局共享一个 client
_deepseek_service: Optional[DeepSeekService] = None


def get_deepseek_service() -> DeepSeekService:
    global _deepseek_service
    if _deepseek_service is None:
        _deepseek_service = DeepSeekService()
    return _deepseek_service
