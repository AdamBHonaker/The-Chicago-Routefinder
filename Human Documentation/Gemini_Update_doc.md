This handoff document is tailored to reflect the substantial progress you’ve already made on the infrastructure while focusing Claude Code’s attention on the specific design evolution and the monetization/utility features discussed in this session.

***

# Project Handoff: CTA Transit PWA Evolution

## 1. Executive Summary & Current State
The project is a functional, high-utility Progressive Web App for Chicago transit. 
* **Production Environment:** Frontend is live on **Vercel**; Backend is hosted on **Railway**.
* **Core Logic:** The app successfully fetches and displays live Bus and Train data via the CTA API, with CORS and proxying managed through the Railway backend.
* **Maturity:** The "plumbing" is solid. The current phase focuses on **UI Refinement**, **User Persistence**, and **Monetizing to cover operational/subscription costs**.

## 2. Design System: "Heritage Organic" (Direction #2)
The aesthetic is shifting from a standard "tech" UI to a "Classic CTA meets Edgewater Candles" look.
* **Visual Language:** High-legibility, minimalist, and sophisticated.
* **Palette:** * Background: `#f2ece0` (Cream/Paper)
    * Typography/Accents: Deep Charcoal
    * Borders/Dividers: `#c9bfa8` (Muted Tan)
* **Line Identity:** Use official CTA colors (Red, Blue, etc.) strictly for functional status indicators, maintaining the neutral cream-and-charcoal base for the rest of the UI.
* **ADA & Accessibility:** Design #2 prioritizes high contrast for charcoal-on-cream and clear typography, ensuring the utility remains accessible to commuters with visual impairments or those in high-glare environments (e.g., outdoor platforms).

## 3. Monetization Strategy (Low-Footprint Ads)
The goal is to cover the **$25/month** Claude subscription and hosting fees using a "one-ad-only" model.
* **Provider Targets:** EthicalAds (Privacy-first) or Carbon Ads (Designer-focused).
* **Ad Placement:** A single, minimalist unit that blends into the "Heritage Organic" design.
* **The "House Ad" Strategy:** Implement a placeholder for contextual affiliates (e.g., minimalist footwear, local Chicago services) to be used when network fill rates are low or during the initial traffic-growth phase.

## 4. Feature Enhancements (Immediate Backlog)
Claude Code should focus on implementing the following scoped but unwritten features:

1.  **Zero-Login Favorites:** * A `SavedStopsContext` using `localStorage` to persist user-selected stations.
    * Implementation of the "Pinned Stations" carousel on the Home screen.
2.  **Commuter Utility Tools:**
    * **"Last Train" Countdown:** A high-visibility alert for the final runs of the night.
    * **Walking Speed Toggle:** A setting to adjust arrival time estimates based on walking pace (Slow/Standard/Brisk).
3.  **Refined Navigation:**
    * Transitioning to the layout in "Design #2" which prioritizes immediate access to saved routes and nearby arrivals.

## 5. Technical Context for Claude Code
* **Backend Coordination:** When adding features (like consolidated favorites), ensure the Railway backend is utilized to aggregate data and keep the frontend lightweight.
* **PWA Standards:** Maintain high performance and offline-ready capabilities for the "Home Screen" experience.

***

### Suggested First Prompt for Claude Code:
> "I have a functional CTA PWA with a Vercel frontend and Railway backend. I am moving the UI toward the 'Heritage Organic' aesthetic (cream/charcoal) and need to implement the 'Favorites' feature. Please build a React context to manage saved Stop IDs in localStorage and create a 'Pinned Stations' component for the Home view that follows the new design language."