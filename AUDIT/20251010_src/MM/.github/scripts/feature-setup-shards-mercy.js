// Feature generator (full): creates/updates Epic + rich child issues,
// links them, and adds everything to your Project board (idempotent).

const { owner, repo } = context.repo;

// ---- Project selection (edit if your board name/login differ) ----
const PROJECT_OWNER = 'cailleanC1C';
const PROJECT_TITLE = 'C1C Cross-Bot Hotlist';
// ------------------------------------------------------------------

// ---- Feature definition (Shards & Mercy v1) ----
const feature = {
  title: 'Achievements - Shards & Mercy (v1)',
  bot: 'bot:achievements',
  comp: 'comp:shards',
  useCases: [
    'Player posts screenshot -> bot reads five shard counts -> user confirms -> snapshot saved',
    'Track mercy per user per shard type; reset correctly on Legendary (incl. Guaranteed/Extra rules)',
    'Users/staff can set initial mercy or reset manually; never block UX if OCR fails',
    'Keep exactly one pinned summary per clan; update within ISO week; new message on week rollover',
    'All actions live in clan shard threads; permissions tied to clan roles'
  ],
  epicBodyIntro: [
    '### Summary',
    "Add a clan-aware Shards & Mercy module to Achievements: users drop a shard-count screenshot in their clan's shard thread; the bot OCRs counts (with manual fallback), stores inventory and events in Sheets, tracks mercy per shard type, and keeps a pinned weekly summary message per clan.",
    '',
    '### Problem / goal',
    'Leads/recruiters lack a reliable, up-to-date shard inventory and pity ledger; screenshots are scattered and mercy math is error-prone.',
    '',
    '### Core use cases (v1)'
  ],
  epicBodyMiddle: [
    '',
    '### High-level design (agreed)',
    '- Module: bot:achievements / comp:shards',
    '- Data: snapshots (inventory) + events (pull ledger)',
    '- Commands/UI: modal/commands; weekly summary rules',
    '- Guards/ops: thread-only, role gating, retries/backoff',
    '',
    '### Implementation plan (v1 steps)'
  ],
  epicBodyEnd: [
    '',
    '### Acceptance criteria (testable)',
    '- [ ] Image in shard thread -> Scan Image modal -> Confirm writes snapshot with message link & timestamp',
    '- [ ] Manual path works when OCR fails; UX never blocks',
    '- [ ] mercy addpulls records batch with shard type/qty/flags; Legendary/Guaranteed/Extra reset correctly',
    '- [ ] Staff can set initial pity or reset; changes persist',
    '- [ ] Exactly one pinned "This Week" summary per clan; in-week updates edit; week rollover creates new',
    '',
    '### Rollout',
    'Dry-run in 1–2 clans; keep manual entry available; simple rollback: disable watcher, leave commands.'
  ],
  subs: [
    { key: 'Guards & config', comp: 'comp:shards', body: [
      '### Scope',
      'Map role_id <-> clan_tag, thread-only gates, staff override toggles.',
      '',
      '### Tasks',
      '- Config: clan_tag, thread_id, emoji ids, page_size, enable_ocr, enable_pinned_summary.',
      '- Reject outside shard threads with a clear message (trace logged).',
      '- Unit tests for gating paths.',
      '',
      '### Acceptance',
      '- Only configured shard threads allow actions.',
      '- Clan role required unless staff override.'
    ]},
    { key: 'Sheets adapters', comp: 'comp:shards', body: [
      '### Scope',
      'Helpers for SNAPSHOTS (inventory) and EVENTS (pull ledger); idempotent appends.',
      '',
      '### Tasks',
      '- SNAPSHOTS: user, display, clan_tag, five counts, origin (ocr|manual), message_link, ts_utc.',
      '- EVENTS: batch_id, batch_size, batch_index, shard_type, qty, flags (guaranteed, extra, resets_pity), message_link, ts_utc.',
      '- Idempotency: (message_link+user+clan) for snapshots; (batch_id+index) for events.',
      '',
      '### Acceptance',
      '- Re-submits do not duplicate rows.',
      '- Schema documented inline.'
    ]},
    { key: 'Watcher (OCR/manual)', comp: 'comp:ocr', body: [
      '### Scope',
      'Detect images; OCR preview; manual fallback; never block.',
      '',
      '### Tasks',
      '- Ephemeral action on image in shard thread.',
      '- Buttons: Confirm / Manual / Retry / Close; cache OCR per image.',
      '- On Confirm/Manual: write SNAPSHOTS via adapters; attach debug crops on failure (staff-only).',
      '',
      '### Acceptance',
      '- Modal appears only in shard threads.',
      '- Manual path works; snapshot includes message link & timestamp.'
    ]},
    { key: 'Commands & UI', comp: 'comp:shards', body: [
      '### Scope',
      'Slash/bang commands & modals for set/adjust/reset/show.',
      '',
      '### Tasks',
      '- `!shards set` -> modal (5 counts) -> confirm -> snapshot',
      '- `!mercy addpulls` -> shard, pulls, flags (Legendary/Guaranteed/Extra)',
      '- `!mercy reset` per shard; `!mercy show` compact summary',
      '',
      '### Acceptance',
      '- Validations: non-negative integers; friendly errors.'
    ]},
    { key: 'Mercy engine & ledger', comp: 'comp:shards', body: [
      '### Scope',
      'Track pity by shard type; apply/reset rules; write EVENTS.',
      '',
      '### Tasks',
      '- Maintain pity for Mystery/Ancient/Void/Primal/Sacred.',
      '- Resets on Legendary; handle Guaranteed/Extra cases.',
      '- Record batches (size, index, flags).',
      '',
      '### Acceptance',
      '- Unit tests cover Legendary/Guaranteed/Extra logic.'
    ]},
    { key: 'Summary renderer (weekly pinned)', comp: 'comp:shards', body: [
      '### Scope',
      'One pinned summary per clan; update in-week; new message on rollover.',
      '',
      '### Tasks',
      '- Header + "updated X ago"; totals for 5 shard types.',
      '- Paged member cards (10/page), stable sort (name then ID).',
      '- Prev / Next / Refresh buttons; ISO-week check.',
      '',
      '### Acceptance',
      '- Exactly one pinned per clan per week; edits coalesce.'
    ]},
    { key: 'Concurrency & rate limits', comp: 'comp:shards', body: [
      '### Scope',
      'Protect Sheets/API; single-writer per user; debounce.',
      '',
      '### Tasks',
      '- Per-user lock during writes.',
      '- Debounce summary edits (~500–1000 ms).',
      '- Backoff/retry on 429/5xx.',
      '',
      '### Acceptance',
      '- No duplicate rows under rapid actions.'
    ]},
    { key: 'Validation & staff tools', comp: 'comp:shards', body: [
      '### Scope',
      'Input validation + tiny diagnostics.',
      '',
      '### Tasks',
      '- Validate non-negative integers; warn on giant jumps.',
      '- `!ocr info` / `!ocr selftest` for quick smoke check.',
      '',
      '### Acceptance',
      '- Bad inputs rejected with clear reasons.',
      '- Staff tools do not expose debug info publicly.'
    ]}
  ]
};
// ------------------------------------------------

