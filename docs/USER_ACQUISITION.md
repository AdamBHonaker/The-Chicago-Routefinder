# The Chicago Routefinder — User Acquisition Plan

> Marketing/growth reference. Not a chunked feature plan — this is the playbook for *getting people to know the app exists and install it* once Phase 6 (deployment) is done and Phase 7 (house ads) is in flight.

## Context

The app is feature-complete through Phase 6 (editorial redesign + map markers, deployed to Railway/Vercel). Phase 7 (house ads) is the only build work left. The next real growth lever is **getting people to know it exists and install it**.

Two unusually strong differentiators most transit apps lack:

1. **Routing accuracy** — a real NetworkX graph over unified train+bus GTFS with live CTA Train/Bus Tracker feeds and walking legs. Google Maps and Transit App both make routing mistakes on the CTA (wrong transfers, ghost buses, stale shapes). This one doesn't.
2. **22+ languages** — Chicago has the third-most linguistically diverse transit ridership in the U.S. No mainstream transit app does this seriously.

Constraints shaping every recommendation below: **full-time job, solo maintainer, based at Argyle/Uptown, no marketing budget assumed.** This plan optimizes for **asynchronous, high-leverage moves** — things you can do in a 90-minute evening block — and explicitly avoids tactics that require sustained daytime hustle.

---

## Honest assessment of the PWA limitation

The PWA model is the single biggest acquisition headwind. Be clear-eyed about what it costs and what to do about each:

| Limitation | Real impact | Mitigation |
|---|---|---|
| **No App Store / Play Store presence** | Loses ~70% of how normal users discover apps. People type "CTA app" into the App Store. | (a) Aggressive SEO on a clean domain (`chicagoroutefinder.com` or similar). (b) Get listed in third-party directories: PWAList, AppScope, alternativeto.net, "Transit App alternatives" listicles. (c) Long-term: a thin Capacitor/PWABuilder wrapper to publish to Play Store costs ~$25 + a weekend. iOS App Store wrapper is harder ($99/yr + review friction) but worth it once there's traction. |
| **iOS install friction** (Share → Add to Home Screen, no install prompt) | Maybe 40–50% of iPhone users who land on the page bounce because they don't know how to "install." | A 10-second looping silent video on the landing page: "Tap Share → Add to Home Screen." Plus auto-detect iOS Safari and show a one-line banner with an animated arrow pointing at the Share button. Typically doubles iOS install rate. |
| **No store reviews / social proof** | New users can't see "4.6★ from 10k reviews." | Collect testimonials directly (a one-question post-trip prompt: "Was this route accurate?"). Surface 3–5 quotes on the landing page. Submit to Product Hunt and treat the upvote count as the review badge. |
| **Push notifications gated behind install** (iOS 16.4+) | Can't re-engage users who didn't install. | Don't try. Treat first-session conversion as the only metric that matters. Email is the only retention channel for non-installers — offer an optional "Service alerts for your saved routes" email subscription. |
| **PWAs feel "less legitimate"** to non-technical users | Trust gap, especially in immigrant communities wary of scams. | (a) HTTPS + custom domain (no `vercel.app` subdomain in front of users). (b) An "About" page with real name, photo, and the technical story. (c) Press coverage (even one Block Club Chicago story) functions as a trust badge. |
| **Updates are silent** | Can't market "version 2.0!" the way native apps can. | Reframe as a feature: "Always up to date, no app store update needed." Mention it in the About page. |

**The PWA model is not a dealbreaker** — it's a tax. The 22-language and accuracy advantages are large enough to overcome it, but only if the install-friction issue is addressed head-on. Fix iOS install onboarding before any acquisition push.

---

## Tactics ranked by ROI given the constraints

### Tier 1 — do these first (highest leverage, lowest time cost)

1. **Chi Hack Night** — Tuesday evenings, free, civic-tech meetup at Merchandise Mart. Their entire audience is the exact intersection of "cares about Chicago" + "appreciates a custom routing engine" + "has a megaphone." A 5-minute lightning talk or demo gets you in front of 80–150 people who all post on Twitter/Bluesky. **One Tuesday evening. Highest single-event ROI in Chicago.**
2. **Reddit launches, sequenced not simultaneous** —
   - `r/chicago` (700k members): lead with the multilingual angle, *not* the technical one. Title: "I built a free CTA app that works in 22 languages — looking for feedback from Spanish/Vietnamese/Chinese/Polish speakers." Pin a comment with the technical story for the engineers.
   - `r/uptownchicago`, `r/RogersPark`, `r/AndersonvilleChicago` (home turf, smaller but more receptive): localize the pitch.
   - `r/CTA`: lead with accuracy. Show a side-by-side where Google Maps gets a transfer wrong and this app doesn't.
   - `r/programming` / Hacker News "Show HN": lead with the graph engine, GTFS pipeline, the Railway free-tier OSMnx trick.
   - **Space these out by 2–3 weeks.** Each is one evening of polish + a day of comment-replying.
3. **Block Club Chicago tip line** (`tips@blockclubchi.org`) — they cover hyperlocal Chicago stories and love "neighbor builds civic tool" angles. The Argyle/Uptown angle (Vietnamese/Chinese/Lao/Ethiopian residents, transit-dependent, 22 languages) is *exactly* their beat. One good email = potentially 50k+ readers. Streetsblog Chicago (`tips@streetsblog.org`) is the transit-nerd parallel.
4. **iOS install onboarding fix** — see PWA mitigations above. Engineering, not marketing, but doubles the conversion of every other tactic on this list. Do it before the Reddit posts.

### Tier 2 — async, immigrant-community focused (structural advantage)

