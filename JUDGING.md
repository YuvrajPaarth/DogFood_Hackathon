# JUDGING.md

## Judge Assignment

Judges are assigned to events by an organizer via `POST /api/events/{event_id}/judges`. Assignment is stored in the `judge_assignments` table. A judge can only see and score projects in events they are assigned to.

Batch assignment is supported: the organizer POSTs a judge's email, the system finds the user and creates the assignment. Algorithmic round-robin assignment can be added on top of this.

## Scoring

Each event has a configurable rubric — a set of named criteria with weights and max scores. Default criteria seeded from fixtures: `functionality` (weight 1.5), `quality` (weight 1.0), `innovation` (weight 1.2), `presentation` (weight 0.8).

A judge submits one score per (submission, rubric criterion) pair via `POST /api/judge/scores`. Scores can be updated before results are published.

**Weighted score per submission per judge:**

```
weighted_score = sum(score_i * weight_i / max_score_i) / sum(weight_i)
```

## Cross-Judge Normalization

Different judges have different internal scales. One judge's "7" may mean the same as another's "9". Without normalization, projects reviewed by lenient judges are unfairly ranked higher.

**Method: Z-score normalization per judge**

For each judge `j`, compute:
- `mean_j` = mean of all raw scores given by judge j
- `std_j` = standard deviation of all raw scores by judge j

Normalized score for a raw score `s` from judge `j`:
```
z = (s - mean_j) / std_j      (if std_j > 0, else z = 0)
```

Rescale z-score back to 0–10 range (z typically falls in -3..+3):
```
normalized = clamp((z + 3) / 6 * max_score, 0, max_score)
```

Final score per submission = weighted average of normalized scores across all rubrics and judges.

**Effect on the fixture data:**
- Judge `jdg_03` rated every project 5/10 (zero variance → normalized to 5.0 for all)
- Judge `jdg_01` ranged from 3 to 8 — normalization spreads these fairly
- Rankings shift: projects reviewed only by lenient judges drop, those reviewed by harsh judges rise

The endpoint `GET /api/events/{id}/results?normalized=true` returns both the ranking and the normalization flag in the response.

## Role Isolation

Role isolation is enforced at the API layer, not the frontend:

- **Judges** can only access `GET /api/judge/scores` for their own scores (no `?judge=` param allowed)
- Passing `?judge=other_judge` as a judge returns HTTP 403
- **Participants** get HTTP 403 on any judge score endpoint
- **Organizers** can view all scores and use `?judge=` to inspect any judge
- This is verified by the acceptance suite (T2.5, T2.6)

## Honest Gap Assessment

- No pairwise comparison mode (Bradley-Terry) — would require T2+ completion first
- No audit trail table yet — score updates overwrite in place
- No vote abuse protection (T3 feature)
- Normalization is implemented and documentable, but not yet proven against the full fixture set via a dedicated report
