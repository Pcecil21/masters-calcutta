## 2026-04-08 — Initial build & rules integration
- **Decision**: Cloned repo, installed deps, got full stack running (FastAPI :8000, Vite :3000)
- **Context**: 2026 Masters Calcutta auction is tomorrow night (April 8, 6:30 PM, Olympic Hills)
- **Rationale**: Need working auction tool ready for live use
- **Open items**: UI polish, mobile responsiveness, draft order tracking

## 2026-04-08 — Payout structure & bonuses
- **Decision**: Updated payout to 40/18/12/9/6/5/3/3/2/1 with $6,200 in fixed bonuses (round leaders, low rounds, last place Sunday)
- **Context**: Matched exact rules from the Olympic Hills rules sheet photo
- **Rationale**: System must reflect actual rules for accurate EV calculations
- **Open items**: None — implemented end-to-end (backend EV calc, schema, frontend config)

## 2026-04-08 — Pure EV bidding (no bankroll cap)
- **Decision**: Removed bankroll concentration caps from max bid logic. Max bid = 85% of breakeven EV with phase adjustment only.
- **Context**: User preferred aggressive pure-EV approach over conservative Kelly sizing
- **Rationale**: In a Calcutta, unspent bankroll is wasted — better to deploy capital on +EV opportunities
- **Open items**: None

## 2026-04-08 — Pool $50k, bankroll $12k defaults
- **Decision**: Set default pool to $50k (+/- $7k) and bankroll to $12k (+/- $3k)
- **Context**: User's estimate based on prior years
- **Rationale**: Calibrates all EV calculations and max bids to realistic scale
- **Open items**: Final numbers confirmed night-of
