from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class Platform(str, Enum):
    douyin = "抖音"
    xiaohongshu = "小红书"
    bilibili = "B站"
    video_account = "视频号"
    kuaishou = "快手"
    general = "通用"


class ContentRequest(BaseModel):
    brand_name: str = Field(..., min_length=1, description="品牌/账号/项目名称")
    brand_positioning: str = Field(default="", description="品牌定位")
    audience: str = Field(..., min_length=1, description="目标用户")
    platform: str = Field(default="抖音", description="发布平台")
    goal: str = Field(default="提升曝光和转化", description="内容目标")
    tone: str = Field(default="真实、直接、有记忆点", description="内容语气")
    keywords: list[str] = Field(default_factory=list, description="核心关键词")
    competitor_notes: list[str] = Field(default_factory=list, description="竞品观察/爆款样本/客户反馈")
    rss_feeds: list[str] = Field(default_factory=list, description="可选 RSS 源")
    content_count: int = Field(default=5, ge=1, le=20, description="生成内容数量")
    use_llm: bool = Field(default=True, description="是否尝试使用 LLM 增强")

    @field_validator("keywords", "competitor_notes", "rss_feeds", mode="before")
    @classmethod
    def split_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = value.replace("，", ",").split(",")
            return [p.strip() for p in parts if p.strip()]
        return value


class TrendSignal(BaseModel):
    title: str
    source: str = "seed"
    keywords: list[str] = Field(default_factory=list)
    reason: str = ""
    estimated_heat: int = Field(default=60, ge=0, le=100)


class CompetitorInsight(BaseModel):
    hooks: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    opportunity_gaps: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    audience_fit: int = Field(ge=0, le=100)
    virality: int = Field(ge=0, le=100)
    conversion: int = Field(ge=0, le=100)
    differentiation: int = Field(ge=0, le=100)
    production_ease: int = Field(ge=0, le=100)

    @property
    def total(self) -> int:
        weighted = (
            self.audience_fit * 0.25
            + self.virality * 0.25
            + self.conversion * 0.2
            + self.differentiation * 0.15
            + self.production_ease * 0.15
        )
        return round(weighted)


class ContentIdea(BaseModel):
    idea_id: str
    topic: str
    angle: str
    target_user_pain: str
    score: int
    score_breakdown: ScoreBreakdown
    score_reason: str
    titles: list[str]
    cover_copy: str
    hook: str
    script: list[str]
    shot_list: list[str]
    caption: str
    hashtags: list[str]
    cta: str
    production_notes: str
    expected_metric: str
    publish_slot: str | None = None


class AgentRunResult(BaseModel):
    run_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request: ContentRequest
    trend_signals: list[TrendSignal]
    competitor_insight: CompetitorInsight
    ideas: list[ContentIdea]
    summary: str
    next_actions: list[str]
    token_plan_note: str


class FeedbackRequest(BaseModel):
    run_id: int
    idea_id: str
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    notes: str = ""


class FeedbackRecord(FeedbackRequest):
    id: int
    created_at: datetime
    engagement_rate: float
    conversion_rate: float
