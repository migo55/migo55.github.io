# SEO & Social Media Marketing Plan

A practical starting plan for **migo55.github.io**. This is a working document —
edit it as your direction firms up. It assumes the site is a **personal brand /
portfolio**; if that changes, revisit the "Goal" and "Content pillars" sections
first, since everything else follows from them.

---

## 1. Start here: define the goal

Marketing only works when it points at a clear outcome. Pick one primary goal:

- [ ] Get hired / find clients
- [ ] Grow an audience around a topic
- [ ] Sell a product or service
- [ ] Something else: ____________________

Everything below should serve that goal. If a tactic doesn't, cut it.

---

## 2. SEO foundations (status)

These are already in the site as of this commit:

| Item | Status | Notes |
|------|--------|-------|
| Descriptive `<title>` and meta description | Done | Update the text to match your real positioning |
| Open Graph tags (nice link previews on LinkedIn/Facebook) | Done | Needs a real `og-image.png` (see below) |
| Twitter/X card tags | Done | Same image |
| Structured data (schema.org Person) | Done | Add your profile URLs to the `sameAs` array |
| `robots.txt` | Done | — |
| `sitemap.xml` | Done | Add a line per page as you add pages |
| Mobile-responsive, dark-mode-aware layout | Done | — |

### Still to do
- [ ] **Create `og-image.png`** (1200×630px). This is the preview image shown
      whenever your link is shared. A simple card with your name + one line is
      enough. Without it, shared links look bare.
- [ ] **Write real content.** Search engines rank pages with substance. Replace
      the placeholder bio, projects, and links (marked `TODO` in `index.html`).
- [ ] **Submit the site to Google.** Go to
      [Google Search Console](https://search.google.com/search-console), add
      `migo55.github.io`, and submit the sitemap. This is the single highest-
      leverage step for getting found on Google.
- [ ] **Add your profile links** and mirror them into the JSON-LD `sameAs`
      array — this tells Google "these accounts are all the same person," which
      strengthens your name search results.

---

## 3. Content pillars

Pick 2–3 themes you'll consistently talk about. Consistency is what builds an
audience and what search engines reward. Example pillars for a portfolio:

1. **Work / projects** — what you build, ship, or make.
2. **Learning in public** — what you're figuring out, lessons, mistakes.
3. **Point of view** — takes on your field, tools, or industry.

> Your pillars: ____________________

---

## 4. Channel strategy

Don't try to be everywhere. Pick **one primary channel** where your audience
actually is, and go deep. Treat the rest as optional repost targets.

| Channel | Best for | Effort |
|---------|----------|--------|
| **LinkedIn** | Career, clients, professional brand | Low–Med |
| **X / Twitter** | Tech, fast conversation, reach | Med |
| **Instagram** | Visual work, design, lifestyle | Med–High |
| **YouTube / TikTok** | Tutorials, personality, big reach | High |
| **GitHub** | Developer credibility (you're already here) | Low |

> Primary channel: ____________________

---

## 5. Cadence (keep it sustainable)

The mistake everyone makes is starting big and burning out. Start small enough
that you'll never skip it:

- **1 post/week** on your primary channel to begin. Raise it only once it's easy.
- **Batch it**: set aside ~1 hour on the same day each week to draft everything.
- **Repurpose**: one good idea → a post, a reply thread, and a site update.

### Simple weekly loop
1. Ship or learn something (from a content pillar).
2. Post about it on your primary channel.
3. Link back to the site when relevant (drives SEO + shows depth).

---

## 6. Measuring what works

You can't improve what you don't watch. Check monthly, not daily:

- **Google Search Console** — what search terms bring people to the site.
- **Channel's built-in analytics** — which posts landed, which flopped.
- **One north-star number** tied to your goal (e.g., inbound messages, profile
  visits, project inquiries). Track just that one closely.

---

## 7. First-week checklist

A concrete, do-able starting sequence:

- [ ] Replace all `TODO` placeholders in `index.html` with real content.
- [ ] Create and add `og-image.png`.
- [ ] Fill in your real profile links (site + JSON-LD `sameAs`).
- [ ] Set up Google Search Console and submit the sitemap.
- [ ] Choose your one primary channel and your 2–3 content pillars.
- [ ] Write and schedule your first post.

Do these six things and you'll be genuinely ahead of most personal sites.
