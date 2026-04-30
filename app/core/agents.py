from __future__ import annotations

import asyncio
import hashlib
import random
from datetime import datetime, timedelta
from typing import Iterable

from app.core.database import db
from app.core.llm import LLMClient
from app.core.schemas import (
    AgentRunResult,
    CompetitorInsight,
    ContentIdea,
    ContentRequest,
    ScoreBreakdown,
    TrendSignal,
)
from app.core.seed import DEFAULT_TREND_PATTERNS, HOOK_TEMPLATES, PLATFORM_PLAYBOOKS, SCRIPT_FRAMEWORKS


class TrendAgent:
    """Collects topic signals from keywords, RSS feeds and seed patterns."""

    async def run(self, request: ContentRequest) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        signals.extend(self._from_keywords(request.keywords))
        rss_signals = await self._from_rss(request.rss_feeds, request.keywords)
        signals.extend(rss_signals)
        signals.extend(self._from_seed(request))
        return self._dedupe(signals)[: max(request.content_count * 3, 10)]

    def _from_keywords(self, keywords: Iterable[str]) -> list[TrendSignal]:
        output: list[TrendSignal] = []
        for keyword in keywords:
            output.append(
                TrendSignal(
                    title=f"{keyword}到底怎么选？普通人最容易忽略的 3 个判断标准",
                    source="keyword",
                    keywords=[keyword, "选择", "避坑"],
                    reason="关键词直接来自业务输入，和目标用户需求相关。",
                    estimated_heat=74,
                )
            )
            output.append(
                TrendSignal(
                    title=f"关于{keyword}，很多人花钱后才明白的真相",
                    source="keyword",
                    keywords=[keyword, "真相", "省钱"],
                    reason="真相/信息差类表达更容易产生点击和评论。",
                    estimated_heat=78,
                )
            )
        return output

    async def _from_rss(self, feeds: list[str], keywords: list[str]) -> list[TrendSignal]:
        if not feeds:
            return []

        try:
            import feedparser
            import httpx
        except Exception:
            return []

        async def fetch(url: str) -> str:
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
            except Exception:
                return ""

        docs = await asyncio.gather(*(fetch(url) for url in feeds[:5]))
        signals: list[TrendSignal] = []
        for url, text in zip(feeds, docs):
            if not text:
                continue
            parsed = feedparser.parse(text)
            for entry in parsed.entries[:8]:
                title = getattr(entry, "title", "").strip()
                if not title:
                    continue
                matched = [kw for kw in keywords if kw and kw.lower() in title.lower()]
                heat = 70 + min(len(matched) * 5, 20)
                signals.append(
                    TrendSignal(
                        title=title,
                        source=url,
                        keywords=matched or keywords[:2],
                        reason="来自用户配置的 RSS 源，可作为外部趋势信号。",
                        estimated_heat=heat,
                    )
                )
        return signals

    def _from_seed(self, request: ContentRequest) -> list[TrendSignal]:
        keyword = request.keywords[0] if request.keywords else "这个问题"
        signals = []
        for item in DEFAULT_TREND_PATTERNS:
            title = item["title"].replace("这件事", keyword).replace("表面参数", f"{keyword}的表面信息")
            signals.append(
                TrendSignal(
                    title=title,
                    source="seed_pattern",
                    keywords=list(dict.fromkeys(item.get("keywords", []) + request.keywords[:2])),
                    reason=item["reason"],
                    estimated_heat=item["estimated_heat"],
                )
            )
        return signals

    def _dedupe(self, signals: list[TrendSignal]) -> list[TrendSignal]:
        seen: set[str] = set()
        unique: list[TrendSignal] = []
        for signal in sorted(signals, key=lambda s: s.estimated_heat, reverse=True):
            key = signal.title.lower().replace(" ", "")[:40]
            if key in seen:
                continue
            seen.add(key)
            unique.append(signal)
        return unique


