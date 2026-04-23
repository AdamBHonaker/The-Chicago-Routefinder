This document is designed to be pasted directly into a `CONTEXT.md` file or provided as a prompt to Claude Code to give it full architectural and aesthetic awareness of your project.

---

# Project Context: CTA Transit PWA

## 1. Project Vision
A high-utility, minimalist Progressive Web App (PWA) for Chicago transit commuters. The goal is to provide a faster, more aesthetic alternative to official apps, operating at near-zero marginal cost with the potential to cover subscription costs through non-intrusive, privacy-focused advertising.

## 2. Technical Stack
* **Frontend:** React-based PWA hosted on **Vercel**.
* **Backend:** Node.js/Express service hosted on **Railway** (handles CTA API polling and CORS management).
* **Data Sources:** Real-time CTA Train Tracker and Bus Tracker APIs.
* **Persistence:** `localStorage` for zero-login "Favorites" (current plan).

## 3. Design System (Direction: "Heritage Organic")
The UI follows a specific aesthetic described as **"Classic CTA meets Edgewater Candles."**
* **Core Palette:** * Background: `#f2ece0` (Cream/Paper)
    * Text/Accents: Deep Charcoal
    * Borders: `#c9bfa8` (Muted Tan)
    * Line Colors: Use official CTA colors (Red, Blue, Green, etc.) strictly for status indicators and route badges.
* **Philosophy:** Minimalist, sophisticated, and functional. Avoid "tech-heavy" dark modes or high-gloss buttons. It should feel like a well-designed physical transit pamphlet.

## 4. Current State
* **Functional:** Real-time fetching of bus and train data is implemented and working via the Railway proxy.
* **In-Progress:** "Favorites" and "Saved Routes" have been scoped but not yet implemented.
* **UI/UX:** Initial redesign concepts have been drafted; the "Heritage Organic" (Design #2) is the chosen direction for the next iteration.

## 5. Development Roadmap (Priorities for Claude Code)
1.  **Favorites Implementation:**
    * Create a `SavedStopsContext` to manage stop IDs in `localStorage`.
    * Add "Pin/Save" toggles to arrival cards.
    * Implement a "Pinned Stations" section on the Home screen.
2.  **Monetization Readiness:**
    * Reserve a component slot for a single **EthicalAds** or **Carbon Ads** unit (small, text-heavy, minimalist).
    * Design "House Ad" placeholders for contextually relevant affiliates (e.g., minimalist footwear, local services).
3.  **Feature Expansion:**
    * "Last Train" countdown timer for late-night commuters.
    * Toggleable "Walking Speed" adjustment for arrival estimates.
    * Service alerts integration.

## 6. Operational Constraints
* **Performance:** The app must remain extremely lightweight to function well on platform Wi-Fi/cellular.
* **Aesthetics:** Any new UI elements must strictly adhere to the organic/cream-and-charcoal design language.
* **Privacy:** No heavy tracking; favor contextual relevance over behavioral data.

---

### Suggested First Prompt for Claude Code:
> "I am working on the CTA Transit PWA. Based on the `CONTEXT.md` (above), let's start by implementing the 'Favorites' functionality. I need a React hook that manages saved Stop IDs in `localStorage` and a 'Pin' button component that matches our Heritage/Organic aesthetic (cream and charcoal)."