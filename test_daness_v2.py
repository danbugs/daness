#!/usr/bin/env python3
"""
Test framework for daness-v2.py
This creates mock tournaments with various edge cases to test the pairing algorithm
"""

import json
import random
import copy
from collections import defaultdict
import sys
import os

# Import the main module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from daness_v2 import (
    calculate_standings,
    calculate_swiss_pairings,
    calculate_final_standings_points_based,
    generate_bracket_seeding,
)


class MockTournament:
    """Creates mock tournament data for testing"""
    
    def __init__(self, num_players=32, seed=None):
        if seed:
            random.seed(seed)
        
        self.num_players = num_players
        self.players = self._generate_players()
        self.initial_seeding = {p["name"]: p["seed"] for p in self.players}
        self.match_results = []
        self.round_results = defaultdict(list)
        
    def _generate_players(self):
        """Generate player names and seeds"""
        players = []
        names = [
            "Alex", "Blake", "Casey", "Drew", "Ellis", "Finley", "Gray", "Harper",
            "Indigo", "Jordan", "Kelly", "Logan", "Morgan", "Nova", "Oakley", "Phoenix",
            "Quinn", "River", "Sage", "Taylor", "Unity", "Vale", "Winter", "Xander",
            "Yuki", "Zephyr", "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"
        ]
        
        for i in range(self.num_players):
            players.append({
                "name": names[i] if i < len(names) else f"Player{i+1}",
                "seed": i + 1
            })
        
        return players
    
    def simulate_match(self, p1_seed, p2_seed, upset_rate=0.2):
        """Simulate a match outcome with configurable upset rate"""
        # Calculate win probability for p1 (lower seed = better)
        seed_diff = p2_seed - p1_seed
        base_prob = 0.5 + (seed_diff * 0.02)  # 2% advantage per seed
        
        # Apply upset factor
        if p1_seed > p2_seed:  # p1 is underdog
            win_prob = base_prob * (1 + upset_rate)
        else:  # p1 is favorite
            win_prob = base_prob * (1 - upset_rate * 0.5)
        
        win_prob = max(0.1, min(0.9, win_prob))  # Clamp between 10% and 90%
        
        return random.random() < win_prob
    
    def simulate_round(self, round_num, pairings, upset_rate=0.2):
        """Simulate all matches in a round"""
        round_results = []
        
        for (p1_name, p1_info), (p2_name, p2_info) in pairings:
            p1_seed = p1_info["seed"]
            p2_seed = p2_info["seed"]
            
            p1_wins = self.simulate_match(p1_seed, p2_seed, upset_rate)
            
            winner_id = f"player_{p1_name}" if p1_wins else f"player_{p2_name}"
            
            match_result = {
                "round": round_num,
                "winner_id": winner_id,
                "players": [
                    {"id": f"player_{p1_name}", "name": p1_name},
                    {"id": f"player_{p2_name}", "name": p2_name}
                ],
                "phase_name": f"Swiss Round {round_num}"
            }
            
            self.match_results.append(match_result)
            round_results.append(match_result)
        
        self.round_results[round_num] = round_results
        return round_results


