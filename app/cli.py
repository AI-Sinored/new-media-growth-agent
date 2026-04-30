from __future__ import annotations

import argparse
import asyncio
import json

from app.core.agents import pipeline
from app.core.schemas import ContentRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Content Growth Agent from CLI")
    parser.add_argument("--brand", required=True, help="品牌/账号名称")
    parser.add_argument("--positioning", default="", help="品牌定位")
    parser.add_argument("--audience", required=True, help="目标用户")
    parser.add_argument("--platform", default="抖音", help="平台：抖音/小红书/B站/视频号/快手/通用")
    parser.add_argument("--goal", default="提升曝光和转化", help="内容目标")
    parser.add_argument("--tone", default="真实、直接、有记忆点", help="内容语气")
    parser.add_argument("--keywords", default="", help="逗号分隔关键词")
    parser.add_argument("--competitor-notes", default="", help="逗号分隔竞品观察")
    parser.add_argument("--rss", default="", help="逗号分隔 RSS URL")
    parser.add_argument("--count", type=int, default=5, help="生成数量")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM 增强")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    request = ContentRequest(
        brand_name=args.brand,
        brand_positioning=args.positioning,
        audience=args.audience,
        platform=args.platform,
        goal=args.goal,
        tone=args.tone,
        keywords=args.keywords,
        competitor_notes=args.competitor_notes,
        rss_feeds=args.rss,
        content_count=args.count,
        use_llm=not args.no_llm,
    )
    result = await pipeline.run(request, persist=True)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