class CompetitorAgent:
    """Extracts useful patterns from competitor notes or customer observations."""

    def run(self, request: ContentRequest) -> CompetitorInsight:
        notes = "；".join(request.competitor_notes)
        keywords = request.keywords or ["产品", "服务", "选择"]
        hooks = [
            f"很多人选{keywords[0]}，第一步就错了",
            f"同样预算，为什么结果差这么多",
            f"内行人看这 3 点，外行人才只看价格",
        ]
        pain_points = [
            "怕花冤枉钱",
            "信息太多不知道信谁",
            "担心售后/结果不达预期",
            "想要一个可以直接照做的判断清单",
        ]
        formats = PLATFORM_PLAYBOOKS.get(request.platform, PLATFORM_PLAYBOOKS["通用"])["best_formats"]
        opportunity_gaps = [
            "把专业信息翻译成普通人能听懂的话",
            "用真实对比降低用户决策成本",
            "把泛泛而谈改成具体人群、具体场景、具体预算",
        ]
        if notes:
            if "价格" in notes or "预算" in notes:
                pain_points.insert(0, "价格不透明，用户怕被套路")
            if "售后" in notes or "服务" in notes:
                pain_points.insert(0, "用户购买前最担心后续服务")
            if "对比" in notes or "横评" in notes:
                formats.insert(0, "真实横向对比")
        return CompetitorInsight(
            hooks=list(dict.fromkeys(hooks))[:5],
            pain_points=list(dict.fromkeys(pain_points))[:6],
            formats=list(dict.fromkeys(formats))[:6],
            opportunity_gaps=list(dict.fromkeys(opportunity_gaps))[:5],
        )


class ScoringAgent:
    """Scores candidate topics with a transparent weighted rubric."""

    def run(self, request: ContentRequest, signals: list[TrendSignal], insight: CompetitorInsight) -> list[tuple[TrendSignal, ScoreBreakdown, str]]:
        scored: list[tuple[TrendSignal, ScoreBreakdown, str]] = []
        audience_terms = set(_tokenize(request.audience + " " + request.goal))
        for signal in signals:
            topic_terms = set(_tokenize(signal.title + " " + " ".join(signal.keywords)))
            keyword_hit = len([kw for kw in request.keywords if kw and kw in signal.title])
            audience_overlap = len(audience_terms.intersection(topic_terms))
            audience_fit = min(100, 55 + keyword_hit * 12 + audience_overlap * 4)
            virality = min(100, signal.estimated_heat + _conflict_bonus(signal.title))
            conversion = min(100, 52 + keyword_hit * 10 + _conversion_bonus(signal.title, request.goal))
            differentiation = min(100, 58 + len(insight.opportunity_gaps) * 4 + _differentiation_bonus(signal.title))
            production_ease = max(45, 88 - _production_penalty(signal.title))
            breakdown = ScoreBreakdown(
                audience_fit=audience_fit,
                virality=virality,
                conversion=conversion,
                differentiation=differentiation,
                production_ease=production_ease,
            )
            reason = (
                f"该选题热度 {signal.estimated_heat}，关键词命中 {keyword_hit} 个；"
                f"兼具痛点表达和决策场景，适合用于{request.goal}。"
            )
            scored.append((signal, breakdown, reason))
        scored.sort(key=lambda item: item[1].total, reverse=True)
        return scored


