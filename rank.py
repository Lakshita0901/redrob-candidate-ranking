#!/usr/bin/env python3
"""
rank.py: Core candidate ranking pipeline.
Streams candidate data, executes the 6-stage scoring logic,
filters out honeypots, and saves the top 100 candidates.
"""

import json
import os
import argparse
from datetime import date
from tqdm import tqdm
import docx

# Discovered founding years of companies in this dataset
FOUNDING_YEARS = {
    "Accenture": 2016, "Acme Corp": 2011, "Adobe": 2019, "Aganitha": 2018, "Amazon": 2017,
    "Apple": 2018, "BYJU'S": 2018, "CRED": 2016, "Capgemini": 2016, "Cognizant": 2016,
    "Dream11": 2018, "Dunder Mifflin": 2011, "Flipkart": 2016, "Freshworks": 2018,
    "Genpact AI": 2017, "Glance": 2018, "Globex Inc": 2011, "Google": 2019, "HCL": 2016,
    "Haptik": 2017, "Hooli": 2011, "InMobi": 2018, "Infosys": 2011, "Initech": 2011,
    "Krutrim": 2018, "LinkedIn": 2019, "Locobuzz": 2018, "Mad Street Den": 2018,
    "Meesho": 2018, "Meta": 2018, "Microsoft": 2018, "Mindtree": 2016, "Mphasis": 2016,
    "Netflix": 2018, "Niramai": 2019, "Nykaa": 2018, "Observe.AI": 2019, "Ola": 2018,
    "Paytm": 2018, "PharmEasy": 2018, "PhonePe": 2018, "Pied Piper": 2011,
    "PolicyBazaar": 2018, "Razorpay": 2016, "Rephrase.ai": 2018, "Saarthi.ai": 2018,
    "Salesforce": 2017, "Sarvam AI": 2018, "Stark Industries": 2011, "Swiggy": 2016,
    "TCS": 2011, "Tech Mahindra": 2016, "Uber": 2019, "Unacademy": 2018,
    "Vedantu": 2018, "Verloop.io": 2019, "Wayne Enterprises": 2011, "Wipro": 2011,
    "Wysa": 2018, "Yellow.ai": 2018, "Zoho": 2018, "Zomato": 2016, "upGrad": 2018
}

FOUNDING_YEARS_LOWER = {k.lower(): v for k, v in FOUNDING_YEARS.items()}

REQUIRED_SKILLS = [
    "python", "machine learning", "deep learning", "llm",
    "pytorch", "tensorflow", "nlp", "rag", "mlops",
    "vector database", "transformers", "langchain"
]

CONSULTING_FIRMS = {
    "deloitte", "mckinsey", "accenture", "wipro", "infosys", "tcs", "cognizant", "capgemini"
}

