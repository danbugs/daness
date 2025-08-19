# daness_v2

A Swiss tournament management tool for StartGG, designed for Microspacing Vancouver's format.

**Now supports both formats:**
- **Swiss + Brackets**: 5 rounds of Swiss → Main/Redemption brackets (original format)
- **Swiss Only**: 5 rounds of Swiss → Final standings (simplified format)

This is V2 of the [original Daness controller](https://github.com/Tonychen0227/SmashExplorer/blob/640db23f07a647e9cbcfa3b1595c50680421cd80/SmashExplorerWeb/SmashExplorerWeb/Controllers/DanessController.cs).

## Why This Tool?

StartGG's default Swiss implementation has limitations:
- Random pairings within score groups (e.g., seed #1 vs #2 in round 2)
- Can't properly calculate final standings based on performance metrics
- Manual pairing adjustments are tedious and error-prone

## Features

- **Proper Swiss pairings**: Uses traditional Swiss system with improved rematch avoidance and weekly variance to prevent repetitive matchups
- **Points-based final seeding**: Custom scoring system with Cinderella run bonuses for overperforming players
- **Automated final standings**: Works with both Swiss-only and Swiss+brackets formats
- **Stream match recommendations**: Prioritizes high-stakes matches and compelling storylines over seed numbers
- **Flexible tournament formats**: Supports tournaments with or without bracket phases

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

3. Create your tournament structure in StartGG:

   **For Swiss-only format:**
   - 5 Swiss phases (Round 1-5)
   - Final Standings phase (custom schedule)

   **For Swiss + Brackets format:**
   - 5 Swiss phases (Round 1-5)
   - Main Bracket phase
   - Redemption Bracket phase
   - Final Standings phase (custom schedule)

## Usage

### Running Swiss Rounds
```bash
# Auto-detect next unstarted round
python3 daness_v2.py <event-slug>

# Specify a specific round
python3 daness_v2.py <event-slug> 3
```

### After Swiss Completion

**For Swiss-only tournaments:**
```bash
# Calculate and update final standings
python3 daness_v2.py <event-slug> standings
```
This updates the Final Standings phase with player rankings based on:
- Win/loss record
- Quality of wins/losses
- Cinderella bonuses for overperforming seeds
- Initial seeding as tiebreaker

**For Swiss + Brackets tournaments:**
```bash
# Generate bracket seeding (shows who goes to Main vs Redemption)
python3 daness_v2.py <event-slug> bracket
```
Then in StartGG:
1. Add players to Main/Redemption brackets using "Bracket Setup"
2. Manually seed each bracket according to the tool's output

After brackets complete:
```bash
# Calculate and update final standings
python3 daness_v2.py <event-slug> standings
```

## Example Workflows

### Swiss-Only Tournament
1. Before Round 1: Seed players in StartGG as normal
2. Before Rounds 2-5: `python3 daness_v2.py tournament/example/event/singles`
3. After Round 5: `python3 daness_v2.py tournament/example/event/singles standings`
4. Finalize the Final Standings phase in StartGG

### Swiss + Brackets Tournament
1. Before Round 1: Seed players in StartGG as normal
2. Before Rounds 2-5: `python3 daness_v2.py tournament/example/event/singles`
3. After Round 5: `python3 daness_v2.py tournament/example/event/singles bracket`
4. Add and seed players to brackets as indicated
5. After brackets finish: `python3 daness_v2.py tournament/example/event/singles standings`
6. Finalize the Final Standings phase in StartGG

## Analyzing Player Pairings

To understand why a player was paired with specific opponents:
```bash
python3 daness_v2.py <event-slug> why <player-name>
```
This shows:
- Complete match history
- Points breakdown for standings
- Cinderella bonus calculations
- Bracket placement reasoning (if applicable)

## Notes

- Initial seeding is saved to a file (e.g., `tournament-example-event-singles-seeding.txt`)
- The tool uses an improved backtracking algorithm to prevent rematches
- Special handling for the crucial 2-2 matches in round 5 (when using brackets)
- Swiss pairings include controlled variance to prevent week-to-week repetition
- Stream recommendations de-prioritize top seeds in favor of dramatic storylines
- Requires all phases to be created in StartGG before running
- Points-based system rewards quality wins and penalizes bad losses
- Cinderella bonuses scale based on seed (higher bonus for lower seeds overperforming)

## Mock Tournament Generator

- Creates fake players with seeds 1-32
- Simulates match outcomes with configurable upset rates
- Maintains tournament state through rounds

### Test Scenarios

- `test_no_rematches_standard()`
   - Runs a full 5-round Swiss
   - Verifies no rematches occur

- `test_high_upset_tournament()`
   - Tests with 40% upset rate
   - Verifies Cinderella bonus calculations work correctly

- `test_round_5_critical_matches()`
   - Specifically tests the 2-2 group pairing logic
   - Ensures fair seed matchups for bracket qualification

- `test_constraint_satisfaction()`
   - Creates difficult pairing scenarios
   - Tests the rematch avoidance algorithm under stress

- `test_bracket_seeding_fairness()`
   - Verifies top 16 make main bracket
   - Checks that seeding rewards performance properly

- `test_edge_cases()`
   - Extreme upset scenarios
   - Other boundary conditions

### Usage
```bash
python3 test_daness_v2.py
```

### Adding New Tests

To add a new test:
```python
def test_my_scenario(self):
    """Test description"""
    tournament = MockTournament(32, seed=12345)
    
    # Your test logic here
    
    return True  # or False if test fails
```

Then add to `run_all_tests()`:
```python
self.run_test("My Scenario", self.test_my_scenario)
```

This framework lets you:
- Test edge cases without real tournaments
- Reproduce bugs with specific seeds
- Verify fixes don't break existing functionality
- Ensure fairness in pairings and rankings

You can also create specific tournament scenarios by manipulating the match results directly to test particular situations (like everyone at 2-2 going into round 5).