class ScriptAgent:
    """Turns scored topics into publish-ready content ideas."""

    def __init__(self) -> None:
        self.llm = LLMClient()

    async def run(
        self,
        request: ContentRequest,
        scored: list[tuple[TrendSignal, ScoreBreakdown, str]],
        insight: CompetitorInsight,
    ) -> list[ContentIdea]:
        ideas: list[ContentIdea] = []
        for idx, (signal, breakdown, reason) in enumerate(scored[: request.content_count], start=1):
            idea = self._rule_based_idea(idx, request, signal, breakdown, reason, insight)
            if request.use_llm:
                idea = await self._llm_enhance(idea, request, insight)
            ideas.append(idea)
        return ideas

    def _rule_based_idea(
        self,
        idx: int,
        request: ContentRequest,
        signal: TrendSignal,
        breakdown: ScoreBreakdown,
        reason: str,
        insight: CompetitorInsight,
    ) -> ContentIdea:
        keyword = signal.keywords[0] if signal.keywords else (request.keywords[0] if request.keywords else "选择")
        framework = SCRIPT_FRAMEWORKS[(idx - 1) % len(SCRIPT_FRAMEWORKS)]
        hook_template = HOOK_TEMPLATES[(idx - 1) % len(HOOK_TEMPLATES)]
        hook = hook_template.format(audience=request.audience, keyword=keyword)
        angle = self._angle_from_signal(signal.title, request, insight)
        pain = insight.pain_points[(idx - 1) % len(insight.pain_points)] if insight.pain_points else "用户不知道如何判断"
        titles = self._titles(signal.title, request, keyword)
        script = self._script_steps(framework, hook, keyword, request, pain)
        shot_list = self._shots(request.platform, framework)
        hashtags = self._hashtags(request, keyword)
        expected_metric = PLATFORM_PLAYBOOKS.get(request.platform, PLATFORM_PLAYBOOKS["通用"])["metric"]
        stable_hash = hashlib.md5(f"{signal.title}-{idx}".encode("utf-8")).hexdigest()[:6]
        return ContentIdea(
            idea_id=f"idea_{idx:03d}_{stable_hash}",
            topic=signal.title,
            angle=angle,
            target_user_pain=pain,
            score=breakdown.total,
            score_breakdown=breakdown,
            score_reason=reason,
            titles=titles,
            cover_copy=self._cover_copy(keyword, pain),
            hook=hook,
            script=script,
            shot_list=shot_list,
            caption=self._caption(request, keyword, pain),
            hashtags=hashtags,
            cta=self._cta(request),
            production_notes="建议 35-60 秒；开头 3 秒必须先抛结论，再给判断标准；尽量加入真实案例、价格/方案对比或用户提问截图。",
            expected_metric=expected_metric,
        )

    async def _llm_enhance(self, idea: ContentIdea, request: ContentRequest, insight: CompetitorInsight) -> ContentIdea:
        system_prompt = (
            "你是资深内容增长策略 Agent。请基于输入优化中文短视频选题，输出 JSON。"
            "必须保留事实稳健，不编造具体数据，不承诺绝对效果。"
            "JSON 字段：titles(list[str]), cover_copy(str), hook(str), script(list[str]), caption(str), hashtags(list[str]), cta(str)。"
        )
        payload = {
            "request": request.model_dump(mode="json"),
            "competitor_insight": insight.model_dump(mode="json"),
            "idea": idea.model_dump(mode="json"),
        }
        data = await self.llm.json_completion(system_prompt, payload)
        if not data:
            return idea
        try:
            update = idea.model_dump()
            for field in ["titles", "cover_copy", "hook", "script", "caption", "hashtags", "cta"]:
                if field in data and data[field]:
                    update[field] = data[field]
            return ContentIdea.model_validate(update)
        except Exception:
            return idea

    def _angle_from_signal(self, title: str, request: ContentRequest, insight: CompetitorInsight) -> str:
        if "成本" in title or "真相" in title:
            return "信息差拆解：把行业默认不透明的地方讲清楚。"
        if "别急" in title or "判断标准" in title:
            return "购买/行动前教育：先建立正确判断标准，再引导咨询。"
        if "清单" in title or "新手" in title:
            return "收藏型清单：降低新手决策门槛。"
        return insight.opportunity_gaps[0] if insight.opportunity_gaps else request.brand_positioning or "专业判断逻辑"

    def _titles(self, topic: str, request: ContentRequest, keyword: str) -> list[str]:
        platform_style = PLATFORM_PLAYBOOKS.get(request.platform, PLATFORM_PLAYBOOKS["通用"])["title_style"]
        return [
            topic,
            f"{request.audience}看完再决定：{keyword}别只看表面",
            f"内行人选{keyword}，真正先看的是这 3 点",
            f"{keyword}避坑指南：这类钱真的没必要花",
            f"一条视频讲清楚：{keyword}怎么选才不后悔",
        ][:5] + [f"标题风格建议：{platform_style}"]

    def _cover_copy(self, keyword: str, pain: str) -> str:
        variants = [
            f"{keyword}别乱选",
            f"这 3 点比价格更重要",
            f"别等踩坑才知道",
            f"{pain[:12]}？先看这里",
        ]
        return " / ".join(variants[:2])

    def _script_steps(self, framework: list[str], hook: str, keyword: str, request: ContentRequest, pain: str) -> list[str]:
        return [
            f"{framework[0]}：{hook}",
            f"{framework[1]}：很多人一上来就问价格/参数，但真正的问题是：{pain}。",
            f"{framework[2]}：第一看是否匹配自己的使用场景；第二看长期成本；第三看后续服务或执行难度。",
            f"{framework[3]}：举一个对比案例：同样关注{keyword}，只看低价的人后期容易补成本，按场景选的人总成本更低。",
            f"{framework[4]}：把你的预算/需求打在评论区，我按你的情况给你一个判断方向。",
        ]

    def _shots(self, platform: str, framework: list[str]) -> list[str]:
        if platform in {"抖音", "快手"}:
            return [
                "0-3秒：真人正面口播，字幕打出反常识结论",
                "3-15秒：展示错误选择的典型场景",
                "15-40秒：用白板/实物/屏幕录制拆 3 个标准",
                "40-55秒：给出真实案例对比",
                "55-60秒：评论区引导或私信 CTA",
            ]
        if platform == "小红书":
            return [
                "封面：大字标题 + 具体人群",
                "第1屏：先给结论",
                "第2-4屏：清单化拆解判断标准",
                "第5屏：避坑提醒",
                "第6屏：评论区提问引导",
            ]
        return [f"镜头/段落 {i + 1}：{step}" for i, step in enumerate(framework)]

    def _caption(self, request: ContentRequest, keyword: str, pain: str) -> str:
        return (
            f"这条内容给{request.audience}。做{keyword}相关决策时，别只看表面信息，"
            f"先确认自己的场景、预算和后续成本。你最担心的是不是：{pain}？"
        )

    def _hashtags(self, request: ContentRequest, keyword: str) -> list[str]:
        base = [f"#{keyword}", "#避坑指南", "#干货分享", "#新手必看"]
        if request.platform == "抖音":
            base.extend(["#同城", "#经验分享"])
        elif request.platform == "小红书":
            base.extend(["#收藏", "#生活经验"])
        return list(dict.fromkeys(base))[:8]

    def _cta(self, request: ContentRequest) -> str:
        if "咨询" in request.goal or "线索" in request.goal or "转化" in request.goal:
            return "评论区留下你的预算/需求，我帮你判断更适合哪种方案。"
        if "曝光" in request.goal or "涨粉" in request.goal:
            return "关注我，后面继续用普通人能听懂的话拆解行业真相。"
        return "把你的具体情况发出来，我按你的场景给你一个参考方向。"


