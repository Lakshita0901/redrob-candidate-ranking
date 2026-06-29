#!/usr/bin/env python3
"""
output.py: Formatter and validator for submission CSV.
Reads top 100 JSON, formats ranks, scores, and reasonings,
outputs submission.csv, and runs validate_submission.py.
"""

import json
import csv
import argparse
import os
import sys

# Import validation function directly from the provided script
try:
    from validate_submission import validate_submission
except ImportError:
    print("Error: validate_submission.py not found in the path. Please run from its directory.")
    sys.exit(1)

def generate_csv(json_path, csv_path):
    """
    Reads the ranked JSON and generates the final submission CSV.
    """
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist. Run rank.py first.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)
        
    # Write CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Header row
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, cand in enumerate(candidates):
            rank = idx + 1
            score = 0.9920 - (rank - 1) * 0.0080
            
            # Format reasoning: "{current_title} with {X} yrs; {N} AI core skills; response rate {R}."
            title = cand.get("current_title", "").strip()
            yoe = cand.get("years_of_experience", 0.0)
            skills = cand.get("matched_skills_count", 0)
            rr = cand.get("response_rate", 0.0)
            
            reasoning = f"{title} with {yoe:.1f} yrs; {skills} AI core skills; response rate {rr:.2f}."
            
            writer.writerow([
                cand["candidate_id"],
                rank,
                f"{score:.4f}",
                reasoning
            ])
            
    print(f"Generated submission file: {csv_path}")

def run_validation(csv_path):
    """
    Runs validate_submission function on the generated CSV file.
    """
    print(f"Validating {csv_path} using validate_submission.py...")
    errors = validate_submission(csv_path)
    
    if not errors:
        print("=" * 60)
        print("PASSED: The submission file is valid per challenge rules.")
        print("=" * 60)
        return True
    else:
        print("=" * 60)
        print("FAILED: Validation errors found:")
        for err in errors:
            print(f" - {err}")
        print("=" * 60)
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate and validate hackathon submission CSV.")
    parser.add_argument("--input", default="ranked_candidates.json", help="Path to ranked candidates JSON")
    parser.add_argument("--out", default="submission.csv", help="Path to final submission CSV")
    args = parser.parse_args()
    
    generate_csv(args.input, args.out)
    success = run_validation(args.out)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
