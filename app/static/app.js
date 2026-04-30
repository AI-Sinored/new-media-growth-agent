const form = document.querySelector('#agent-form');
const submitBtn = document.querySelector('#submit-btn');
const statusEl = document.querySelector('#status');
const summaryEl = document.querySelector('#summary');
const ideasEl = document.querySelector('#ideas');
const exportWrap = document.querySelector('#export-wrap');

function splitList(value) {
  return (value || '')
    .replaceAll('，', ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderIdea(idea) {
  const titles = idea.titles || [];
  const script = idea.script || [];
  const shots = idea.shot_list || [];
  const hashtags = idea.hashtags || [];
  const score = idea.score_breakdown || {};
  return `
    <article class="idea-card">
      <div class="idea-top">
        <div>
          <h3>${escapeHtml(idea.topic)}</h3>
          <p class="meta">${escapeHtml(idea.idea_id)} · 建议发布时间：${escapeHtml(idea.publish_slot || '待定')}</p>
          <div class="badges">
            <span class="badge">受众匹配 ${score.audience_fit ?? '-'}</span>
            <span class="badge">传播潜力 ${score.virality ?? '-'}</span>
            <span class="badge">转化价值 ${score.conversion ?? '-'}</span>
            <span class="badge">差异化 ${score.differentiation ?? '-'}</span>
            <span class="badge">制作难度友好 ${score.production_ease ?? '-'}</span>
          </div>
        </div>
        <div class="score">${escapeHtml(idea.score)}</div>
      </div>

      <div class="details">
        <div class="detail">
          <strong>角度</strong>
          <p>${escapeHtml(idea.angle)}</p>
        </div>
        <div class="detail">
          <strong>用户痛点</strong>
          <p>${escapeHtml(idea.target_user_pain)}</p>
        </div>
        <div class="detail">
          <strong>标题候选</strong>
          <ol>${titles.map((title) => `<li>${escapeHtml(title)}</li>`).join('')}</ol>
        </div>
        <div class="detail">
          <strong>封面文案 / Hook</strong>
          <p>${escapeHtml(idea.cover_copy)}</p>
          <p>${escapeHtml(idea.hook)}</p>
        </div>
        <div class="detail">
          <strong>脚本</strong>
          <ol>${script.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ol>
        </div>
        <div class="detail">
          <strong>镜头建议</strong>
          <ol>${shots.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ol>
        </div>
        <div class="detail">
          <strong>Caption / 标签</strong>
          <p>${escapeHtml(idea.caption)}</p>
          <p>${hashtags.map(escapeHtml).join(' ')}</p>
        </div>
        <div class="detail">
          <strong>CTA / 复盘指标</strong>
          <p>${escapeHtml(idea.cta)}</p>
          <p>${escapeHtml(idea.expected_metric)}</p>
        </div>
      </div>
    </article>
  `;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  statusEl.textContent = 'Agent 正在运行：热点监测、竞品拆解、选题评分、脚本生成...';
  summaryEl.innerHTML = '';
  ideasEl.innerHTML = '';
  exportWrap.innerHTML = '';

  const data = new FormData(form);
  const payload = {
    brand_name: data.get('brand_name'),
    brand_positioning: data.get('brand_positioning'),
    audience: data.get('audience'),
    platform: data.get('platform'),
    goal: data.get('goal'),
    tone: data.get('tone'),
    keywords: splitList(data.get('keywords')),
    competitor_notes: splitList(data.get('competitor_notes')),
    rss_feeds: splitList(data.get('rss_feeds')),
    content_count: Number(data.get('content_count') || 5),
    use_llm: data.get('use_llm') === 'on',
  };

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();
    statusEl.textContent = `生成完成，Run ID：${result.run_id}`;
    summaryEl.innerHTML = `<strong>总结：</strong>${escapeHtml(result.summary)}<br/><br/><strong>下一步：</strong>${(result.next_actions || []).map(escapeHtml).join('；')}`;
    ideasEl.innerHTML = (result.ideas || []).map(renderIdea).join('');
    exportWrap.innerHTML = `<a class="export-link" href="/api/export/${result.run_id}.csv">导出 CSV</a>`;
  } catch (err) {
    statusEl.innerHTML = `<span class="error">运行失败：${escapeHtml(err.message || err)}</span>`;
  } finally {
    submitBtn.disabled = false;
  }
});