// ---------- Helpers ----------
async function resolveProject(login, title) {
  // Try user first
  try {
    const r1 = await github.graphql(
      'query($login:String!){ user(login:$login){ projectsV2(first:50){ nodes{ id title number } } } }',
      { login }
    );
    const nodes = r1.user?.projectsV2?.nodes || [];
    const hit = nodes.find(p => p.title === title);
    if (hit) { core.info(`Using user project ${hit.number}: ${hit.title}`); return hit.id; }
  } catch (_) { /* ignore and try org */ }
  // Then org (works if the login is an org)
  const r2 = await github.graphql(
    'query($login:String!){ organization(login:$login){ projectsV2(first:50){ nodes{ id title number } } } }',
    { login }
  );
  const nodes2 = r2.organization?.projectsV2?.nodes || [];
  const hit2 = nodes2.find(p => p.title === title);
  if (hit2) { core.info(`Using org project ${hit2.number}: ${hit2.title}`); return hit2.id; }
  throw new Error(`Project "${title}" not found for ${login}.`);
}

async function addToProject(projectId, nodeId) {
  await github.graphql(
    'mutation($projectId:ID!,$contentId:ID!){ addProjectV2ItemById(input:{projectId:$projectId,contentId:$contentId}){ item{ id } } }',
    { projectId, contentId: nodeId }
  );
}