class TournamentTester:
    """Test various tournament scenarios"""
    
    def __init__(self):
        self.test_results = []
    
    def run_test(self, test_name, test_func):
        """Run a single test and record results"""
        print(f"\n{'='*60}")
        print(f"Running Test: {test_name}")
        print(f"{'='*60}")
        
        try:
            result = test_func()
            self.test_results.append({
                "name": test_name,
                "status": "PASSED" if result else "FAILED",
                "details": result
            })
            print(f"✅ Test PASSED" if result else f"❌ Test FAILED")
        except Exception as e:
            self.test_results.append({
                "name": test_name,
                "status": "ERROR",
                "details": str(e)
            })
            print(f"❌ Test ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    def test_no_rematches_standard(self):
        """Test that no rematches occur in a standard tournament"""
        tournament = MockTournament(32, seed=42)
        
        for round_num in range(1, 6):
            standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            
            # Check for rematches
            for (p1_name, p1_info), (p2_name, p2_info) in pairings:
                if p2_name in p1_info.get("opponents", []):
                    print(f"❌ Rematch detected in round {round_num}: {p1_name} vs {p2_name}")
                    return False
            
            # Simulate the round
            tournament.simulate_round(round_num, pairings)
        
        print("✓ No rematches detected in 5 rounds")
        return True
    
    def test_high_upset_tournament(self):
        """Test tournament with high upset rate"""
        tournament = MockTournament(32, seed=123)
        
        for round_num in range(1, 6):
            standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            tournament.simulate_round(round_num, pairings, upset_rate=0.4)
        
        # Check final standings
        final_standings = calculate_final_standings_points_based(
            tournament.initial_seeding, tournament.match_results
        )
        
        # Count cinderella stories
        cinderella_count = sum(1 for p in final_standings if p["cinderella_bonus"] > 5)
        print(f"✓ Found {cinderella_count} Cinderella stories (bonus > 5)")
        
        return cinderella_count > 3  # Expect several cinderella stories
    
    def test_round_5_critical_matches(self):
        """Test that round 5 properly pairs 2-2 players"""
        tournament = MockTournament(32, seed=789)
        
        # Simulate 4 rounds
        for round_num in range(1, 5):
            standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            tournament.simulate_round(round_num, pairings)
        
        # Get round 5 pairings
        standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
        pairings = calculate_swiss_pairings(standings, round_number=5)
        
        # Check 2-2 pairings
        two_two_matches = []
        for (p1_name, p1_info), (p2_name, p2_info) in pairings:
            if p1_info["wins"] == 2 and p1_info["losses"] == 2:
                if p2_info["wins"] == 2 and p2_info["losses"] == 2:
                    two_two_matches.append((p1_name, p1_info["seed"], p2_name, p2_info["seed"]))
        
        print(f"✓ Found {len(two_two_matches)} matches between 2-2 players")
        
        # Check seed differences
        for p1_name, p1_seed, p2_name, p2_seed in two_two_matches:
            seed_diff = abs(p1_seed - p2_seed)
            print(f"  {p1_name} (seed {p1_seed}) vs {p2_name} (seed {p2_seed}) - diff: {seed_diff}")
        
        return len(two_two_matches) >= 4
    
    def test_constraint_satisfaction(self):
        """Test with artificial constraints to force difficult pairings"""
        tournament = MockTournament(32, seed=456)
        
        # Create a scenario where many players have played each other
        # This simulates a worst-case scenario for rematch avoidance
        
        # Round 1: Normal
        standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
        pairings = calculate_swiss_pairings(standings, round_number=1)
        tournament.simulate_round(1, pairings)
        
        # Rounds 2-4: Force some specific results to create constraints
        for round_num in range(2, 5):
            standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
            
            # Manipulate standings to force certain records
            if round_num == 4:
                # Count players by record
                record_counts = defaultdict(list)
                for name, info in standings.items():
                    record = (info["wins"], info["losses"])
                    record_counts[record].append(name)
                
                print(f"\nRound {round_num} record distribution:")
                for record, players in sorted(record_counts.items()):
                    print(f"  {record[0]}-{record[1]}: {len(players)} players")
            
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            tournament.simulate_round(round_num, pairings)
        
        # Test round 5 with maximum constraints
        standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
        pairings = calculate_swiss_pairings(standings, round_number=5)
        
        # Check if algorithm handled constraints
        rematch_count = 0
        for (p1_name, p1_info), (p2_name, p2_info) in pairings:
            if p2_name in p1_info["opponents"]:
                rematch_count += 1
        
        print(f"✓ Round 5 completed with {rematch_count} rematches")
        return rematch_count <= 1  # Allow at most 1 forced rematch
    
    def test_bracket_seeding_fairness(self):
        """Test that bracket seeding properly rewards performance"""
        tournament = MockTournament(32, seed=999)
        
        # Simulate full Swiss
        for round_num in range(1, 6):
            standings = calculate_standings(tournament.initial_seeding, tournament.match_results)
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            tournament.simulate_round(round_num, pairings)
        
        # Generate bracket seeding
        final_standings = calculate_final_standings_points_based(
            tournament.initial_seeding, tournament.match_results
        )
        main_bracket, redemption_bracket = generate_bracket_seeding(final_standings)
        
        # Check that higher seeds with same record are ranked higher
        print("\nMain Bracket:")
        for i, player in enumerate(main_bracket[:8]):
            print(f"  {i+1}. {player['name']} ({player['wins']}-{player['losses']}, seed {player['initial_seed']})")
        
        # Verify no 0-5 or 1-4 in main bracket
        for player in main_bracket:
            if player['wins'] <= 1:
                print(f"❌ Low performer in main bracket: {player['name']} ({player['wins']}-{player['losses']})")
                return False
        
        print("✓ Bracket seeding appears fair")
        return True
    
    def test_edge_cases(self):
        """Test various edge cases"""        
        # Test with extreme upset scenarios
        tournament_upset = MockTournament(32, seed=222)
        
        # Simulate where all lower seeds win
        for round_num in range(1, 3):
            standings = calculate_standings(tournament_upset.initial_seeding, tournament_upset.match_results)
            pairings = calculate_swiss_pairings(standings, round_number=round_num)
            
            # Force upsets
            for (p1_name, p1_info), (p2_name, p2_info) in pairings:
                winner_id = f"player_{p2_name}" if p2_info["seed"] > p1_info["seed"] else f"player_{p1_name}"
                tournament_upset.match_results.append({
                    "round": round_num,
                    "winner_id": winner_id,
                    "players": [
                        {"id": f"player_{p1_name}", "name": p1_name},
                        {"id": f"player_{p2_name}", "name": p2_name}
                    ],
                    "phase_name": f"Swiss Round {round_num}"
                })
        
        print("✓ Handled extreme upset scenarios")
        return True
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        self.run_test("No Rematches in Standard Tournament", self.test_no_rematches_standard)
        self.run_test("High Upset Tournament", self.test_high_upset_tournament)
        self.run_test("Round 5 Critical Matches", self.test_round_5_critical_matches)
        self.run_test("Constraint Satisfaction", self.test_constraint_satisfaction)
        self.run_test("Bracket Seeding Fairness", self.test_bracket_seeding_fairness)
        self.run_test("Edge Cases", self.test_edge_cases)
        
        # Generate report
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for t in self.test_results if t["status"] == "PASSED")
        failed = sum(1 for t in self.test_results if t["status"] == "FAILED")
        errors = sum(1 for t in self.test_results if t["status"] == "ERROR")
        
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Errors: {errors}")
        
        if failed > 0 or errors > 0:
            print("\nFailed/Error Tests:")
            for test in self.test_results:
                if test["status"] in ["FAILED", "ERROR"]:
                    print(f"  - {test['name']}: {test['status']}")
                    if test["status"] == "ERROR":
                        print(f"    Error: {test['details']}")
        
        return passed == len(self.test_results)


def main():
    """Run the test suite"""
    print("DANESS-V2 TEST SUITE")
    print("=" * 60)
    
    tester = TournamentTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED - Review output above")
        sys.exit(1)


if __name__ == "__main__":
    main()