def parse_jd(jd_path):
    """
    Read job_description.docx using python-docx.
    Logs that it was parsed successfully.
    """
    if not os.path.exists(jd_path):
        # Try relative to script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_path = os.path.join(script_dir, os.path.basename(jd_path))
        if os.path.exists(resolved_path):
            jd_path = resolved_path
        else:
            print(f"Warning: Job description not found at {jd_path}")
            return ""
    try:
        doc = docx.Document(jd_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        print(f"Successfully loaded and parsed Job Description ({len(text)} characters).")
        return text
    except Exception as e:
        print(f"Error parsing job description: {e}")
        return ""

def is_honeypot_candidate(cand):
    """
    Step 1: Honeypot Detection
    Returns True if the candidate has impossible/contradictory data.
    """
    profile = cand.get("profile", {})
    career = cand.get("career_history", [])
    education = cand.get("education", [])
    skills = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    
    # 1. Experience years > age of company or job starts before founding
    for job in career:
        comp = job.get("company", "").strip().lower()
        dur_months = job.get("duration_months")
        start_date = job.get("start_date")
        
        if comp in FOUNDING_YEARS_LOWER:
            f_yr = FOUNDING_YEARS_LOWER[comp]
            age_limit = 2026 - f_yr
            
            # Check duration
            if dur_months is not None and (dur_months / 12.0) > age_limit:
                return True
                
            # Check start year
            if start_date:
                try:
                    start_year = int(start_date.split("-")[0])
                    if start_year < f_yr:
                        return True
                except ValueError:
                    pass

    # 2. Skill listed with proficiency > 0.9 (expert) but duration = 0 years
    for s in skills:
        prof = s.get("proficiency")
        dur_months = s.get("duration_months", 0)
        # In our dataset, all proficiencies are strings. 'expert' is mapped to >0.9.
        if prof == "expert" and dur_months == 0:
            return True

    # 3. Graduation year is in the future (> 2026)
    for e in education:
        end_yr = e.get("end_year")
        if end_yr and end_yr > 2026:
            return True

    # 4. Total experience > (2026 - graduation_year + 4)
    # We use min_grad_yr (earliest degree end year) to avoid false positives on postgrads.
    min_grad_yr = 9999
    for e in education:
        end_yr = e.get("end_year")
        if end_yr and end_yr < min_grad_yr:
            min_grad_yr = end_yr
            
    if min_grad_yr < 9999:
        yoe = profile.get("years_of_experience", 0)
        if yoe > (2026 - min_grad_yr + 4):
            return True

    # 5. Obviously contradictory data (e.g. expected salary min > max)
    salary = signals.get("expected_salary_range_inr_lpa", {})
    s_min = salary.get("min")
    s_max = salary.get("max")
    if s_min is not None and s_max is not None and s_min > s_max:
        return True

    # 6. Signup date after last active date
    signup_date = signals.get("signup_date")
    last_active_date = signals.get("last_active_date")
    if signup_date and last_active_date and signup_date > last_active_date:
        return True

    return False

def calculate_score(cand):
    """
    Executes Steps 2-6 to compute the candidate's final score.
    """
    profile = cand.get("profile", {})
    career = cand.get("career_history", [])
    education = cand.get("education", [])
    skills = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    
    # --- Step 2: Skill Match Score (weight: 40%) ---
    cand_skills_lower = [s.get("name", "").lower().strip() for s in skills if s.get("name")]
    matched_count = 0
    for req in REQUIRED_SKILLS:
        matched = False
        for cs in cand_skills_lower:
            if req in cs or cs in req:
                matched = True
                break
        if matched:
            matched_count += 1
    skill_score = matched_count / len(REQUIRED_SKILLS)
    
    # --- Step 3: Experience Score (weight: 25%) ---
    yoe = profile.get("years_of_experience", 0.0)
    exp_score = min(yoe / 8.0, 1.0)
    
    companies = [j.get("company", "").strip().lower() for j in career if j.get("company")]
    if companies:
        is_only_consulting = all(c in CONSULTING_FIRMS for c in companies)
        has_product_startup = any(c not in CONSULTING_FIRMS for c in companies)
        
        if is_only_consulting:
            exp_score *= 0.6
        if has_product_startup:
            exp_score *= 1.15
            
    exp_score = min(exp_score, 1.0)
    
    # --- Step 4: Behavioral Signals Score (weight: 20%) ---
    behavior_scores = []
    
    # Response rate
    rr = signals.get("recruiter_response_rate")
    if rr is not None:
        behavior_scores.append(rr)
        
    # Profile completeness
    pc = signals.get("profile_completeness_score")
    if pc is not None:
        behavior_scores.append(pc / 100.0)
        
    # Last active days
    lad = signals.get("last_active_date")
    if lad:
        try:
            current_date = date(2026, 6, 29)
            act_date = date.fromisoformat(lad)
            days = (current_date - act_date).days
            if days < 30:
                act_score = 1.0
            elif days < 90:
                act_score = 0.7
            elif days < 180:
                act_score = 0.4
            else:
                act_score = 0.1
            behavior_scores.append(act_score)
        except:
            pass
            
    behavioral_score = sum(behavior_scores) / len(behavior_scores) if behavior_scores else 0.0
    
    # --- Step 5: Education Score (weight: 10%) ---
    if not education:
        edu_score = 0.1
    else:
        best_edu = 0.1
        for edu in education:
            deg = edu.get("degree", "").lower().strip()
            field = edu.get("field_of_study", "").lower().strip()
            
            is_ai_ml_cs = any(t in field for t in ["computer science", "cs", "artificial intelligence", "ai", "machine learning", "ml", "data science"])
            is_cs = any(t in field for t in ["computer science", "cs"])
            
            if any(t in deg for t in ["phd", "ph.d", "doctor"]):
                if is_ai_ml_cs:
                    best_edu = max(best_edu, 1.0)
                else:
                    best_edu = max(best_edu, 0.3)
            elif any(t in deg for t in ["master", "ms", "mtech", "m.tech", "msc", "m.sc"]):
                if is_ai_ml_cs:
                    best_edu = max(best_edu, 0.8)
                else:
                    best_edu = max(best_edu, 0.3)
            elif any(t in deg for t in ["btech", "b.tech", "b.e.", "be", "bachelor", "bs", "b.s."]):
                if is_cs or is_ai_ml_cs:
                    best_edu = max(best_edu, 0.6)
                else:
                    best_edu = max(best_edu, 0.3)
            else:
                best_edu = max(best_edu, 0.3)
        edu_score = best_edu
        
    # --- Step 6: Seniority Title Match (weight: 5%) ---
    title = profile.get("current_title", "").lower().strip()
    if any(t in title for t in ["senior", "lead", "principal", "staff", "architect"]):
        seniority_score = 1.0
    elif any(t in title for t in ["mid", "engineer ii", "engineer 2"]):
        seniority_score = 0.6
    elif any(t in title for t in ["junior", "fresher", "intern"]):
        seniority_score = 0.1
    else:
        seniority_score = 0.4
        
    # --- Final Score Formula ---
    final_score = (
        0.40 * skill_score +
        0.25 * exp_score +
        0.20 * behavioral_score +
        0.10 * edu_score +
        0.05 * seniority_score
    )
    
    return final_score, matched_count

def process_candidates(candidates_path, jd_path):
    """
    Streams candidates from JSONL or loads from JSON list,
    checks honeypots, scores, and returns sorted list of candidates.
    """
    parse_jd(jd_path)
    
    scored_candidates = []
    honeypot_detected = 0
    total_processed = 0
    
    # Check if the file is a JSON array or JSONL
    is_json_array = False
    if os.path.exists(candidates_path):
        with open(candidates_path, "r", encoding="utf-8") as f:
            for char in f.read(100):
                if char.strip():
                    if char == '[':
                        is_json_array = True
                    break
                    
    if is_json_array:
        print("Detected JSON array format. Loading entire file...")
        with open(candidates_path, "r", encoding="utf-8") as f:
            candidates_list = json.load(f)
        for cand in tqdm(candidates_list, desc="Processing candidates"):
            total_processed += 1
            if is_honeypot_candidate(cand):
                honeypot_detected += 1
                continue
            score, matched_skills = calculate_score(cand)
            scored_candidates.append({
                "candidate_id": cand["candidate_id"],
                "current_title": cand.get("profile", {}).get("current_title", ""),
                "years_of_experience": cand.get("profile", {}).get("years_of_experience", 0.0),
                "matched_skills_count": matched_skills,
                "response_rate": cand.get("redrob_signals", {}).get("recruiter_response_rate", 0.0),
                "final_score": score
            })
    else:
        print("Detected JSONL format. Streaming line-by-line...")
        num_lines = 100000 if "candidates.jsonl" in candidates_path else None
        with open(candidates_path, "r", encoding="utf-8") as f:
            for line in tqdm(f, total=num_lines, desc="Processing candidates"):
                if not line.strip():
                    continue
                total_processed += 1
                cand = json.loads(line)
                
                # Honeypot Check
                if is_honeypot_candidate(cand):
                    honeypot_detected += 1
                    continue
                    
                # Score
                score, matched_skills = calculate_score(cand)
                scored_candidates.append({
                    "candidate_id": cand["candidate_id"],
                    "current_title": cand.get("profile", {}).get("current_title", ""),
                    "years_of_experience": cand.get("profile", {}).get("years_of_experience", 0.0),
                    "matched_skills_count": matched_skills,
                    "response_rate": cand.get("redrob_signals", {}).get("recruiter_response_rate", 0.0),
                    "final_score": score
                })
            
    print(f"\nProcessing Complete:")
    print(f"  Total Candidates Processed: {total_processed}")
    print(f"  Honeypots Detected & Filtered: {honeypot_detected}")
    print(f"  Valid Candidates Scored: {len(scored_candidates)}")
    
    # Sort descending by final_score, tie-break by candidate_id ascending
    scored_candidates.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))
    
    return scored_candidates[:100]

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for RedRob AI Founding Engineer role.")
    parser.add_argument("--candidates", default="candidates.jsonl", help="Path to candidates jsonl file")
    parser.add_argument("--jd", default="job_description.docx", help="Path to job_description.docx")
    parser.add_argument("--out", default="ranked_candidates.json", help="Output path for top 100 JSON")
    args = parser.parse_args()
    
    top_100 = process_candidates(args.candidates, args.jd)
    
    # Write to JSON
    with open(args.out, "w", encoding="utf-8") as out_f:
        json.dump(top_100, out_f, indent=2)
    print(f"Top 100 candidates written to {args.out}")

if __name__ == "__main__":
    main()
