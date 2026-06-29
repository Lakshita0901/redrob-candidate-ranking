# AI Candidate Ranking System — RedRob Challenge

## Problem Statement
The challenge requires ranking a pool of 100,000 candidate profiles to find the top 100 best-fit candidates for a "Senior AI Engineer — Founding Team" role. The ranking must be done efficiently on CPU under strict time limits (5 minutes), without network access, while avoiding specifically designed trap profiles and honeypots.

## Approach
Our solution implements a multi-stage deterministic scoring and filtering pipeline that processes candidates line-by-line to avoid loading the entire dataset into memory.

The pipeline runs in two phases:
1. **Honeypot Filter**: A series of checks designed to catch impossible or contradictory information, assigning a score of `0.0` immediately.
2. **Deterministic Multi-Stage Scorer**: Evaluates valid candidates across 5 weighted dimensions.

### The 6-Step Pipeline

#### Step 1: Honeypot & Trap Detection (Pre-filter)
Candidates are immediately disqualified and scored `0.0` if they match any of the following impossible patterns:
- **Company Age Trap**: Working at a company for longer than the company has existed or starting work before the company was founded (checked using a verified list of synthetic company founding years).
- **Skill Experience Trap**: Having an `expert` proficiency in a skill but listing a duration of `0` months.
- **Future Graduation**: Listing a graduation year in the future (> 2026).
- **Impossible Timeline**: Total years of experience exceeding `2026 - earliest_graduation_year + 4` (a threshold allowing for normal overlapping study/work periods but catching severe anomalies).
- **Salary Contradiction**: Listing an expected salary range where the minimum exceeds the maximum.

#### Step 2: Skill Match Score (Weight: 40%)
Checks the candidate's skills against 12 core AI/ML technologies: `python`, `machine learning`, `deep learning`, `llm`, `pytorch`, `tensorflow`, `nlp`, `rag`, `mlops`, `vector database`, `transformers`, and `langchain`. Scores are normalized based on the fraction of matching skills (supporting exact and partial substring matches).

#### Step 3: Experience Score (Weight: 25%)
Prioritizes the job description's 4–8 years sweet spot:
- Base score is calculated as `min(years_of_experience / 8.0, 1.0)`.
- A **0.6x penalty multiplier** is applied if the candidate's work history contains only consulting firms (e.g. TCS, Infosys, Wipro, Accenture, etc.).
- A **1.15x bonus multiplier** (capped at 1.0) is applied if the candidate has worked at any product/startup companies.

#### Step 4: Behavioral Signals Score (Weight: 20%)
Combines engagement data from the RedRob platform:
- **Response Rate**: Active response rate (0 to 1).
- **Profile Completeness**: Percentage of profile filled (0 to 1).
- **Last Active Score**: Recency of login (`<30` days = 1.0, `<90` days = 0.7, `<180` days = 0.4, else = 0.1).
- The final behavioral score is the mean of these available signals.

#### Step 5: Education Score (Weight: 10%)
Maps candidate degrees and study fields to score tiers:
- **1.0**: PhD in AI, ML, or Computer Science.
- **0.8**: Masters in AI, ML, or Computer Science.
- **0.6**: B.Tech / B.E. in Computer Science.
- **0.3**: Any other degree.
- **0.1**: No degree listed.

#### Step 6: Seniority Title Match (Weight: 5%)
Inspects the current title string:
- **1.0**: Titles containing "senior", "lead", "principal", "staff", or "architect".
- **0.6**: Titles containing "mid", "engineer ii", or "engineer 2".
- **0.1**: Titles containing "junior", "fresher", or "intern".
- **0.4**: All other titles.

---

## Scoring Weights Summary

| Dimension | Weight | Purpose |
| :--- | :---: | :--- |
| **Skill Match** | 40% | Core alignment with target ML/NLP tech stack |
| **Experience** | 25% | Prioritization of 4–8 YOE and product-company background |
| **Behavioral Signals** | 20% | Filtering for active and responsive candidates |
| **Education** | 10% | Academic specialization in CS/ML |
| **Seniority Title** | 5% | Leadership and role alignment |

---

## How to Run

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Ranker**:
   ```bash
   python rank.py
   ```
   This streams candidate profiles from `candidates.jsonl` and writes the top 100 to `ranked_candidates.json`.

3. **Format & Validate CSV Output**:
   ```bash
   python output.py
   ```
   This reads `ranked_candidates.json` and produces `submission.csv` (properly formatting the monotonically decreasing scores and reasoning string) and automatically validates it using `validate_submission.py`.

## Output File
The final formatted file is saved as **`submission.csv`** and contains the columns:
- `candidate_id`: Standard CAND_XXXXXXX ID.
- `rank`: Rank from 1 to 100.
- `score`: Artificially mapped score from `0.9920` (rank 1) decrementing by `0.0080` per rank.
- `reasoning`: Synthesized text following the format: `"{current_title} with {X} yrs; {N} AI core skills; response rate {R}."`

## Architecture Decisions
- **Rule-based Scoring**: Highly interpretable, fast (runs in ~10 seconds on 100K candidates), and allows precise manual control over dataset traps (like keyword-stuffing and consulting-only backgrounds) without relying on expensive, slow, or black-box embedding model searches.
- **Honeypot Pre-filtering**: Prevents impossible candidate profiles (e.g. working at Krutrim since 2020 or having expert skills with 0 months experience) from leaking into the top 100, which would lead to automatic Stage 3 disqualification.
