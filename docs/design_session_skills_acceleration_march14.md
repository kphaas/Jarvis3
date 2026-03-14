# JARVIS Design Session: Skills Acceleration Strategy
**Date:** March 14, 2026  
**Session Type:** Architecture Review + Skills Integration Planning  
**Duration:** 2-3 hours

---

## Session Agenda

1. **Completed Work Evaluation** (What we've built)
2. **Remaining Gaps Analysis** (What's left to build)
3. **Skills Repository Survey** (What's available)
4. **Acceleration Mapping** (Which skills eliminate which gaps)
5. **Integration Strategy** (How to install without breaking anything)
6. **Prioritization Matrix** (Install order and dependencies)

---

## Part 1: Completed Work Evaluation (Feb 1 - Mar 14, 2026)

### ✅ Core Infrastructure (100% Complete)

**Routing & Orchestration:**
- [x] Adaptive complexity router (keyword + complexity scoring)
- [x] Multi-provider support (Ollama, Perplexity, Claude)
- [x] Cost tracking per call (Postgres cost_logger)
- [x] Budget enforcement (daily limits, alerts at 75%/90%)
- [x] User profiles (Ken + 2 household members with caps)

**Memory System (Phase 6a):**
- [x] 6 Postgres tables with pgvector
- [x] Sentence-transformers embeddings (384-dim)
- [x] RAG pattern for conversation retrieval
- [x] 2,346+ conversations stored

**Network Architecture:**
- [x] 3-node distributed system (Brain, Gateway, Endpoint)
- [x] Tailscale VPN mesh (100.64.0.0/10)
- [x] SSH mesh (jarvis_agent key on all paths)
- [x] Brain airgapped (no internet access)
- [x] Gateway as sole egress point

**Security & Secrets:**
- [x] Secrets consolidated to .secrets file
- [x] Git branch protection (main locked)
- [x] Pre-commit hooks (private keys, large files)
- [x] MCP security scanner (Phase 1)

**Operations:**
- [x] Dependency-based boot sequencing
- [x] System health monitoring (7 services)
- [x] Dashboard with 10 tabs
- [x] Overnight agent (11 PM daily runs)
- [x] Postgres WAL archiving to Unraid

**Voice & Presentation:**
- [x] Faster-whisper STT
- [x] Kokoro TTS (Apple Silicon optimized)
- [x] Canvas 2D animated avatars
- [x] Voice UI at :4001
- [x] Avatar service at :4002

### 📊 By the Numbers

- **Total Queries:** 2,346 (Feb 1 - Mar 14)
- **Cost:** $10.60 total ($0.0045/query average)
- **Free Query %:** 79% (Ollama local models)
- **Routing Accuracy:** ~85% (based on cost distribution)
- **Uptime:** 99.9% (one restart for SSH fix)
- **Code Base:** 15,000+ lines across 50+ files
- **Git Commits:** 60+ commits
- **Development Time:** 6 weeks (part-time)

### 🎯 What Works Really Well

1. **Cost Control is Exceptional**
   - $0.0045/query vs industry $0.05-0.15
   - Budget caps prevent runaway costs
   - 79% free local routing

2. **Boot Sequencing is Bulletproof**
   - Zero failed startups after dependency implementation
   - Services gracefully wait for dependencies
   - Health check catches issues immediately

3. **Memory Persistence is Solid**
   - Postgres + WAL = reliable storage
   - 48 WALs archived, 0 failures
   - Embeddings working for RAG

4. **Router is Smart Enough**
   - Keyword detection works (code→qwen, web→scrape)
   - Complexity scoring reasonable
   - 85% accuracy is good baseline

---

## Part 2: Remaining Gaps Analysis

### 🔴 Critical Gaps (Blocking Phase 8)

**GAP 1: Circuit Breakers (Router Enhancement)**
- **Current State:** No error tracking per provider
- **Impact:** Failing providers aren't auto-disabled
- **Effort Without Skills:** 1 week (error tracking, cooldown logic, auto-recovery)
- **Skill Opportunity:** ❓ Any MCP skills for monitoring/alerting?

**GAP 3: Brain /state Endpoint (Avatar Integration)**
- **Current State:** Avatar has no state visibility
- **Impact:** Can't sync avatar emotions with conversation
- **Effort Without Skills:** 2 days (endpoint + avatar integration)
- **Skill Opportunity:** ❌ None (too JARVIS-specific)

**GAP 4: Memory Consolidation**
- **Current State:** Conversations grow unbounded
- **Impact:** Postgres bloat, slower queries over time
- **Effort Without Skills:** 1 week (summarization logic, decay scoring)
- **Skill Opportunity:** ✅ **Memory MCP** (Anthropic) - handles consolidation

**GAP 5: MCP Security - Phase 2 (Docker Sandbox)**
- **Current State:** Scanner done, no sandbox yet
- **Impact:** Can't safely run untrusted MCP servers
- **Effort Without Skills:** 2 weeks (Docker setup, permission gateway, dashboard UI)
- **Skill Opportunity:** ❌ None (security layer is JARVIS-specific)

**GAP 6: jarvis_sandbox User**
- **Current State:** Untrusted code runs as jarvisbrain
- **Impact:** Security risk
- **Effort Without Skills:** 1 day (user creation, permission setup)
- **Skill Opportunity:** ❌ None (OS-level config)

**GAP 9: CI/CD Pipeline**
- **Current State:** No automated testing
- **Impact:** Regression risk as code grows
- **Effort Without Skills:** 1 week (GitHub Actions, lint, test, Bandit)
- **Skill Opportunity:** ✅ **GitHub MCP** - auto-create PR workflows

### 🟡 Medium Priority Gaps

**Code Generation Persistence:**
- **Current:** Code shows in chat, manual copy-paste to files
- **Effort:** N/A (manual workflow)
- **Skill:** ✅ **Filesystem MCP** - eliminates manual step entirely

**Postgres Connection Pooling:**
- **Current:** New connection per request
- **Effort:** 3 days (asyncpg pool setup, testing)
- **Skill:** ✅ **PostgreSQL MCP** - may include pooling patterns

**Atlanta News Feeds:**
- **Current:** WSB-TV, AJC broken (timeout/paywall)
- **Effort:** 1 day (find alternative sources)
- **Skill:** ✅ **Brave Search MCP** - real-time news better than RSS

**Web Scraping Fragility:**
- **Current:** Gateway fetch + BeautifulSoup breaks often
- **Effort:** Ongoing maintenance (sites change)
- **Skill:** ✅ **Brave Search MCP** OR **Puppeteer MCP** - more reliable

### 🟢 Phase 9 Features (Want, Not Need)

**3D Avatar Upgrade:**
- **Effort:** 2 weeks (Ready Player Me integration, Three.js renderer)
- **Skill:** ❓ UI/UX Pro Max might have Three.js templates?

**Wake Word Detection:**
- **Effort:** 1 week (Porcupine integration, testing)
- **Skill:** ❌ None found

**HomePod AirPlay Routing:**
- **Effort:** 3 days (macOS AirPlay API)
- **Skill:** ❌ None found

**Home Assistant Integration:**
- **Effort:** 2 weeks (API, webhook setup, testing)
- **Skill:** ✅ **Home Assistant MCP** exists!

**Google Calendar Integration:**
- **Effort:** 1 week (OAuth, sync logic)
- **Skill:** ✅ **Google Calendar MCP** exists!

**Dynamic Routing Weights (ML-based):**
- **Effort:** 2 weeks (training data, model, A/B testing)
- **Skill:** ✅ **Sequential Thinking MCP** - better reasoning for complexity

---

## Part 3: Skills Repository Survey

### Source 1: modelcontextprotocol/servers (Official Anthropic)
**Already Scanned:** Risk score 75 (SANDBOX REQUIRED)

**Available Skills (from our scan):**
- Filesystem (read/write files)
- Brave Search (web search)
- GitHub (issues, PRs, repos)
- Google Drive
- Google Maps
- Slack
- PostgreSQL
- Memory (persistent context)
- Sequential Thinking (step-by-step reasoning)
- Fetch (HTTP requests)
- Puppeteer (browser automation)
- Git (version control)
- Time (current time/date)

### Source 2: skillboss by claude
**Need to research:** GitHub repo link?

### Source 3: awesome-openclaw-skills
**Need to research:** Is this "awesome-mcp-servers"? Link?

### Source 4: scrapling on github
**Need to research:** Advanced web scraping? Link?

### Source 5: everything-claude-code
**Need to research:** Code generation templates? Link?

### Source 6: ui ux pro max
**Need to research:** Frontend skill pack? Link?

**ACTION NEEDED:** Provide GitHub links for sources 2-6 so we can evaluate them.

---

## Part 4: Acceleration Mapping (Skills → Gaps)

### High-Impact Eliminations (Install First)

| Skill | Eliminates Gap | Time Saved | Install Risk |
|-------|---------------|------------|-------------|
| **Filesystem MCP** | Code generation persistence | Ongoing (every code gen) | LOW - Sandboxed paths |
| **GitHub MCP** | GAP 9 (CI/CD setup) | 1 week | LOW - Read-only first |
| **Memory MCP** | GAP 4 (Memory consolidation) | 1 week | MEDIUM - Postgres integration |
| **Brave Search MCP** | Web scraping fragility | Ongoing maintenance | LOW - Replace gateway fetch |
| **PostgreSQL MCP** | Connection pooling patterns | 3 days | LOW - Advisory only |

### Medium-Impact Additions (Install Second Wave)

| Skill | Adds Capability | Time Saved | Install Risk |
|-------|----------------|------------|-------------|
| **Sequential Thinking** | Better code generation | 40% fewer bugs | LOW - Pure reasoning |
| **Google Calendar** | Phase 9 calendar integration | 1 week | MEDIUM - OAuth setup |
| **Home Assistant** | Phase 9 smart home | 2 weeks | MEDIUM - Network access |
| **Puppeteer MCP** | Better web scraping | Ongoing | HIGH - Browser automation |

### Low-Priority Nice-to-Haves

| Skill | Benefit | When to Install |
|-------|---------|----------------|
| Google Drive | Cloud file access | Phase 10 |
| Slack | Notifications | Phase 10 (if you use Slack) |
| Time | Current time queries | Phase 10 (low value) |
| Google Maps | Location queries | Phase 10 (low value) |

---

## Part 5: Integration Strategy (No Breaking Changes)

### Principle: MCP Skills are Additive

**What MCP Skills DON'T Replace:**
- ❌ Your routing logic stays
- ❌ Your cost tracking stays
- ❌ Your memory tables stay
- ❌ Your budget enforcement stays
- ❌ Your user profiles stay

**What MCP Skills ADD:**
- ✅ New capabilities Claude can use
- ✅ Better tools for code generation
- ✅ Shortcuts for common tasks
- ✅ Integrations you'd build anyway

### Installation Pattern (Safe)
```python
# Phase 1: Scan
result = scan_mcp_server("https://github.com/anthropic/mcp-servers")

# Phase 2: Review Findings
if result['risk_score'] > 75:
    # Require manual approval
    await request_approval(result)

# Phase 3: Install to Registry
await install_mcp_server(
    server_name="filesystem",
    trust_level="VERIFIED",  # or SANDBOX
    approved_by="ken"
)

# Phase 4: Your Router Decides When to Use It
def route(user_input):
    if "create file" in user_input:
        # Router can now choose filesystem MCP as a tool
        return {"target": "claude", "tools": ["filesystem"]}
```

**Key Point:** Skills don't auto-activate. Your router still controls everything.

---

## Part 6: Prioritization Matrix

### Install Wave 1: Code Acceleration (This Weekend)

**Priority 1: Filesystem MCP**
- **Why First:** Immediate ROI on every code generation
- **Risk:** LOW (sandboxed write paths)
- **Setup Time:** 30 minutes
- **Test:** Generate a new endpoint, verify file created

**Priority 2: GitHub MCP**
- **Why Second:** Enables auto-PR workflow
- **Risk:** LOW (start read-only)
- **Setup Time:** 1 hour (OAuth)
- **Test:** Create issue for GAP 3, link to commit

**Priority 3: Sequential Thinking MCP**
- **Why Third:** Better code quality immediately
- **Risk:** NONE (pure reasoning)
- **Setup Time:** 15 minutes
- **Test:** Complex refactor task

### Install Wave 2: Integration Elimination (Next Week)

**Priority 4: Brave Search MCP**
- **Replaces:** Gateway fetch + BeautifulSoup
- **Setup Time:** 30 minutes
- **Test:** News query, compare to current scraper

**Priority 5: Memory MCP**
- **Replaces:** Custom consolidation logic
- **Setup Time:** 2 hours (Postgres integration)
- **Test:** Long conversation, verify consolidation

**Priority 6: PostgreSQL MCP**
- **Advisory:** Connection pooling patterns
- **Setup Time:** 1 hour
- **Test:** Query optimization suggestions

### Install Wave 3: Phase 9 Features (Future)

**Priority 7: Google Calendar**
**Priority 8: Home Assistant**
**Priority 9: Puppeteer** (if needed)

---

## Part 7: Open Questions for Discussion

### Architecture Decisions

**Q1: Sandbox Strategy**
- Docker on Brain (current plan) vs dedicated Mac Mini?
- How aggressive on sandboxing? (VERIFIED trust level ok?)

**Q2: Filesystem Paths**
- Which directories allow MCP file writes?
- Proposal: `/Users/jarvisendpoint/jarvis/generated/` only

**Q3: GitHub Integration Scope**
- Auto-create PRs? Or just read-only for now?
- Link GAP tasks to GitHub Issues?

**Q4: Memory MCP vs Your Tables**
- Use Memory MCP alongside your Postgres tables?
- Or migrate entirely to Memory MCP?

### Skill Source Verification

**Q5: Other Skill Repositories**
- GitHub links for skillboss, awesome-openclaw, scrapling, everything-claude-code, ui-ux-pro-max?
- Are these Claude Desktop skills or MCP servers?
- Do they work with self-hosted Claude (your setup)?

### Timeline & Budget

**Q6: Installation Budget**
- Skills are free to install, but using them costs API calls
- Filesystem writes during code gen: +$0.01-0.02 per generation
- Acceptable cost increase?

**Q7: Phase 8 Timeline**
- Original: 2 weeks for security hardening
- With skills: Maybe 1 week? (GitHub MCP helps CI/CD)
- Adjust timeline?

---

## Part 8: Success Metrics

### How We'll Know Skills Are Working

**Code Generation Speed:**
- Before: Generate code → copy-paste → test
- After: Generate code → auto-written → test
- **Target:** 5 min saved per code gen = 50 min/week

**Development Velocity:**
- Before: 1-2 features per week
- After: 3-5 features per week
- **Target:** 2x feature output

**Cost Per Feature:**
- Before: ~$2-3 in API costs per new feature
- After: ~$3-4 (slight increase from skill usage)
- **Target:** <$5 per feature (acceptable)

**Bug Rate:**
- Before: ~15% of generated code needs fixes
- After: ~8% (Sequential Thinking improves quality)
- **Target:** <10% bug rate

**Time to Phase 9:**
- Before: 4 weeks estimated
- After: 2 weeks with Calendar + Home Assistant skills
- **Target:** Ship Phase 9 by April 15

---

## Part 9: Risk Assessment

### What Could Go Wrong

**Risk 1: Skill Conflicts**
- **Scenario:** Two skills try to write same file
- **Mitigation:** Filesystem paths carefully scoped
- **Likelihood:** LOW

**Risk 2: Cost Explosion**
- **Scenario:** Skill makes excessive API calls
- **Mitigation:** Budget caps still enforced
- **Likelihood:** LOW (budget system unchanged)

**Risk 3: Security Breach**
- **Scenario:** Sandboxed skill escapes
- **Mitigation:** Docker isolation (Phase 2)
- **Likelihood:** VERY LOW (verified skills first)

**Risk 4: Postgres Corruption**
- **Scenario:** Memory MCP conflicts with your tables
- **Mitigation:** Test on dev database first
- **Likelihood:** LOW (separate tables)

**Risk 5: Integration Complexity**
- **Scenario:** Too many skills, hard to maintain
- **Mitigation:** Install max 6 skills in Wave 1
- **Likelihood:** MEDIUM (discipline required)

---

## Part 10: Next Steps (Action Plan)

### Immediate (Tonight)

1. ✅ Mount overnight router (`app.include_router(overnight_router)`)
2. ✅ Update architecture_review document with skills plan
3. ❓ Get GitHub links for skill sources 2-6
4. ❓ Review skill repositories together
5. ❓ Decide Wave 1 install list (3-4 skills max)

### This Weekend

6. Install Filesystem MCP
7. Install GitHub MCP  
8. Install Sequential Thinking MCP
9. Test all 3 with real code generation tasks
10. Measure time savings

### Next Week

11. Install Brave Search MCP
12. Replace Gateway scraper routing
13. Test news queries
14. Install Memory MCP
15. Test consolidation

### Phase 8 (Revised with Skills)

16. GitHub MCP: Auto-PR creation
17. mTLS setup (Tailscale certs)
18. jarvis_sandbox user
19. MCP Docker sandbox (for untrusted skills)
20. CI/CD pipeline (GitHub Actions)

---

**END OF DESIGN SESSION DOCUMENT**
**Ready for collaborative editing and decision-making.**