class CalendarAgent:
    def run(self, request: ContentRequest, ideas: list[ContentIdea]) -> list[ContentIdea]:
        playbook = PLATFORM_PLAYBOOKS.get(request.platform, PLATFORM_PLAYBOOKS["通用"])
        slots = playbook["publish_slots"]
        start = datetime.utcnow() + timedelta(days=1)
        for idx, idea in enumerate(ideas):
            day = start + timedelta(days=idx)
            slot = slots[idx % len(slots)]
            idea.publish_slot = f"{day.strftime('%Y-%m-%d')} {slot}"
        return ideas


class LearningAgent:
    def run(self, request: ContentRequest) -> tuple[str, list[str]]:
        feedback = db.get_feedback_for_brand(request.brand_name, limit=30)
        if not feedback:
            return (
                "当前暂无历史反馈数据，本次将采用通用内容增长评分模型。",
                [
                    "先连续发布 7-14 天，收集每条内容的播放、完播、互动、私信/线索数据。",
                    "每周筛选前 20% 内容，提炼钩子、选题、人群和 CTA 共性。",
                    "把低分内容按开头、脚本结构、选题相关性分别复盘，不要只看播放量。",
                ],
            )
        avg_engagement = sum(row["engagement_rate"] for row in feedback) / len(feedback)
        avg_conversion = sum(row["conversion_rate"] for row in feedback) / len(feedback)
        best = max(feedback, key=lambda row: (row["conversion_rate"], row["engagement_rate"]))
        summary = (
            f"已读取 {len(feedback)} 条历史反馈；平均互动率约 {avg_engagement:.2%}，"
            f"平均线索转化率约 {avg_conversion:.2%}。表现较好的样本是 {best['idea_id']}。"
        )
        actions = [
            "优先复用高互动内容的前 3 秒钩子结构。",
            "把有线索转化的内容拆成系列，不要只做单条爆点。",
            "对低互动但高转化内容增加封面和标题测试。",
        ]
        return summary, actions