async function ensureLabel(name, color) {
  try { await github.rest.issues.getLabel({ owner, repo, name }); }
  catch {
    try { await github.rest.issues.createLabel({ owner, repo, name, color }); }
    catch (e) { core.info(`ensureLabel: could not create "${name}" (${e.message || e})`); }
  }
}
// -----------------------------------------------

// 1) Resolve project
const projectId = await resolveProject(PROJECT_OWNER, PROJECT_TITLE);

// 2) Ensure labels exist (best effort)
await ensureLabel('epic', '5319e7');
await ensureLabel('feature', '1f883d');

// 3) Create/retrieve Epic
const epicTitle = `[Feature] ${feature.title}`;
const useCaseBullets = feature.useCases.map(u => `- ${u}`).join('\n');
const planChecklist = feature.subs.map(s => `- [ ] ${s.key}`).join('\n');

let epicNum, epicNode;
{
  const search = await github.rest.search.issuesAndPullRequests({
    q: `repo:${owner}/${repo} is:issue in:title "${epicTitle}"`
  });
  if (search.data.total_count) {
    epicNum = search.data.items[0].number;
    const full = await github.rest.issues.get({ owner, repo, issue_number: epicNum });
    epicNode = full.data.node_id;
  } else {
    const epicBody = [
      ...feature.epicBodyIntro,
      useCaseBullets,
      ...feature.epicBodyMiddle,
      planChecklist,
      ...feature.epicBodyEnd
    ].join('\n');
    const epic = await github.rest.issues.create({
      owner, repo, title: epicTitle,
      labels: ['feature','epic', feature.bot, feature.comp],
      body: epicBody
    });
    epicNum = epic.data.number;
    epicNode = epic.data.node_id;
  }
}
// Add epic to project
await addToProject(projectId, epicNode);

// 4) Create/update children with full bodies + add to project
const childNums = [];
for (const sub of feature.subs) {
  const childTitle = `[Feature] ${sub.key} - ${feature.title}`;
  const search = await github.rest.search.issuesAndPullRequests({
    q: `repo:${owner}/${repo} is:issue in:title "${childTitle}"`
  });
  let num, node;
  if (search.data.total_count) {
    num = search.data.items[0].number;
    const full = await github.rest.issues.get({ owner, repo, issue_number: num });
    node = full.data.node_id;
    const body = (full.data.body || '').trim();
    if (body === '' || /^Split from #\d+$/i.test(body)) {
      await github.rest.issues.update({ owner, repo, issue_number: num, body: sub.body.join('\n') });
    }
  } else {
    const created = await github.rest.issues.create({
      owner, repo, title: childTitle,
      labels: ['feature', feature.bot, sub.comp],
      body: sub.body.join('\n')
    });
    num = created.data.number;
    node = created.data.node_id;
  }
  await addToProject(projectId, node);
  childNums.push(num);
}

// 5) Ensure the epic has a clean task-list linking children (so "Tracked in" works)
const epicFull = await github.rest.issues.get({ owner, repo, issue_number: epicNum });
const newChecklist = childNums.map(n => `- [ ] #${n}`).join('\n');

let newBody;
if (/### Sub-issues/.test(epicFull.data.body || '')) {
  // replace everything from "### Sub-issues" to end with a fresh checklist
  newBody = epicFull.data.body.replace(/### Sub-issues[\s\S]*$/m, `### Sub-issues\n${newChecklist}`);
} else {
  newBody = `${epicFull.data.body}\n\n### Sub-issues\n${newChecklist}`;
}
await github.rest.issues.update({ owner, repo, issue_number: epicNum, body: newBody });

// 6) Done
core.summary
  .addHeading('Feature setup complete')
  .addRaw(`Epic: #${epicNum}\nChildren: ${childNums.map(n => `#${n}`).join(', ')}`)
  .write();
