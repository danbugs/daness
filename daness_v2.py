#!/usr/bin/env python3
import requests
import json
import sys
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
import random

load_dotenv()

# StartGG API endpoints
API_URL_READ = "https://www.start.gg/api/-/gql"
API_URL_WRITE = "https://api.start.gg/gql/alpha"

AUTH_TOKEN = os.environ.get("STARTGG_TOKEN")
if not AUTH_TOKEN:
    print("Error: STARTGG_TOKEN environment variable not set")
    print("Please set it with: export STARTGG_TOKEN='your_token_here'")
    print("Or create a .env file with: STARTGG_TOKEN=your_token_here")
    sys.exit(1)

# State mappings
PHASE_STATES = {
    "CREATED": 1,
    "ACTIVE": 2,
    "COMPLETED": 3,
    "READY": 1,
    "NOT_STARTED": 1,
    "STARTED": 2,
    "COMPLETE": 3,
    1: 1,
    2: 2,
    3: 3,
}


def get_phase_state(state):
    """Convert phase state to numeric value"""
    if isinstance(state, int):
        return state
    return PHASE_STATES.get(state, 1)


# Simplified query to get basic phase info first
PHASES_QUERY = """
query GetPhases($slug: String!) {
  event(slug: $slug) {
    name
    phases {
      id
      name
      state
      phaseOrder
    }
  }
}
"""