class ContentGrowthPipeline:
    def __init__(self) -> None:
        self.trend_agent = TrendAgent()
        self.competitor_agent = CompetitorAgent()
        self.scoring_agent = ScoringAgent()
        self.script_agent = ScriptAgent()
        self.calendar_agent = CalendarAgent()
        self.learning_agent = LearningAgent()

    async def run(self, request: ContentRequest, persist: bool = True) -> AgentRunResult:
        trend_signals = await self.trend_agent.run(request)
        competitor_insight = self.competitor_agent.run(request)
        scored = self.scoring_agent.run(request, trend_signals, competitor_insight)
        ideas = await self.script_agent.run(request, scored, competitor_insight)
        ideas = self.calendar_agent.run(request, ideas)
        learning_summary, next_actions = self.learning_agent.run(request)
        result = AgentRunResult(
            request=request,
            trend_signals=trend_signals[:12],
            competitor_insight=competitor_insight,
            ideas=ideas,
            summary=(
                f"本次为 {request.brand_name} 在 {request.platform} 生成 {len(ideas)} 条内容方案。"
                f"核心目标是：{request.goal}。{learning_summary}"
            ),
            next_actions=next_actions,
            token_plan_note=(
                "MVP 当前支持无 Key 规则模式和 OpenAI 增强模式。若申请更高 token / plan 额度，"
                "建议用于：更多趋势源抓取、更大规模竞品样本分析、脚本多版本 A/B 生成、发布后自动复盘。"
            ),
        )
        if persist:
            result = db.save_run(result)
        return result


def _tokenize(text: str) -> list[str]:
    separators = ["，", "。", "、", " ", ",", ".", "?", "？", "!", "！", "：", ":", "；", ";"]
    for sep in separators:
        text = text.replace(sep, " ")
    return [part.strip().lower() for part in text.split() if len(part.strip()) >= 2]


def _conflict_bonus(title: str) -> int:
    words = ["别", "坑", "真相", "后悔", "低价", "最怕", "不会告诉", "错"]
    return min(15, sum(3 for word in words if word in title))


def _conversion_bonus(title: str, goal: str) -> int:
    bonus = 0
    if any(word in title for word in ["判断", "选择", "下单", "预算", "清单"]):
        bonus += 12
    if any(word in goal for word in ["咨询", "转化", "线索", "成交"]):
        bonus += 8
    return bonus


def _differentiation_bonus(title: str) -> int:
    if any(word in title for word in ["成本", "逻辑", "讲成人话", "业内"]):
        return 12
    return 5


def _production_penalty(title: str) -> int:
    if any(word in title for word in ["横评", "测评", "全流程"]):
        return 25
    if any(word in title for word in ["成本", "案例"]):
        return 15
    return 5


pipeline = ContentGrowthPipeline()
