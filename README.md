# daness-v2

A Swiss tournament management tool for StartGG, designed for Microspacing Vancouver's format (5 rounds of Swiss → Main/Redemption brackets).

This is V2 of the [original Daness controller](https://github.com/Tonychen0227/SmashExplorer/blob/640db23f07a647e9cbcfa3b1595c50680421cd80/SmashExplorerWeb/SmashExplorerWeb/Controllers/DanessController.cs).

## Why This Tool?

StartGG's default Swiss implementation has limitations:
- Random pairings within score groups (e.g., seed #1 vs #2 in round 2)
- Can't properly calculate final standings when Swiss feeds into multiple brackets
- Manual pairing adjustments are tedious and error-prone

## Features

- **Proper Swiss pairings**: Uses traditional Swiss system with rematch avoidance and weekly variance to prevent repetitive matchups
- **Points-based bracket seeding**: Custom scoring system with Cinderella run bonuses
- **Automated final standings**: Correctly ranks players across Main/Redemption brackets
- **Stream match recommendations**: Prioritizes high-stakes matches and compelling storylines over seed numbers
- **Balanced bracket paths**: Ensures fair matchups in both brackets with rematch avoidance

## Setup

1. Clone the repository and set up Python environment:
   ```bash
   git clone https://github.com/danbugs/daness
   cd daness
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Set your StartGG API token:
   ```bash
   # Option 1: Environment variable
   export STARTGG_TOKEN="your_token_here"
   
   # Option 2: Create a .env file
   echo "STARTGG_TOKEN=your_token_here" > .env
   ```

3. Create your tournament structure in StartGG (see [Microspacing Vancouver 103](https://www.start.gg/tournament/microspacing-vancouver-103/events) as reference):
   - 5 Swiss phases (Round 1-5)
   - Main Bracket phase
   - Redemption Bracket phase
   - Final Standings phase (custom schedule)

## Usage

### Running Swiss Rounds
```bash
# Auto-detect next unstarted round
python3 daness-v2.py <event-slug>

# Specify a specific round
python3 daness-v2.py <event-slug> 3
```

### After Swiss Completion
```bash
# Generate bracket seeding (shows who goes to Main vs Redemption)
python3 daness-v2.py <event-slug> bracket
```
Then in StartGG:
1. Add players to Main/Redemption brackets using "Bracket Setup"
2. Manually seed each bracket according to the tool's output

### After Brackets Complete
```bash
# Calculate and update final standings
python3 daness-v2.py <event-slug> standings
```
This updates the Final Standings phase with correct overall placements. Then finalize the standings in StartGG. Don't forget to manually add everybody to the Final Standings phase first!

## Example Workflow

1. Before Round 1: Seed players in StartGG as normal
2. Before Rounds 2-5: `python3 daness-v2.py tournament/example/event/singles`
3. After Round 5: `python3 daness-v2.py tournament/example/event/singles bracket`
4. Add and seed players to brackets as indicated
5. After brackets finish: `python3 daness-v2.py tournament/example/event/singles standings`
6. Finalize the Final Standings phase in StartGG

## Notes

- Initial seeding is saved to a file (e.g., `tournament-example-event-singles-seeding.txt`)
- The tool prevents rematches when possible (verifies after each round)
- Special handling for the crucial 2-2 matches in round 5 (bracket qualification)
- Swiss pairings include controlled variance to prevent week-to-week repetition
- Stream recommendations de-prioritize top seeds in favor of dramatic storylines
- Requires all phases to be created in StartGG before running