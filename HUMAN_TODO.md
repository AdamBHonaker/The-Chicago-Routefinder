# Human To-Do List

Tasks that require human action — account creation, API keys, billing, etc.
Claude cannot do these. Check them off as you go.

---

## Accounts to Create

- [ ] **Railway** — backend hosting (free tier)
  - Go to railway.app → "Sign in with GitHub"
  - No credit card required for free tier

- [ ] **Vercel** — frontend hosting (free tier)
  - Go to vercel.com → "Continue with GitHub"
  - No credit card required for free tier

---

## API Keys to Obtain

- [x] **CTA Train Tracker API key** ✅
- [x] **CTA Bus Tracker API key** ✅
- [x] **Anthropic API key** ✅
- [ ] **Google Maps API key** ← required before deployment
  - Go to console.cloud.google.com → create or select a project
  - Enable the **Geocoding API** (not Places API — just Geocoding)
  - Create an API key under "Credentials"
  - Add to `backend/.env` as `GOOGLE_MAPS_API_KEY=your_key_here`
  - Also add to Railway dashboard env vars (Settings → Variables) before deploying
  - Free tier: ~40,000 geocoding calls/month — well within expected usage
  - Once you have the key, tell Claude and the implementation will be done immediately (single function swap in `gtfs_loader.py`)

---

## Phase 6 — Deployment (do after accounts above are ready)

- [ ] Deploy backend to Railway (see step-by-step in `cta_app_handoff_prompt.md`)
- [ ] Set environment variables in Railway dashboard:
  - `CTA_TRAIN_API_KEY`
  - `CTA_BUS_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_MAPS_API_KEY` ← required for address/landmark geocoding
  - `ALLOWED_ORIGINS` ← fill in after Vercel URL is known
- [ ] Deploy frontend to Vercel (see step-by-step in `cta_app_handoff_prompt.md`)
- [ ] Set `VITE_BACKEND_URL` in Vercel dashboard → your Railway URL
- [ ] Go back to Railway and set `ALLOWED_ORIGINS` → your Vercel URL, then redeploy
- [ ] Update `frontend/.env.production` with the real Railway URL and commit
- [ ] Test the live app end-to-end on the public URLs
- [ ] (Optional) Add a custom domain in Vercel dashboard → Settings → Domains

---

## Map UI — Pre-Deployment Checks

- [ ] **Confirm desktop split-panel width ratio** — currently set to 40% route cards / 60% map. Check this on a real desktop screen before deployment and adjust if needed.

- [ ] **Confirm mobile minimum heights** — currently set to route card panel min-height: 300px, map min-height: 350px. Test on a real mobile device before deployment and adjust if needed.

- [ ] **Source and provide transit location photos** — at least 10 photos needed for the loading/no-routes map panel. Decide on sourcing approach:
  - Option A: Take your own photos at CTA locations
  - Option B: Free stock photos from Unsplash or Wikimedia Commons (verify license per image)
  - Option C: Combination of both
  - Each photo needs a location name caption (e.g. "Addison · Red Line", "O'Hare · Blue Line", "95th/Dan Ryan · Red Line")
  - Once sourced, place images in `frontend/public/transit-photos/` and give Claude the list of filenames + captions to wire up

---

## Phase 7 — Monetization (future)

- [ ] Research and select an ad network (Google AdSense is the standard starting point for a utility app)
- [ ] Apply for AdSense account at adsense.google.com — requires a live public URL, so do this after Phase 6
- [ ] Share AdSense publisher ID with Claude to wire up ad placements in the frontend

---

## Ongoing Maintenance

- [ ] **GTFS data** — CTA updates its static feed periodically. Railway re-downloads it on every deploy, but if you go weeks without deploying, restart the Railway service manually to pull fresh data.
- [ ] **Monitor Anthropic API costs** — check console.anthropic.com/usage monthly, especially after any public launch push
- [ ] **CTA API keys** — both are free but may require periodic renewal; check transitchicago.com if API calls start failing