5. **Aldermanic newsletters** — Ald. Leni Manaa-Hoppenworth (48th Ward) sends a weekly newsletter to thousands of Uptown residents. A single email pitch to her office ("free multilingual transit tool built by a constituent") has a real chance of being included. Repeat for 46th (Lakeview), 40th (Lincoln Square/Albany Park — extremely linguistically diverse), 47th, 39th. **Five emails, one evening.**
6. **Community organization partnerships** — *the* way to reach non-English-speaking riders, who benefit most from 22-language support:
   - Vietnamese Association of Illinois (Argyle)
   - Chinese American Service League (Chinatown)
   - ICIRR (Illinois Coalition for Immigrant and Refugee Rights) — umbrella org, one email reaches dozens of member orgs
   - Centro Romero, Erie Neighborhood House, Ethiopian Community Association
   - Truman College ESL program (Uptown, on Wilson) — instructors love free tools for students
   - Pitch: "free tool, no signup, no ads, works offline-ish, shows transit in [their language]." Offer a 15-min Zoom demo.
7. **Chicago Public Library** — branch managers at Uptown, Chinatown, Albany Park, and Rogers Park branches are usually receptive to printed flyers about free civic tools, especially multilingual ones. One flyer design, eight branches, one Saturday morning.
8. **Multilingual press** — Hoy Chicago / La Raza (Spanish), World Journal (Chinese), Korea Times Chicago, Vietnamese-language Chicago papers. Many have very small newsrooms and *will* run a story about a free tool serving their readership. The Argyle origin story is the hook.

### Tier 3 — broader reach, more time per unit of return

9. **Product Hunt launch** — one-day burst, requires prep (gallery, tagline, hunter coordination). Probably 2k–10k visits if it goes well, mostly tech audience. Worth doing *once* the iOS onboarding is polished and there are a few testimonials to display.
10. **Short-form video** — TikTok/Reels showing a side-by-side: "Google Maps says take the 36, but the 36 is rerouted right now. Here's an app that knows." Demonstrate the language switcher. Demoing accuracy is more shareable than describing it. One good 30-second video can outperform every other channel. The catch: have to make several before one lands.
11. **CTA itself** — tag `@cta` on Bluesky/Twitter/Instagram with a polished demo. They occasionally amplify third-party tools. Low probability, ~zero cost.
12. **Transit-nerd corners** — Chicago-L.org forums, the Chicago Transit & Railfans Facebook group, the Urban Rail Magazine subreddit. Small but they spread the word in transit circles.

### Tier 4 — explicitly skip (or defer)

- **Paid ads** — don't, until monetization is in place (Phase 7+). Burning money to acquire users who can't be monetized is a treadmill.
- **Conference circuit / TRB / APTA** — high time cost, wrong audience (operators, not riders).
- **Cold-emailing journalists at the Tribune/Sun-Times** — much lower hit rate than Block Club. Defer until there's a real news hook (1k installs, a CTA partnership, etc.).
- **QR-code stickers on bus stops** — illegal flyposting, CTA will remove them, conversion rate is awful. Skip.

---

## Concrete 4-week plan that fits around a full-time job

**Week 1 (≈4 evenings):** ship iOS install onboarding fix + collect 3–5 testimonials from friends/family who already use it. Polish the landing page (real domain, About page with photo + name, install instructions video).

**Week 2 (≈3 evenings):** Chi Hack Night demo (one Tuesday, 6:00–9:00 PM). Email Block Club Chicago and Streetsblog. Email five aldermen.

**Week 3 (≈2 evenings):** `r/chicago` and `r/CTA` posts on consecutive evenings. Reply to every comment. Cross-post to neighborhood subs.

**Week 4 (≈3 evenings + 1 Saturday):** email immigrant-community organizations (15 emails, batched). Saturday morning: print flyers, walk them to Uptown + Chinatown libraries.

After week 4, evaluate metrics. If install conversion is healthy, run the Product Hunt + Hacker News Show HN sequence the following month.

---

## The 22-language angle is the moat — lead with it

Most US transit apps treat translation as a checkbox. This one treats it as the product. **In every single pitch above, lead with the multilingual story.** It's:

- More emotionally resonant than "graph-based routing" (even though that's also true)
- Exactly the angle that makes Block Club, aldermen, libraries, and community orgs say yes
- Hard for competitors (Google Maps, Transit App) to credibly counter — they technically translate the UI, but their accuracy and stop-name handling in non-English languages is poor

The accuracy story is for engineers (HN, r/programming, Chi Hack Night). The languages story is for everyone else. Don't mix them in the same pitch.

---

## Verification / how to know it's working

- Add minimal analytics (Plausible or Umami — both privacy-respecting and free-tier friendly). Track only: landing-page visits, install events (`beforeinstallprompt` + iOS heuristic), first route searched.
- Set a weekly check-in on Sunday evening to look at: visits, installs, install rate (target: >15% on Android, >5% on iOS — iOS will always lag because of friction).
- After each acquisition push (Reddit post, press story), watch the 48-hour spike, then the 7-day retention. Retention >20% week-over-week means the product is sticky enough to keep pushing acquisition. Below that, fix the product before pushing more traffic.

---

## Critical files (cited for context; no modifications driven by this plan)

- [frontend/src/App.jsx](../frontend/src/App.jsx) — landing/first-run experience lives here; iOS install banner would go here
- [frontend/index.html](../frontend/index.html) — meta tags, OG tags, manifest reference (review for SEO before any acquisition push)
- `frontend/public/manifest.webmanifest` (if it exists) — confirm `name`, `short_name`, `description`, icons are all polished before submitting to PWA directories
- `frontend/public/locales/` — the 22-language moat; keep advertising it