# Separate query for detailed phase data
PHASE_DETAILS_QUERY = """
query GetPhaseDetails($phaseId: ID!) {
  phase(id: $phaseId) {
    id
    name
    phaseGroups {
      nodes {
        id
        displayIdentifier
        seeds(query: {perPage: 100}) {
          nodes {
            id
            seedNum
            placement
            entrant {
              id
              name
              participants {
                gamerTag
              }
            }
          }
        }
        standings(query: {perPage: 100}) {
          nodes {
            placement
            entrant {
              id
              name
              participants {
                gamerTag
              }
            }
          }
        }
        sets(perPage: 200) {
          nodes {
            id
            round
            winnerId
            completedAt
            state
            slots {
              seed {
                seedNum
              }
              entrant {
                id
                name
                participants {
                  gamerTag
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def make_request(query, variables, is_mutation=False):
    """Make a GraphQL request to StartGG API"""
    url = API_URL_WRITE if is_mutation else API_URL_READ

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }

    if not is_mutation:
        headers["Client-Version"] = "20"
        headers["User-Agent"] = "Python/daness-script"

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=30,
        )

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        return response.json()

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
        return None
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None


def save_initial_seeding(event_slug, seeds):
    """Save initial seeding to file"""
    filename = f"{event_slug.replace('/', '-')}-seeding.txt"

    if os.path.exists(filename):
        print(f"Initial seeding file {filename} already exists - using existing file")
        return filename

    with open(filename, "w") as f:
        for seed in sorted(seeds, key=lambda x: x["seedNum"]):
            gamer_tag = seed["entrant"]["participants"][0]["gamerTag"]
            f.write(f"{seed['seedNum']}: {gamer_tag}\n")
    print(f"Initial seeding saved to {filename}")
    return filename


def load_initial_seeding(filename):
    """Load initial seeding from file"""
    seeding = {}
    with open(filename, "r") as f:
        for line in f:
            seed_num, gamer_tag = line.strip().split(": ", 1)
            seeding[gamer_tag] = int(seed_num)
    return seeding


def get_match_results_from_phases(phases, swiss_only=False):
    """Extract all match results from completed phases"""
    all_results = []

    for phase in phases:
        phase_state = get_phase_state(phase["state"])
        phase_name_lower = phase["name"].lower()

        # Skip non-Swiss phases if swiss_only is True
        if swiss_only:
            if "bracket" in phase_name_lower or "final" in phase_name_lower:
                continue
            # Only include Swiss rounds 1-5
            if not any(f"round {i}" in phase_name_lower for i in range(1, 6)):
                continue

        if phase_state == 3:  # COMPLETED state
            phase_name = phase["name"]
            round_num = extract_round_number(phase_name)

            # Additional check for Swiss only
            if swiss_only and round_num > 5:
                continue

            for group in phase["phaseGroups"]["nodes"]:
                for set_data in group["sets"]["nodes"]:
                    set_state = get_phase_state(set_data["state"])
                    if set_state == 3 and set_data["winnerId"]:  # Completed
                        winner_id = set_data["winnerId"]

                        match_result = {
                            "round": round_num,
                            "winner_id": winner_id,
                            "players": [],
                            "phase_name": phase["name"],  # Add phase name for debugging
                        }

                        for slot in set_data["slots"]:
                            if slot["entrant"]:
                                match_result["players"].append(
                                    {
                                        "id": slot["entrant"]["id"],
                                        "name": slot["entrant"]["participants"][0][
                                            "gamerTag"
                                        ],
                                    }
                                )

                        all_results.append(match_result)

    return all_results


def extract_round_number(phase_name):
    """Extract round number from phase name"""
    try:
        return int(phase_name.split()[-1])
    except:
        return 1


def calculate_standings(initial_seeding, match_results):
    """Calculate standings based on match results"""
    standings = {}

    # Initialize standings for all players
    for gamer_tag, seed in initial_seeding.items():
        standings[gamer_tag] = {
            "seed": seed,
            "wins": 0,
            "losses": 0,
            "opponents": [],
            "opponent_wins": 0,
        }

    # Process match results
    for match in match_results:
        winner_id = match["winner_id"]

        for player in match["players"]:
            player_name = player["name"]
            if player_name in standings:
                # Record opponent
                opponent_name = next(
                    (p["name"] for p in match["players"] if p["name"] != player_name),
                    None,
                )
                if opponent_name:
                    standings[player_name]["opponents"].append(opponent_name)

                # Record result
                if player["id"] == winner_id:
                    standings[player_name]["wins"] += 1
                else:
                    standings[player_name]["losses"] += 1

    # Calculate opponent wins for tiebreakers
    for player_name, info in standings.items():
        for opp_name in info["opponents"]:
            if opp_name in standings:
                info["opponent_wins"] += standings[opp_name]["wins"]

    return standings


def get_expected_wins(seed):
    """Calculate expected wins based on seed"""
    if seed <= 4:
        return 4.0 - (seed - 1) * 0.2  # Seeds 1-4: 4.0, 3.8, 3.6, 3.4
    elif seed <= 8:
        return 3.5 - (seed - 4) * 0.15  # Seeds 5-8: 3.35, 3.2, 3.05, 2.9
    elif seed <= 16:
        return 3.0 - (seed - 8) * 0.1  # Seeds 9-16: 2.9 down to 2.2
    elif seed <= 24:
        return 2.2 - (seed - 16) * 0.1  # Seeds 17-24: 2.1 down to 1.4
    else:
        return 1.4 - (seed - 24) * 0.05  # Seeds 25-32: 1.35 down to 1.0


def get_cinderella_multiplier(seed):
    """Get Cinderella bonus multiplier based on seed"""
    if seed <= 8:
        return 0.5, "minimal (top seed)"
    elif seed <= 16:
        return 1.0, "moderate (mid seed)"
    elif seed <= 24:
        return 1.5, "good (lower seed)"
    else:
        return 2.0, "maximum (bottom seed)"


def calculate_cinderella_bonus(seed, wins, standings, match_results, player_name):
    """Calculate Cinderella bonus for a player"""
    expected_wins = get_expected_wins(seed)
    wins_above_expected = wins - expected_wins
    cinderella_bonus = 0

    # Only award Cinderella bonus for significant overperformance
    if wins_above_expected > 0.5:
        multiplier, _ = get_cinderella_multiplier(seed)

        # Calculate bonus based on wins above expected
        for i in range(int(wins_above_expected)):
            base_bonus = 3 + i * 2
            cinderella_bonus += base_bonus * multiplier

        # Handle fractional part
        fractional_part = wins_above_expected - int(wins_above_expected)
        if fractional_part > 0:
            next_bonus = (3 + int(wins_above_expected) * 2) * multiplier
            cinderella_bonus += fractional_part * next_bonus

        # Special upset bonus
        upset_bonus = 0
        for opp_name in standings[player_name]["opponents"]:
            if opp_name in standings:
                opp_seed = standings[opp_name]["seed"]
                seed_diff = seed - opp_seed

                if seed_diff >= 8:
                    # Check if we actually beat them
                    for match in match_results:
                        match_players = [p["name"] for p in match["players"]]
                        if player_name in match_players and opp_name in match_players:
                            winner_id = match["winner_id"]
                            player_id = next(
                                (
                                    p["id"]
                                    for p in match["players"]
                                    if p["name"] == player_name
                                ),
                                None,
                            )
                            if player_id == winner_id:
                                if seed_diff >= 16:
                                    upset_bonus += 5
                                elif seed_diff >= 12:
                                    upset_bonus += 3
                                else:
                                    upset_bonus += 2
                                break

        cinderella_bonus += upset_bonus

    # Cap Cinderella bonus at reasonable level
    return min(cinderella_bonus, 20.0)

def calculate_swiss_pairings(standings, round_number=None):
    """Calculate Swiss pairings with improved rematch avoidance"""
    # Group players by record
    groups = defaultdict(list)
    for player_name, info in standings.items():
        record = (info["wins"], info["losses"])
        groups[record].append((player_name, info))

    # Sort groups by record (wins desc, losses asc)
    sorted_groups = sorted(
        groups.items(), key=lambda x: (x[0][0], -x[0][1]), reverse=True
    )

    print("\nPlayer groups by record:")
    for record, players in sorted_groups:
        print(f"  {record[0]}-{record[1]}: {len(players)} players")

    # Check if this is the final round (round 5)
    is_final_round = False
    if sorted_groups:
        first_group_players = list(groups.values())[0]
        if first_group_players:
            total_games_played = (
                first_group_players[0][1]["wins"] + first_group_players[0][1]["losses"]
            )
            is_final_round = total_games_played == 4

    pairings = []
    used = set()

    def can_pair(p1, p2):
        """Check if two players can be paired (haven't played before)"""
        return p2[0] not in p1[1]["opponents"] and p1[0] not in p2[1]["opponents"]

    def find_valid_pairing_for_group(players_list):
        """
        Find a valid pairing for all players in a group using backtracking.
        Returns list of pairs or None if no valid pairing exists.
        """
        if len(players_list) == 0:
            return []
        
        if len(players_list) == 1:
            # Odd player, will be handled later
            return None
            
        # For small groups, use exhaustive search
        if len(players_list) <= 8:
            return find_perfect_matching_backtrack(players_list)
        
        # For larger groups, use the optimized algorithm
        return find_perfect_matching_large_group(players_list)

    def find_perfect_matching_backtrack(players, current_matching=None, used_players=None):
        """
        Backtracking algorithm to find a perfect matching without rematches.
        """
        if current_matching is None:
            current_matching = []
        if used_players is None:
            used_players = set()
        
        # Base case: all players are paired
        if len(used_players) == len(players):
            return current_matching
        
        # Find first unpaired player
        p1 = None
        for player in players:
            if player[0] not in used_players:
                p1 = player
                break
        
        if p1 is None:
            return current_matching
        
        # Try pairing with each valid opponent
        for p2 in players:
            if p2[0] not in used_players and p1[0] != p2[0] and can_pair(p1, p2):
                # Try this pairing
                new_matching = current_matching + [(p1, p2)]
                new_used = used_players | {p1[0], p2[0]}
                
                # Recursively try to pair remaining players
                result = find_perfect_matching_backtrack(players, new_matching, new_used)
                
                if result is not None and len(result) * 2 == len(players):
                    return result
        
        # No valid pairing found with p1
        return None

    def find_perfect_matching_large_group(players):
        """
        For larger groups, use a more efficient algorithm with multiple strategies.
        """
        n = len(players)
        if n % 2 != 0:
            return None
        
        # Strategy 1: Swiss-style pairing (top half vs bottom half)
        players_sorted = sorted(players, key=lambda x: x[1]["seed"])
        half = n // 2
        
        # Try standard Swiss pairing first
        swiss_pairs = []
        used_indices = set()
        
        for i in range(half):
            if i not in used_indices:
                # Try to pair with corresponding player in other half
                j = i + half
                if j not in used_indices and can_pair(players_sorted[i], players_sorted[j]):
                    swiss_pairs.append((players_sorted[i], players_sorted[j]))
                    used_indices.add(i)
                    used_indices.add(j)
        
        if len(swiss_pairs) == half:
            return swiss_pairs
        
        # Strategy 2: Minimum weight matching based on seed difference
        # Build adjacency matrix
        valid_pairings = []
        for i in range(n):
            for j in range(i + 1, n):
                if can_pair(players[i], players[j]):
                    weight = abs(players[i][1]["seed"] - players[j][1]["seed"])
                    valid_pairings.append((i, j, weight))
        
        # Sort by weight (seed difference)
        valid_pairings.sort(key=lambda x: x[2])
        
        # Greedy matching
        matched = set()
        result_pairs = []
        
        for i, j, weight in valid_pairings:
            if i not in matched and j not in matched:
                result_pairs.append((players[i], players[j]))
                matched.add(i)
                matched.add(j)
                
                if len(result_pairs) == half:
                    return result_pairs
        
        # Strategy 3: If still no complete matching, use backtracking for remaining
        if len(result_pairs) > half - 2:  # Almost complete
            remaining = [p for i, p in enumerate(players) if i not in matched]
            if len(remaining) <= 4:
                remaining_pairs = find_perfect_matching_backtrack(remaining)
                if remaining_pairs:
                    return result_pairs + remaining_pairs
        
        return None

    def pair_within_group_swiss_style(players_in_group, record):
        """Pair players within a score group using improved algorithm"""
        available = [p for p in players_in_group if p[0] not in used]
        
        if len(available) < 2:
            return []
        
        print(f"\nPairing {record[0]}-{record[1]} group ({len(available)} players):")
        
        # Handle odd number - hold out middle player
        held_out_player = None
        if len(available) % 2 == 1:
            # Choose player with most potential opponents for cross-group pairing
            best_player = None
            best_flexibility = -1
            
            for player in available:
                flexibility = 0
                # Count valid opponents in this and adjacent groups
                for other in available:
                    if other[0] != player[0] and can_pair(player, other):
                        flexibility += 1
                
                if flexibility > best_flexibility:
                    best_flexibility = flexibility
                    best_player = player
            
            if best_player:
                held_out_player = best_player
                available.remove(held_out_player)
                print(f"    Holding {held_out_player[0]} for cross-group pairing (has {best_flexibility} valid opponents)")
        
        # Try to find a perfect matching for the group
        group_pairings = find_valid_pairing_for_group(available)
        
        if group_pairings is None:
            print(f"    ⚠️  Could not find perfect matching for group, using fallback")
            # Fallback to original algorithm
            group_pairings = []
            temp_available = available[:]
            
            while len(temp_available) >= 2:
                p1 = temp_available[0]
                best_opponent = None
                
                for p2 in temp_available[1:]:
                    if can_pair(p1, p2):
                        best_opponent = p2
                        break
                
                if best_opponent:
                    group_pairings.append((p1, best_opponent))
                    temp_available.remove(p1)
                    temp_available.remove(best_opponent)
                else:
                    # This should be very rare
                    print(f"    ⚠️  No valid opponent for {p1[0]} in group")
                    break
        else:
            print(f"    ✓ Found perfect matching for group")
        
        # Add the held out player back to unpaired list if needed
        if held_out_player:
            # Will be handled in cross-group pairing
            pass
        
        return group_pairings

    # Process each score group
    unpaired_players = []
    
    for record, players in sorted_groups:
        group_pairings = pair_within_group_swiss_style(players, record)
        
        # Mark paired players as used
        for p1, p2 in group_pairings:
            used.add(p1[0])
            used.add(p2[0])
            print(f"    ✓ {p1[0]} vs {p2[0]}")
        
        pairings.extend(group_pairings)
        
        # Collect unpaired players from this group
        for player in players:
            if player[0] not in used:
                unpaired_players.append(player)

    # Handle remaining unpaired players with cross-group pairing
    if unpaired_players:
        print(f"\nCross-group pairings for {len(unpaired_players)} remaining players:")
        
        # Sort by performance (wins - losses) and seed
        unpaired_players.sort(
            key=lambda x: (-(x[1]["wins"] - x[1]["losses"]), x[1]["seed"])
        )
        
        # Try to pair them optimally
        cross_group_pairs = find_valid_pairing_for_group(unpaired_players)
        
        if cross_group_pairs:
            for p1, p2 in cross_group_pairs:
                pairings.append((p1, p2))
                used.add(p1[0])
                used.add(p2[0])
                print(f"  ✓ {p1[0]} ({p1[1]['wins']}-{p1[1]['losses']}) vs {p2[0]} ({p2[1]['wins']}-{p2[1]['losses']})")
        else:
            # Last resort: pair any remaining players
            print("  ⚠️  Could not find valid cross-group pairings, using fallback")
            i = 0
            while i < len(unpaired_players) - 1:
                p1 = unpaired_players[i]
                p2 = unpaired_players[i + 1]
                pairings.append((p1, p2))
                used.add(p1[0])
                used.add(p2[0])
                
                if can_pair(p1, p2):
                    print(f"  ✓ {p1[0]} vs {p2[0]}")
                else:
                    print(f"  ⚠️  FORCED REMATCH: {p1[0]} vs {p2[0]}")
                
                i += 2

    # Final verification
    print(f"\nTotal pairings: {len(pairings)} (expected: {len(standings) // 2})")
    
    # Verify no rematches
    print("\n🔍 Verifying no rematches...")
    rematch_count = 0
    forced_rematches = []
    
    for (p1_name, p1_info), (p2_name, p2_info) in pairings:
        if p2_name in p1_info["opponents"] or p1_name in p2_info["opponents"]:
            rematch_count += 1
            forced_rematches.append((p1_name, p2_name))
            print(f"  ⚠️  REMATCH DETECTED: {p1_name} vs {p2_name}")
    
    if rematch_count == 0:
        print("  ✅ No rematches found - all pairings are valid!")
    else:
        print(f"  ❌ Found {rematch_count} rematch(es)")
        print("     This should only happen if mathematically unavoidable")
        print("     Check if the tournament structure allows for valid pairings")
    
    return pairings

def update_phase_seeding_for_pairings(phase_id, phase_groups, pairings):
    """Update the seeding in a phase to match our calculated pairings"""

    if not phase_groups or len(phase_groups) == 0:
        print("No phase groups found")
        return False

    phase_group = phase_groups[0]
    current_seeds = phase_group["seeds"]["nodes"]

    print(f"\nCurrent seeds in phase: {len(current_seeds)}")

    # Build mappings
    seed_id_by_name = {}
    for seed in current_seeds:
        name = seed["entrant"]["participants"][0]["gamerTag"]
        seed_id_by_name[name] = seed["id"]

    # Calculate total number of players
    total_players = len(current_seeds)
    half_players = total_players // 2

    # Create new seed mapping
    new_seed_mapping = []
    assigned_positions = set()

    print("\nAssigning new positions based on StartGG bracket structure:")

    for match_idx, ((p1_name, p1_info), (p2_name, p2_info)) in enumerate(pairings):
        p1_seed_id = seed_id_by_name.get(p1_name)
        p2_seed_id = seed_id_by_name.get(p2_name)

        if not p1_seed_id or not p2_seed_id:
            print(f"Warning: Could not find seed ID for {p1_name} or {p2_name}")
            continue

        pos1 = match_idx + 1  # Top half
        pos2 = match_idx + half_players + 1  # Bottom half

        print(
            f"  Match {match_idx + 1}: {p1_name} -> position {pos1}, {p2_name} -> position {pos2}"
        )

        new_seed_mapping.append({"seedId": p1_seed_id, "seedNum": pos1})
        new_seed_mapping.append({"seedId": p2_seed_id, "seedNum": pos2})

        assigned_positions.add(pos1)
        assigned_positions.add(pos2)

    # Handle any unpaired players
    paired_players = set()
    for (p1_name, _), (p2_name, _) in pairings:
        paired_players.add(p1_name)
        paired_players.add(p2_name)

    unpaired_players = []
    for seed in current_seeds:
        name = seed["entrant"]["participants"][0]["gamerTag"]
        if name not in paired_players:
            unpaired_players.append((name, seed["id"]))

    if unpaired_players:
        print(f"\nFound {len(unpaired_players)} unpaired players")

        all_positions = set(range(1, total_players + 1))
        available_positions = sorted(all_positions - assigned_positions)

        for i, (player_name, seed_id) in enumerate(unpaired_players):
            if i < len(available_positions):
                pos = available_positions[i]
                print(f"  {player_name} -> position {pos}")
                new_seed_mapping.append({"seedId": seed_id, "seedNum": pos})

    # Sort the seed mapping by seedNum
    new_seed_mapping.sort(key=lambda x: x["seedNum"])

    if len(new_seed_mapping) != len(current_seeds):
        print(
            f"Warning: Only assigned {len(new_seed_mapping)} out of {len(current_seeds)} players"
        )
        return False

    # Update seeding
    UPDATE_SEEDING_MUTATION = """
    mutation UpdatePhaseSeeding($phaseId: ID!, $seedMapping: [UpdatePhaseSeedInfo]!) {
        updatePhaseSeeding(phaseId: $phaseId, seedMapping: $seedMapping) {
            id
        }
    }
    """

    print(f"\nUpdating seeding for {len(new_seed_mapping)} players...")

    result = make_request(
        UPDATE_SEEDING_MUTATION,
        {"phaseId": phase_id, "seedMapping": new_seed_mapping},
        is_mutation=True,
    )

    if result and "data" in result and result["data"]["updatePhaseSeeding"]:
        print("Successfully updated phase seeding!")
        return True
    else:
        print("Failed to update phase seeding")
        if result and "errors" in result:
            print(f"Errors: {result['errors']}")
        return False


def calculate_final_standings_points_based(initial_seeding, match_results):
    """Calculate final standings using a points-based system with Cinderella run bonuses"""
    standings = calculate_standings(initial_seeding, match_results)

    # Convert to list and calculate points-based scores
    final_standings = []
    total_players = len(initial_seeding)

    for player_name, info in standings.items():
        # Base points from initial seeding
        base_points = total_players - (info["seed"] - 1)

        # Calculate quality points from wins and losses
        win_points = 0
        loss_points = 0

        for opp_name in info["opponents"]:
            if opp_name in standings:
                opp_seed = standings[opp_name]["seed"]
                opp_base_points = total_players - (opp_seed - 1)

                # Check if this was a win or loss
                for match in match_results:
                    match_players = [p["name"] for p in match["players"]]
                    if player_name in match_players and opp_name in match_players:
                        winner_id = match["winner_id"]
                        player_id = next(
                            (
                                p["id"]
                                for p in match["players"]
                                if p["name"] == player_name
                            ),
                            None,
                        )

                        if player_id == winner_id:
                            win_points += opp_base_points * 0.1
                        else:
                            loss_penalty = (total_players - opp_base_points + 1) * 0.05
                            loss_points -= loss_penalty

        # Calculate Cinderella bonus
        cinderella_bonus = calculate_cinderella_bonus(
            info["seed"], info["wins"], standings, match_results, player_name
        )

        # Total score
        total_score = (
            (info["wins"] * 100)
            + base_points
            + win_points
            + loss_points
            + cinderella_bonus
        )

        expected_wins = get_expected_wins(info["seed"])
        wins_above_expected = info["wins"] - expected_wins

        final_standings.append(
            {
                "name": player_name,
                "wins": info["wins"],
                "losses": info["losses"],
                "initial_seed": info["seed"],
                "base_points": base_points,
                "win_points": win_points,
                "loss_points": loss_points,
                "cinderella_bonus": cinderella_bonus,
                "expected_wins": expected_wins,
                "wins_above_expected": wins_above_expected,
                "total_score": total_score,
                "opponents": info["opponents"],
            }
        )

    # Sort within record groups first, then by total score
    record_groups = defaultdict(list)
    for player in final_standings:
        record = (player["wins"], player["losses"])
        record_groups[record].append(player)

    # Sort each record group by total score
    for record in record_groups:
        record_groups[record].sort(key=lambda x: (-x["total_score"], x["initial_seed"]))

    # Rebuild final standings maintaining record groups in order
    sorted_standings = []
    for record in sorted(record_groups.keys(), key=lambda x: (-x[0], x[1])):
        sorted_standings.extend(record_groups[record])

    return sorted_standings


def find_best_bracket_arrangement(players, bracket_name):
    """Find the best bracket arrangement to minimize rematches"""
    best_arrangement = players[:]
    best_rematch_count = count_bracket_rematches(best_arrangement)

    if best_rematch_count == 0:
        return best_arrangement, best_rematch_count

    print(f"\n  Initial {bracket_name} bracket has {best_rematch_count} rematch(es)")

    # Try swapping adjacent players
    for i in range(len(players) - 1):
        test_arrangement = best_arrangement[:]
        test_arrangement[i], test_arrangement[i + 1] = (
            test_arrangement[i + 1],
            test_arrangement[i],
        )

        rematch_count = count_bracket_rematches(test_arrangement)
        if rematch_count < best_rematch_count:
            best_arrangement = test_arrangement[:]
            best_rematch_count = rematch_count
            print(
                f"  Swapped positions {i+1} and {i+2} to reduce rematches to {best_rematch_count}"
            )

    # If still have rematches, try more aggressive swapping
    if best_rematch_count > 0:
        print(f"  Trying more aggressive swaps...")

        for i in range(len(players)):
            for j in range(i + 2, min(i + 5, len(players))):
                if abs(players[i]["total_score"] - players[j]["total_score"]) < 10:
                    test_arrangement = best_arrangement[:]
                    test_arrangement[i], test_arrangement[j] = (
                        test_arrangement[j],
                        test_arrangement[i],
                    )

                    rematch_count = count_bracket_rematches(test_arrangement)
                    if rematch_count < best_rematch_count:
                        best_arrangement = test_arrangement[:]
                        best_rematch_count = rematch_count
                        print(
                            f"  Swapped positions {i+1} and {j+1} to reduce rematches to {best_rematch_count}"
                        )

                        if best_rematch_count == 0:
                            break
            if best_rematch_count == 0:
                break

    return best_arrangement, best_rematch_count


def count_bracket_rematches(players):
    """Count potential first round rematches in a 16-player bracket"""
    rematches = 0
    for i in range(8):
        p1 = players[i]
        p2 = players[15 - i]

        if p2["name"] in p1["opponents"]:
            rematches += 1

    return rematches


def generate_bracket_seeding(final_standings):
    """Generate seeding for main and redemption brackets with rematch avoidance"""
    print("\n" + "=" * 60)
    print("BRACKET SEEDING GENERATION (Points-Based System)")
    print("=" * 60)

    # Group players by record for display
    record_groups = defaultdict(list)
    for player in final_standings:
        record = (player["wins"], player["losses"])
        record_groups[record].append(player)

    print("\nFinal standings by record (with point breakdown):")
    for record, players in sorted(
        record_groups.items(), key=lambda x: (-x[0][0], x[0][1])
    ):
        print(f"\n  {record[0]}-{record[1]}: {len(players)} players")
        for player in players:
            overall_rank = final_standings.index(player) + 1
            cinderella_text = ""
            if player["cinderella_bonus"] > 0:
                cinderella_text = f" + {player['cinderella_bonus']:.0f} Cinderella"

            print(
                f"    {overall_rank:2d}. {player['name']} "
                f"(seed {player['initial_seed']}, "
                f"score: {player['total_score']:.0f})"
            )

    # Determine bracket cutoff - top 16 to main, bottom 16 to redemption
    main_bracket_candidates = final_standings[:16]
    redemption_bracket_candidates = final_standings[16:]

    # Optimize bracket arrangements to minimize rematches
    print(f"\n{'OPTIMIZING BRACKET ARRANGEMENTS TO AVOID REMATCHES'}")
    print("-" * 60)

    main_bracket_players, main_rematches = find_best_bracket_arrangement(
        main_bracket_candidates, "Main"
    )
    redemption_bracket_players, redemption_rematches = find_best_bracket_arrangement(
        redemption_bracket_candidates, "Redemption"
    )

    # Display final brackets
    print(f"\n{'MAIN BRACKET (Top 16)':<40} {'REDEMPTION BRACKET (Bottom 16)'}")
    print("-" * 80)

    for i in range(16):
        main_player = main_bracket_players[i]
        redemption_player = redemption_bracket_players[i]

        main_info = f"{i+1:2d}. {main_player['name']} ({main_player['wins']}-{main_player['losses']})"
        redemption_info = f"{i+1:2d}. {redemption_player['name']} ({redemption_player['wins']}-{redemption_player['losses']})"

        print(f"{main_info:<40} {redemption_info}")

    # Show rematch analysis
    print(f"\n{'REMATCH ANALYSIS'}")
    print("-" * 50)

    def show_bracket_rematches(players, bracket_name):
        print(f"\n{bracket_name} first round matchups:")
        rematches = []

        for i in range(8):
            p1 = players[i]
            p2 = players[15 - i]

            status = "REMATCH!" if p2["name"] in p1["opponents"] else "OK"
            print(f"  Match {i+1}: {p1['name']} vs {p2['name']} - {status}")

            if p2["name"] in p1["opponents"]:
                rematches.append((i + 1, 16 - i, p1["name"], p2["name"]))

        return rematches

    main_rematches_detail = show_bracket_rematches(main_bracket_players, "MAIN BRACKET")
    redemption_rematches_detail = show_bracket_rematches(
        redemption_bracket_players, "REDEMPTION BRACKET"
    )

    total_rematches = len(main_rematches_detail) + len(redemption_rematches_detail)
    if total_rematches == 0:
        print(f"\n✅ SUCCESS: No rematches in either bracket!")
    else:
        print(f"\n⚠️  {total_rematches} total rematch(es) - may be unavoidable")

    return main_bracket_players, redemption_bracket_players


def recommend_stream_matches(pairings, standings):
    """Recommend matches for streaming based on compelling storylines"""
    print(f"\n{'STREAM MATCH RECOMMENDATIONS'}")
    print("=" * 50)

    scored_matches = []

    # Determine current round based on games played
    current_round = 1
    if pairings:
        sample_player = pairings[0][0][1]
        current_round = sample_player["wins"] + sample_player["losses"] + 1

    for i, ((p1_name, p1_info), (p2_name, p2_info)) in enumerate(pairings, 1):
        hype_score = 0
        reasons = []

        # Calculate performance vs expectation
        p1_expected_wins = 2.5 - (p1_info["seed"] - 16.5) * 0.06
        p2_expected_wins = 2.5 - (p2_info["seed"] - 16.5) * 0.06
        p1_overperformance = p1_info["wins"] - (
            p1_expected_wins * (current_round - 1) / 5
        )
        p2_overperformance = p2_info["wins"] - (
            p2_expected_wins * (current_round - 1) / 5
        )

        # Factor 1: CRITICAL MATCHES (round 5 bracket qualification)
        if current_round == 5:
            if (
                p1_info["wins"] == 2
                and p1_info["losses"] == 2
                and p2_info["wins"] == 2
                and p2_info["losses"] == 2
            ):
                hype_score += 50  # Highest priority
                reasons.append("🏆 BRACKET QUALIFICATION ON THE LINE")
            elif (p1_info["wins"] == 3 and p2_info["wins"] == 3) or (
                p1_info["wins"] == 1 and p2_info["wins"] == 1
            ):
                hype_score += 30
                reasons.append("🎯 Final round seeding implications")

        # Factor 2: Mid-tournament elimination pressure
        elif current_round >= 3:
            if p1_info["losses"] == 2 and p2_info["losses"] == 2:
                hype_score += 35
                reasons.append("💀 Elimination zone battle")
            elif (
                p1_info["wins"] == 2
                and p1_info["losses"] == 0
                and p2_info["wins"] == 2
                and p2_info["losses"] == 0
            ):
                hype_score += 30
                reasons.append("🔥 Clash of the undefeated")

        # Factor 3: Cinderella stories (lower seeds overperforming)
        cinderella_factor = 0
        if p1_info["seed"] >= 17 and p1_overperformance >= 0.5:
            cinderella_factor += 1
        if p2_info["seed"] >= 17 and p2_overperformance >= 0.5:
            cinderella_factor += 1

        if cinderella_factor == 2:
            hype_score += 25
            reasons.append("✨ Battle of the Cinderellas")
        elif cinderella_factor == 1:
            hype_score += 15
            reasons.append("🌟 Cinderella story")

        # Factor 4: Mid-tier mayhem (seeds 9-24 competing for bracket spots)
        if 9 <= p1_info["seed"] <= 24 and 9 <= p2_info["seed"] <= 24:
            # These players are fighting for main bracket spots
            hype_score += 15
            reasons.append("⚔️ Mid-tier bracket battle")

        # Factor 5: David vs Goliath matches
        seed_diff = abs(p1_info["seed"] - p2_info["seed"])
        if seed_diff >= 12:
            lower_seed = p1_info if p1_info["seed"] > p2_info["seed"] else p2_info
            higher_seed = p2_info if p1_info["seed"] > p2_info["seed"] else p1_info

            # Big seed difference matches are inherently interesting
            hype_score += 15
            reasons.append("👑 David vs Goliath")

            # Extra points if the lower seed is overperforming expectations
            if lower_seed == p1_info and p1_overperformance >= 0.5:
                hype_score += 5
                reasons.append("🌟 Underdog overperforming")
            elif lower_seed == p2_info and p2_overperformance >= 0.5:
                hype_score += 5
                reasons.append("🌟 Underdog overperforming")

        # Factor 6: Momentum clashes
        if p1_info["wins"] >= 2 and p2_info["wins"] >= 2 and current_round >= 3:
            hype_score += 10
            reasons.append("🚀 High momentum clash")

        # Factor 7: Redemption stories (good players bouncing back)
        if (p1_info["seed"] <= 12 and p1_info["losses"] >= 2) or (
            p2_info["seed"] <= 12 and p2_info["losses"] >= 2
        ):
            hype_score += 8
            reasons.append("💪 Redemption opportunity")

        # PENALTY for top seeds in early rounds (they'll get stream time in brackets)
        if current_round <= 3 and (p1_info["seed"] <= 4 or p2_info["seed"] <= 4):
            hype_score -= 10
            # Don't add this as a reason, just silently deprioritize

        scored_matches.append(
            {
                "match_num": i,
                "players": (p1_name, p2_name),
                "records": (
                    f"{p1_info['wins']}-{p1_info['losses']}",
                    f"{p2_info['wins']}-{p2_info['losses']}",
                ),
                "seeds": (p1_info["seed"], p2_info["seed"]),
                "hype_score": max(0, hype_score),  # Don't go negative
                "reasons": reasons,
                "round": current_round,
            }
        )

    # Sort by hype score
    scored_matches.sort(key=lambda x: x["hype_score"], reverse=True)

    print(f"\nRound {current_round} - Top 5 most compelling matches:")
    for i, match in enumerate(scored_matches[:5], 1):
        p1_name, p2_name = match["players"]
        p1_record, p2_record = match["records"]
        p1_seed, p2_seed = match["seeds"]

        print(f"\n{i}. Match {match['match_num']}: {p1_name} vs {p2_name}")
        print(f"   Records: {p1_record} vs {p2_record}")
        print(f"   Seeds: #{p1_seed} vs #{p2_seed}")
        print(f"   Hype Score: {match['hype_score']}")
        if match["reasons"]:
            print(f"   Storylines: {', '.join(match['reasons'])}")


def get_bracket_standings(bracket_phase):
    """Get final standings/placements from a bracket phase"""
    standings = {}

    # Check standings first
    for group in bracket_phase.get("phaseGroups", {}).get("nodes", []):
        if "standings" in group and group["standings"]["nodes"]:
            for standing in group["standings"]["nodes"]:
                if standing["entrant"] and standing["entrant"]["participants"]:
                    player_name = standing["entrant"]["participants"][0]["gamerTag"]
                    placement = standing["placement"]
                    standings[player_name] = placement

    # If no standings, check seed placements
    if not standings:
        for group in bracket_phase.get("phaseGroups", {}).get("nodes", []):
            for seed in group.get("seeds", {}).get("nodes", []):
                if (
                    seed.get("placement")
                    and seed["entrant"]
                    and seed["entrant"]["participants"]
                ):
                    player_name = seed["entrant"]["participants"][0]["gamerTag"]
                    placement = seed["placement"]
                    standings[player_name] = placement

    return standings


def get_bracket_results(bracket_phase):
    """Extract bracket results from a completed bracket phase"""
    if get_phase_state(bracket_phase["state"]) != 3:
        print(f"⚠️  {bracket_phase['name']} is not completed yet")
        return {}

    bracket_results = {}
    match_count = {}  # Track how many times we've seen each match

    for group in bracket_phase["phaseGroups"]["nodes"]:
        for set_data in group["sets"]["nodes"]:
            if get_phase_state(set_data["state"]) == 3 and set_data.get("winnerId"):
                # Create a unique match key to avoid counting the same match multiple times
                player_ids = []
                for slot in set_data["slots"]:
                    if slot["entrant"]:
                        player_ids.append(slot["entrant"]["id"])

                if len(player_ids) == 2:
                    match_key = tuple(sorted(player_ids))

                    # Skip if we've already processed this match
                    if match_key in match_count:
                        continue
                    match_count[match_key] = 1

                    # Process the match
                    for slot in set_data["slots"]:
                        if slot["entrant"]:
                            player_name = slot["entrant"]["participants"][0]["gamerTag"]
                            player_id = slot["entrant"]["id"]

                            if player_name not in bracket_results:
                                bracket_results[player_name] = {
                                    "wins": 0,
                                    "losses": 0,
                                    "final_round": 0,
                                    "eliminated_by": None,
                                }

                            if player_id == set_data["winnerId"]:
                                bracket_results[player_name]["wins"] += 1
                                bracket_results[player_name]["final_round"] = max(
                                    bracket_results[player_name]["final_round"],
                                    set_data.get("round", 0),
                                )
                            else:
                                bracket_results[player_name]["losses"] += 1
                                # Find who eliminated them
                                for other_slot in set_data["slots"]:
                                    if (
                                        other_slot["entrant"]
                                        and other_slot["entrant"]["id"]
                                        == set_data["winnerId"]
                                    ):
                                        bracket_results[player_name][
                                            "eliminated_by"
                                        ] = other_slot["entrant"]["participants"][0][
                                            "gamerTag"
                                        ]
                                        break

    return bracket_results


def calculate_swiss_only_tournament_standings(initial_seeding, match_results):
    """Calculate final tournament standings based only on Swiss rounds"""
    print("\n" + "=" * 60)
    print("FINAL TOURNAMENT STANDINGS (Swiss Only)")
    print("=" * 60)

    # Get Swiss-only match results (rounds 1-5 ONLY)
    swiss_match_results = [m for m in match_results if m["round"] <= 5]
    swiss_standings = calculate_standings(initial_seeding, swiss_match_results)

    # Calculate points-based standings
    final_standings_points = calculate_final_standings_points_based(
        initial_seeding, swiss_match_results
    )

    # Build final standings list
    final_standings = []

    for rank, player_data in enumerate(final_standings_points, 1):
        player_name = player_data["name"]
        swiss_data = swiss_standings.get(
            player_name, {"wins": 0, "losses": 0, "seed": 999}
        )

        player_info = {
            "name": player_name,
            "initial_seed": swiss_data["seed"],
            "swiss_wins": swiss_data["wins"],
            "swiss_losses": swiss_data["losses"],
            "total_wins": swiss_data["wins"],
            "total_losses": swiss_data["losses"],
            "final_placement": rank,
            "total_score": player_data["total_score"],
            "base_points": player_data["base_points"],
            "win_points": player_data["win_points"],
            "loss_points": player_data["loss_points"],
            "cinderella_bonus": player_data["cinderella_bonus"],
            "expected_wins": player_data["expected_wins"],
            "wins_above_expected": player_data["wins_above_expected"],
        }

        final_standings.append(player_info)

    # Display final standings with detailed breakdown
    print(
        f"\n{'Rank':<5} {'Player':<15} {'Record':<8} {'Seed':<6} {'Score':<8} {'Breakdown'}"
    )
    print("-" * 80)

    for player in final_standings:
        record = f"{player['swiss_wins']}-{player['swiss_losses']}"

        # Create breakdown string
        breakdown_parts = []
        breakdown_parts.append(f"Base: {player['base_points']:.0f}")

        if player["win_points"] > 0:
            breakdown_parts.append(f"Win: +{player['win_points']:.0f}")

        if player["loss_points"] < 0:
            breakdown_parts.append(f"Loss: {player['loss_points']:.0f}")

        if player["cinderella_bonus"] > 0:
            breakdown_parts.append(f"Cind: +{player['cinderella_bonus']:.0f}")

        breakdown = " | ".join(breakdown_parts)

        print(
            f"{player['final_placement']:<5} {player['name']:<15} {record:<8} "
            f"#{player['initial_seed']:<5} {player['total_score']:<8.0f} {breakdown}"
        )

    # Show record groups summary
    print(f"\n{'RECORD GROUPS SUMMARY'}")
    print("-" * 40)

    record_groups = defaultdict(list)
    for player in final_standings:
        record = (player["swiss_wins"], player["swiss_losses"])
        record_groups[record].append(player)

    for record in sorted(record_groups.keys(), key=lambda x: (-x[0], x[1])):
        players_in_group = record_groups[record]
        print(f"\n{record[0]}-{record[1]}: {len(players_in_group)} players")

        # Show top performers in each group
        for player in players_in_group[:3]:  # Show top 3 in each group
            if player["wins_above_expected"] > 0.5:
                perf_indicator = (
                    f" (↑ {player['wins_above_expected']:.1f} above expected)"
                )
            elif player["wins_above_expected"] < -0.5:
                perf_indicator = (
                    f" (↓ {abs(player['wins_above_expected']):.1f} below expected)"
                )
            else:
                perf_indicator = " (performing as expected)"

            print(
                f"  #{player['final_placement']:2d}. {player['name']} "
                f"(seed #{player['initial_seed']}){perf_indicator}"
            )

        if len(players_in_group) > 3:
            print(f"  ... and {len(players_in_group) - 3} more")

    return final_standings


def update_final_standings_phase(phases, final_tournament_standings, initial_seeding):
    """Update Final Standings phase using swapSeeds mutations"""

    # Find the Final Standings phase
    final_standings_phase = None
    for phase in phases:
        if phase["name"].lower() == "final standings":
            final_standings_phase = phase
            break

    if not final_standings_phase:
        print("❌ Could not find 'Final Standings' phase")
        return False

    print(f"\nFound 'Final Standings' phase: {final_standings_phase['name']}")
    print("Updating phase seeding...")

    # Get current state query
    CURRENT_STATE_QUERY = """
    query GetCurrentState($phaseId: ID!) {
        phase(id: $phaseId) {
            phaseGroups {
                nodes {
                    seeds(query: {perPage: 100}) {
                        nodes {
                            id
                            seedNum
                            entrant {
                                participants {
                                    gamerTag
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    SWAP_MUTATION = """
    mutation SwapSeeds($phaseId: ID!, $seed1Id: ID!, $seed2Id: ID!) {
        swapSeeds(phaseId: $phaseId, seed1Id: $seed1Id, seed2Id: $seed2Id) {
            id
        }
    }
    """

    def get_current_positions():
        current_data = make_request(
            CURRENT_STATE_QUERY, {"phaseId": final_standings_phase["id"]}
        )
        if not (current_data and "data" in current_data):
            return None

        seeds = current_data["data"]["phase"]["phaseGroups"]["nodes"][0]["seeds"][
            "nodes"
        ]
        position_to_player = {}
        player_to_seed = {}

        for seed in seeds:
            if seed["entrant"] and seed["entrant"]["participants"]:
                gamer_tag = seed["entrant"]["participants"][0]["gamerTag"]
                position = seed["seedNum"]
                seed_id = seed["id"]

                position_to_player[position] = gamer_tag
                player_to_seed[gamer_tag] = {"position": position, "seed_id": seed_id}

        return position_to_player, player_to_seed

    # Get initial state
    position_to_player, player_to_seed = get_current_positions()
    if not position_to_player:
        print("❌ Could not get current positions")
        return False

    print(f"\nTarget final standings (top 10):")
    for i, player_data in enumerate(final_tournament_standings[:10], 1):
        print(f"  Position {i}: {player_data['name']}")

    # Execute swaps
    print(f"\nExecuting swaps to achieve final standings...")
    swap_count = 0
    max_swaps = 100

    while swap_count < max_swaps:
        position_to_player, player_to_seed = get_current_positions()
        swap_needed = False

        for target_pos, target_player in enumerate(final_tournament_standings, 1):
            current_player_at_pos = position_to_player.get(target_pos)
            target_player_name = target_player["name"]

            if current_player_at_pos != target_player_name:
                current_pos_of_target = player_to_seed[target_player_name]["position"]

                if current_pos_of_target != target_pos:
                    player1_seed_id = player_to_seed[target_player_name]["seed_id"]
                    player2_seed_id = player_to_seed[current_player_at_pos]["seed_id"]

                    print(
                        f"  Swap {swap_count + 1}: {target_player_name} (pos {current_pos_of_target}) ↔ {current_player_at_pos} (pos {target_pos})"
                    )

                    result = make_request(
                        SWAP_MUTATION,
                        {
                            "phaseId": final_standings_phase["id"],
                            "seed1Id": player1_seed_id,
                            "seed2Id": player2_seed_id,
                        },
                        is_mutation=True,
                    )

                    if result and "data" in result and result["data"]["swapSeeds"]:
                        swap_count += 1
                        swap_needed = True
                        break
                    else:
                        print(f"    ❌ Swap failed")
                        return False

        if not swap_needed:
            print("✅ All players in correct positions!")
            break

    if swap_count >= max_swaps:
        print(f"⚠️  Reached maximum swap limit ({max_swaps})")
        return False

    # Verify final result
    print(f"\n🔍 Verification after {swap_count} swaps:")
    position_to_player, player_to_seed = get_current_positions()

    all_correct = True
    for target_pos, player_data in enumerate(final_tournament_standings[:10], 1):
        current_player = position_to_player.get(target_pos, "NOT FOUND")
        expected_player = player_data["name"]

        if current_player == expected_player:
            status = "✅"
        else:
            status = "❌"
            all_correct = False

        print(
            f"  {status} Position {target_pos}: expected {expected_player}, got {current_player}"
        )

    if all_correct:
        print(
            f"\n🎉 SUCCESS! Final standings correctly arranged using {swap_count} swaps!"
        )
        return True
    else:
        print(f"\n⚠️  Some positions still incorrect after {swap_count} swaps")
        return False


def analyze_player_pairings(player_name, initial_seeding, detailed_phases):
    """Analyze why a specific player was paired with their opponents"""
    print(f"\n{'='*60}")
    print(f"PAIRING ANALYSIS FOR: {player_name}")
    print(f"{'='*60}")

    # Find player's initial seed
    player_seed = initial_seeding.get(player_name)
    if not player_seed:
        print(f"❌ Player '{player_name}' not found in initial seeding")
        return

    print(f"\nInitial seed: #{player_seed}")

    # Separate Swiss and bracket matches
    swiss_matches = []
    bracket_matches = []

    # Track which phase each match came from
    for phase in detailed_phases:
        if get_phase_state(phase["state"]) != 3:  # Only completed phases
            continue

        phase_name = phase["name"].lower()
        is_swiss = "round" in phase_name and any(
            str(i) in phase_name for i in range(1, 6)
        )
        is_bracket = "bracket" in phase_name

        if not (is_swiss or is_bracket):
            continue

        # Extract round number for Swiss
        round_num = extract_round_number(phase["name"]) if is_swiss else None

        # Get matches from this phase
        for group in phase["phaseGroups"]["nodes"]:
            for set_data in group["sets"]["nodes"]:
                if get_phase_state(set_data["state"]) == 3 and set_data["winnerId"]:
                    # Check if player is in this match
                    player_in_match = False
                    opponent = None
                    won = False

                    for slot in set_data["slots"]:
                        if slot["entrant"] and slot["entrant"]["participants"]:
                            name = slot["entrant"]["participants"][0]["gamerTag"]
                            if name == player_name:
                                player_in_match = True
                                won = slot["entrant"]["id"] == set_data["winnerId"]

                    if player_in_match:
                        # Find opponent
                        for slot in set_data["slots"]:
                            if slot["entrant"] and slot["entrant"]["participants"]:
                                name = slot["entrant"]["participants"][0]["gamerTag"]
                                if name != player_name:
                                    opponent = name
                                    break

                        if opponent:
                            match_info = {
                                "opponent": opponent,
                                "won": won,
                                "opponent_seed": initial_seeding.get(opponent, 0),
                                "phase": phase["name"],
                            }

                            if is_swiss:
                                match_info["round"] = round_num
                                swiss_matches.append(match_info)
                            else:
                                match_info["bracket_round"] = set_data.get("round", 0)
                                bracket_matches.append(match_info)

    # Sort Swiss matches by round
    swiss_matches.sort(key=lambda x: x["round"])

    # Display Swiss match history
    print(f"\n{'SWISS ROUNDS (1-5)'}")
    print(f"{'Round':<8} {'Opponent':<20} {'Seed':<6} {'Result':<8} {'Record'}")
    print("-" * 60)

    swiss_wins = 0
    swiss_losses = 0
    for match in swiss_matches:
        if match["won"]:
            swiss_wins += 1
            result = "WIN ✓"
        else:
            swiss_losses += 1
            result = "LOSS ✗"

        record = f"{swiss_wins}-{swiss_losses}"
        print(
            f"Round {match['round']:<2} {match['opponent']:<20} "
            f"#{match['opponent_seed']:<4} {result:<8} {record}"
        )

    final_swiss_record = f"{swiss_wins}-{swiss_losses}"

    # Bracket seeding calculation
    print(f"\n{'BRACKET SEEDING CALCULATION'}")
    print("=" * 60)

    # Get ONLY Swiss results (rounds 1-5)
    swiss_match_results = get_match_results_from_phases(
        detailed_phases, swiss_only=True
    )
    swiss_only_results = [m for m in swiss_match_results if m["round"] <= 5]

    final_standings = calculate_final_standings_points_based(
        initial_seeding, swiss_only_results
    )

    # Find player's position
    player_standing = next(
        (p for p in final_standings if p["name"] == player_name), None
    )

    if player_standing:
        print(f"\nPOINTS BREAKDOWN:")
        print("─" * 40)

        # Base points
        print(
            f"Base Points (seed #{player_seed}): {player_standing['base_points']:.1f}"
        )

        # Win quality
        print(f"Win Quality: +{player_standing['win_points']:.1f}")

        # Loss quality
        print(f"Loss Quality: {player_standing['loss_points']:.1f}")

        # Cinderella bonus calculation with details
        expected_wins = get_expected_wins(player_seed)
        actual_wins_above = swiss_wins - expected_wins

        print(f"\nCINDERELLA BONUS CALCULATION:")
        print(f"  Expected wins for seed #{player_seed}: {expected_wins:.1f}")
        print(f"  Actual Swiss wins: {swiss_wins}")
        print(f"  Overperformance: {actual_wins_above:.1f} wins")

        if actual_wins_above > 0.5:
            multiplier, desc = get_cinderella_multiplier(player_seed)
            print(f"  Multiplier: {multiplier}x ({desc})")

            # Show any major upsets
            upset_count = 0
            for match in swiss_matches:
                if match["won"]:
                    seed_diff = player_seed - match["opponent_seed"]
                    if seed_diff >= 16:
                        print(
                            f"  🌟 HUGE upset vs {match['opponent']} (#{match['opponent_seed']})"
                        )
                        upset_count += 1
                    elif seed_diff >= 12:
                        print(
                            f"  ⭐ Big upset vs {match['opponent']} (#{match['opponent_seed']})"
                        )
                        upset_count += 1
                    elif seed_diff >= 8:
                        print(
                            f"  ✨ Upset vs {match['opponent']} (#{match['opponent_seed']})"
                        )
                        upset_count += 1

            print(
                f"  Total Cinderella Bonus: +{player_standing['cinderella_bonus']:.1f}"
            )
        else:
            print(f"  No Cinderella bonus (need >0.5 wins above expected)")

        # Win points
        print(f"\nWin Points: {swiss_wins} × 100 = {swiss_wins * 100}")

        # Total
        print(f"\n{'─' * 40}")
        print(f"TOTAL SCORE: {player_standing['total_score']:.1f}")

        overall_rank = final_standings.index(player_standing) + 1
        print(f"\nFinal Swiss Rank: #{overall_rank} of {len(final_standings)}")

        if overall_rank <= 16:
            print("→ MAIN BRACKET (Top 16)")
            bracket_seed = overall_rank
        else:
            print("→ REDEMPTION BRACKET (Bottom 16)")
            bracket_seed = overall_rank - 16

        print(f"→ Bracket seed: #{bracket_seed}")

    # Display bracket matches if any
    if bracket_matches:
        print(f"\n{'BRACKET MATCHES'}")
        print("=" * 60)

        # Determine which bracket
        bracket_type = "Unknown"
        for match in bracket_matches:
            if "main" in match["phase"].lower():
                bracket_type = "Main Bracket"
                break
            elif "redemption" in match["phase"].lower():
                bracket_type = "Redemption Bracket"
                break

        print(f"{bracket_type}:")
        print(f"{'Round':<8} {'Opponent':<20} {'Seed':<6} {'Result'}")
        print("-" * 50)

        for match in bracket_matches:
            result = "WIN ✓" if match["won"] else "LOSS ✗"
            # Handle negative rounds for losers bracket
            bracket_round = match["bracket_round"]
            if bracket_round < 0:
                round_text = f"L{abs(bracket_round)}"
            elif bracket_round > 0:
                round_text = f"W{bracket_round}"
            else:
                round_text = "?"

            print(
                f"{round_text:<8} {match['opponent']:<20} "
                f"#{match['opponent_seed']:<4} {result}"
            )


def main():
    try:
        if len(sys.argv) < 2:
            print(
                "Usage: python daness-v2.py <event-slug> [round|bracket|standings|why]"
            )
            print(
                "Example: python daness-v2.py tournament/playground-bracket-2/event/ultimate-singles-2"
            )
            print(
                "         python daness-v2.py tournament/playground-bracket-2/event/ultimate-singles-2 2"
            )
            print(
                "         python daness-v2.py tournament/playground-bracket-2/event/ultimate-singles-2 bracket"
            )
            print(
                "         python daness-v2.py tournament/playground-bracket-2/event/ultimate-singles-2 standings"
            )
            print(
                "         python daness-v2.py tournament/playground-bracket-2/event/ultimate-singles-2 why <player-name>"
            )
            sys.exit(1)

        slug = sys.argv[1]
        command = sys.argv[2] if len(sys.argv) > 2 else None

        print(f"Fetching basic event data for: {slug}")

        # Get basic phases info
        data = make_request(PHASES_QUERY, {"slug": slug})

        if not data or "data" not in data or not data["data"]["event"]:
            print("Event not found")
            sys.exit(1)

        event = data["data"]["event"]
        basic_phases = event["phases"]

        print(f"Event: {event['name']}")
        print(f"Found {len(basic_phases)} phases")

        # Sort phases by order
        phases = sorted(basic_phases, key=lambda x: x["phaseOrder"])

        print("\nPhases found:")
        for phase in phases:
            state = get_phase_state(phase["state"])
            state_name = {1: "NOT_STARTED", 2: "ACTIVE", 3: "COMPLETED"}.get(
                state, f"UNKNOWN({phase['state']})"
            )
            print(f"  - {phase['name']} (state: {state_name})")

        # Get detailed data for each phase
        detailed_phases = []
        for phase in phases:
            phase_data = make_request(PHASE_DETAILS_QUERY, {"phaseId": phase["id"]})
            if phase_data and "data" in phase_data and phase_data["data"]["phase"]:
                detailed_phase = phase_data["data"]["phase"]
                detailed_phase["state"] = phase["state"]
                detailed_phase["phaseOrder"] = phase["phaseOrder"]
                detailed_phases.append(detailed_phase)

        print(f"Got detailed data for {len(detailed_phases)} phases")

        # Get initial seeding
        first_phase = detailed_phases[0]
        all_seeds = []

        for group in first_phase["phaseGroups"]["nodes"]:
            if group["seeds"]["nodes"]:
                all_seeds.extend(group["seeds"]["nodes"])

        if not all_seeds:
            print("No seeding found in first phase")
            sys.exit(1)

        print(f"Found {len(all_seeds)} players in initial seeding")

        # Save/load initial seeding
        seeding_file = save_initial_seeding(slug, all_seeds)
        initial_seeding = load_initial_seeding(seeding_file)
        print(f"Loaded initial seeding for {len(initial_seeding)} players")

        # Handle bracket generation command
        if command == "bracket":
            match_results = get_match_results_from_phases(
                detailed_phases, swiss_only=True
            )

            print("Generating bracket seeding...")
            final_standings = calculate_final_standings_points_based(
                initial_seeding, match_results
            )
            generate_bracket_seeding(final_standings)
            return

        # Handle final standings command
        if command == "standings":
            match_results = get_match_results_from_phases(
                detailed_phases, swiss_only=True
            )
            print("Calculating final tournament standings...")

            # Use Swiss-only standings calculation
            final_tournament_standings = calculate_swiss_only_tournament_standings(
                initial_seeding, match_results
            )

            if final_tournament_standings:
                print("\nUpdating 'Final Standings' phase...")
                success = update_final_standings_phase(
                    detailed_phases, final_tournament_standings, initial_seeding
                )
                if success:
                    print(
                        "\n🎉 Final standings calculated and phase updated successfully!"
                    )
                else:
                    print("\n⚠️  Final standings calculated but phase update failed")
            return

        if command == "why":
            if len(sys.argv) < 4:
                print("Usage: python daness-v2.py <event-slug> why <player-name>")
                sys.exit(1)

            player_name = " ".join(sys.argv[3:])  # Handle names with spaces
            print(f"Analyzing pairings for: {player_name}")

            # Load initial seeding
            seeding_file = f"{slug.replace('/', '-')}-seeding.txt"
            if not os.path.exists(seeding_file):
                print(f"❌ No seeding file found. Run the tool without commands first.")
                sys.exit(1)

            initial_seeding = load_initial_seeding(seeding_file)

            # Analyze the player
            analyze_player_pairings(player_name, initial_seeding, detailed_phases)
            return

        # Handle round-specific updates
        target_round = None
        if command and command.isdigit():
            target_round = int(command)
            print(f"Target round specified: {target_round}")
        else:
            print("Finding next unstarted phase...")
            # Find next unstarted phase
            for phase in detailed_phases:
                phase_state = get_phase_state(phase["state"])
                if phase_state < 2:  # NOT_STARTED or CREATED
                    target_round = extract_round_number(phase["name"])
                    print(
                        f"Found unstarted phase: {phase['name']}, round {target_round}"
                    )
                    break

            if target_round is None:
                print("All phases are started or completed")
                sys.exit(1)

        # Find the phase for target round
        target_phase = None
        for phase in detailed_phases:
            if extract_round_number(phase["name"]) == target_round:
                target_phase = phase
                print(f"Found target phase: {phase['name']}")
                break

        if not target_phase:
            print(f"Round {target_round} phase not found")
            sys.exit(1)

        target_phase_state = get_phase_state(target_phase["state"])
        if target_phase_state >= 2:
            print(f"Round {target_round} has already started")
            sys.exit(1)

        print(f"\nPreparing pairings for Round {target_round}")

        # Calculate standings
        print("Calculating standings...")
        match_results = get_match_results_from_phases(detailed_phases, swiss_only=True)
        standings = calculate_standings(initial_seeding, match_results)
        print(f"Calculated standings for {len(standings)} players")

        # Calculate pairings
        print("Calculating pairings...")
        pairings = calculate_swiss_pairings(standings, round_number=target_round)

        print(f"\nCalculated {len(pairings)} pairings:")
        for i, ((p1_name, p1_info), (p2_name, p2_info)) in enumerate(pairings, 1):
            print(
                f"  Match {i}: {p1_name} ({p1_info['wins']}-{p1_info['losses']}) vs "
                + f"{p2_name} ({p2_info['wins']}-{p2_info['losses']})"
            )

        # Update the phase seeding
        print("Updating phase seeding...")
        if update_phase_seeding_for_pairings(
            target_phase["id"], target_phase["phaseGroups"]["nodes"], pairings
        ):
            print(f"\n✅ Successfully updated Round {target_round} pairings!")
            print("You can now start this phase in StartGG.")
        else:
            print(f"\n❌ Failed to update Round {target_round} pairings")
            return

        # Recommend stream matches
        print("Generating stream recommendations...")
        recommend_stream_matches(pairings, standings)

    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
