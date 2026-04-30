import pytest

from app.core.agents import pipeline
from app.core.schemas import ContentRequest


@pytest.mark.asyncio
async def test_pipeline_generates_ideas_without_llm():
    request = ContentRequest(
        brand_name="测试账号",
        brand_positioning="专业内容顾问",
        audience="新手用户",
        platform="抖音",
        goal="提升咨询量",
        keywords=["装修", "避坑"],
        content_count=3,
        use_llm=False,
    )
    result = await pipeline.run(request, persist=False)
    assert len(result.ideas) == 3
    assert result.ideas[0].score > 0
    assert result.ideas[0].titles
    assert result.ideas[0].script
