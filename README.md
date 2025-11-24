# daness_v2

Swiss tournament automation for StartGG. Supports variable player counts. Made for Microspacing Vancouver.

This is V2 of the [original Daness controller](https://github.com/Tonychen0227/SmashExplorer/blob/640db23f07a647e9cbcfa3b1595c50680421cd80/SmashExplorerWeb/SmashExplorerWeb/Controllers/DanessController.cs).

## Quick Reference

### Pairing Algorithm

**Round 1:** Seed-based (seed 1 vs seed N/2+1, seed 2 vs N/2+2, etc.)

**Round 2+:** 
1. Group players by W-L record
2. Apply date-based randomness (seed: YYYYMMDD) for weekly variance
3. Within groups: pair by seed ± small random offset
4. Backtracking ensures zero rematches
5. Quality checks prevent close-seed matchups in early rounds (1v2, 2v3, etc.)
6. Power-of-2: strict within-group pairing
7. Non-power-of-2: allows cross-group pairing when needed

**Scoring:** Points = (Wins × 100) + Base seed points + Win quality + Cinderella bonus  
**Cinderella:** Lower seeds get higher multipliers for overperformance

### Commands

```bash
# Recommend Swiss rounds for player count
python daness_v2.py <event-slug> recommend <num-players>
# Example: 28 players → 5 rounds, 16 players → 4 rounds

# Setup next unstarted round (autodetect)
python daness_v2.py <event-slug>

# Or specify a round number
python daness_v2.py <event-slug> <round-number>

# Calculate Swiss final standings
python daness_v2.py <event-slug> standings

# Generate bracket split (after all Swiss rounds)
python daness_v2.py <event-slug> bracket
# Splits 50/50: 32→16/16, 28→14/14, 24→12/12

# Analyze player pairings
python daness_v2.py <event-slug> why <player-name>
```

## Setup

```bash
git clone https://github.com/danbugs/daness
cd daness
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set API token
export STARTGG_TOKEN="your_token_here"
# Or create .env file: echo "STARTGG_TOKEN=your_token" > .env
```

## StartGG Structure

**Swiss + Brackets:**
- Swiss phases (Round 1-N, where N = recommended rounds)
- Main Bracket phase
- Redemption Bracket phase  
- Final Standings phase (custom schedule)

**Swiss Only:**
- Swiss phases (Round 1-N)
- Final Standings phase (custom schedule)

## Tournament Flow

1. Seed players in Round 1 phase manually
2. `python daness_v2.py <slug> recommend <count>` - get recommended rounds
3. `python daness_v2.py <slug> 1` - setup Round 1 pairings
4. Start Round 1 in StartGG, complete matches
5. `python daness_v2.py <slug> 2` - setup Round 2 (uses results from R1)
6. Repeat for rounds 3-5
7. `python daness_v2.py <slug> bracket` - generate bracket seeding
8. Manually seed bracket phases with displayed seeding
9. Run brackets
10. `python daness_v2.py <slug> standings` - update Final Standings phase

## Features

- **Zero rematches:** Backtracking algorithm guarantees no repeat pairings
- **Weekly variance:** Date-based randomness varies pairings week-to-week
- **Smart pairing:** Prevents close-seed matchups in early rounds (heavy penalty for adjacent seeds)
- **Cinderella bonuses:** Lower seeds get higher rewards for overperformance
- **Stream recommendations:** Identifies compelling matchups by storyline
- **Variable player counts:** Works with 32, 28, 24, or any count

## Notes

- Tool never modifies match results, only seeding order
- Pairing randomness is deterministic per day (same date = same pairings)
- Cross-group pairing noted in output for non-power-of-2 tournaments
- Bracket split always 50/50, main bracket gets extra on odd counts
- Initial seeding saved to file (e.g., `tournament-example-event-singles-seeding.txt`)
- Points system rewards quality wins and penalizes bad losses
- Cinderella bonuses scale based on seed percentile

## Testing

```bash
python test_daness_v2.py
```

Tests include: 32/28/24/20 players, date variance, odd counts, rematch avoidance, bracket fairness.
