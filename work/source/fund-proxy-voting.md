# Do ESG funds vote like ESG funds?

[![CI](https://github.com/AshokReddy010/fund-proxy-voting/actions/workflows/ci.yml/badge.svg)](https://github.com/AshokReddy010/fund-proxy-voting/actions/workflows/ci.yml)

Every US fund must publish how it voted at company shareholder meetings. This project collects three years of those records from the SEC, 73.8 million votes from 12,416 funds, and asks one question:

**When a fund has "ESG" or "sustainable" in its name, does it vote differently from an ordinary fund?**

The short answer: a little, and far less than the name suggests. The fund house a fund belongs to tells you more about its votes than its label does.

**▶ [Interactive explorer](https://ashokreddy010.github.io/fund-proxy-voting/)**: support by fund group, ESG-named funds against their siblings at every fund house, and a searchable list of all ESG-named funds. It reads the result tables in [`reports/tables/`](reports/tables/) directly, so it updates whenever the data is refreshed.

## Findings

All figures are for shareholder proposals on environmental and social topics, in the reporting years ending June 2024, 2025 and 2026.

### 1. An ESG name predicts only modest support

![Support by fund group](reports/figures/support_by_fund_group.png)

Share of votes cast FOR proposals that specialist ESG fund houses backed:

| Fund group | 2024 | 2025 | 2026 |
|:--|--:|--:|--:|
| Specialist ESG houses (the yardstick) | 98.5% | 97.1% | 91.7% |
| ESG-named funds at other houses | 38.9% | 37.2% | 32.7% |
| All other funds | 28.1% | 16.4% | 13.9% |

ESG-named funds outside the specialist houses backed these proposals about a third of the time. That is more than ordinary funds, and well short of the specialists.

### 2. Ordinary funds' support halved in two years

Support from funds without an ESG name fell from 28.1% to 13.9% on the same kind of proposal. ESG-named funds slipped much less, from 38.9% to 32.7%.

### 3. Proposals that push the other way get almost no support from anyone

Many recent proposals ask companies to drop diversity programmes or climate targets. Every group voted for those about 1% to 2% of the time, ESG-named or not.

### 4. Most ESG-named funds vote exactly like their siblings

The fairest comparison is an ESG-named fund against ordinary funds from the same filer, voting on the same proposal. On proposals the specialists backed:

| | 2024 | 2025 | 2026 |
|:--|--:|--:|--:|
| Proposals compared | 5,139 | 3,612 | 2,173 |
| ESG-named fund voted the same as its siblings | 86.6% | 82.6% | 83.3% |
| ESG-named fund was more supportive | 11.8% | 16.3% | 16.1% |
| ESG-named fund was less supportive | 1.6% | 1.1% | 0.6% |

### 5. The fund house matters more than the label

![ESG-named funds against siblings by fund house](reports/figures/siblings_by_house.png)

At some filers the ESG-named funds vote very differently from their siblings: FlexShares Trust 99.7% against 25.4%, Northern Funds 99.4% against 42.6%. At others there is no difference at all: at SPDR Index Shares Funds, Russell Investment Company, TIAA-CREF Funds and Thrivent Series Fund, ESG-named funds matched their siblings on every proposal compared.

### 6. ESG-named funds are spread across the whole range

![Spread of ESG-named funds](reports/figures/esg_fund_spread.png)

Of 145 ESG-named funds outside the specialist houses with at least 20 votes, 41 backed fewer than 10% of these proposals and 21 backed 75% or more. The full list is in [`reports/tables/esg_named_fund_support.csv`](reports/tables/esg_named_fund_support.csv).

## How to read these results

- **Voting is one measure of a fund, not the whole of it.** A fund can pursue ESG aims through which shares it holds or through private talks with companies. Low support here describes how a fund voted on these proposals. It is not evidence that a fund's label is misleading.
- **"Backed by specialists" is a chosen yardstick.** A proposal counts as pro-ESG when ten specialist ESG fund houses mostly voted for it. Their own 98% is therefore close to true by construction.
- **The ESG label is read from fund names.** 413 funds are labelled this way. Funds that follow ESG rules without saying so in their name are counted as ordinary funds.
- Everything here comes from public SEC filings, reported as filed.

## The data

Form N-PX filings from SEC EDGAR, in the structured XML format the SEC introduced for filings from mid-2024.

| | |
|:--|--:|
| Filings read | 33,929 |
| Filings containing votes | 16,251 |
| Vote records | 73,755,572 |
| From funds (all topics) | 67,094,632 |
| From investment managers (executive pay votes only) | 6,660,940 |
| Distinct funds | 12,416 |
| Files that could not be read | 4 |

The raw data is not in this repository. `download_votes.py` rebuilds it from the SEC in about nine hours, at the SEC's permitted request rate.

## What made this hard

**1. Filers write the same answer many ways.** "For" appears as FOR, For, F and Yes; a one-year vote as ONE YEAR, 1 Year, 1-YEAR, 1YR and 1.0. There were more than 40 spellings across ten real answers, and meeting dates in 12 formats. After cleaning, 99.97% of votes map to a standard value. A dbt test fails if unrecognised votes ever pass 1%.

**2. One column does not mean what its name says.** The field `managementRecommendation` does not hold management's recommendation. It records whether the vote was cast for or against that recommendation. Read literally, it makes almost every shareholder proposal look management-backed. Read correctly, funds vote with management 89.9% of the time.

**3. The same proposal is worded differently by every filer.** A single Microsoft proposal appears in 16 wordings. `scripts/label_proposals.py` matches them within each company meeting, turning 8,274 wordings into 3,850 proposals.

**4. A proposal's title does not tell you which side it is on.** "Revisit Plastics Packaging Policies" and "Report on Net Zero Business Performance Risks" sound pro-ESG, and both received 0% support from specialist ESG houses. So direction is decided by two independent signals:

| Signal | How it works | Coverage |
|:--|:--|:--|
| Reference votes | How ten specialist ESG fund houses voted on the proposal | 857 proposals, 84% of all fund votes |
| Wording | Keyword rules, with rules for opposing proposals checked first | Fallback for the rest |

Where both signals gave an answer, the first version of the wording rules agreed with the reference votes 91.2% of the time. Nearly every disagreement was an opposing proposal written in ESG vocabulary. Refining the rules raised agreement to 94.7% on 664 proposals, but they were refined on those same cases, so that figure is optimistic. The published results therefore use reference votes wherever they exist, and report wording-only labels separately.

## Can a language model label the proposals?

Reference votes exist for 84% of fund votes. The rest depend on keyword rules, which are the weakest part of the pipeline. So I tested whether a language model could label a proposal's direction from its company name and title alone, and measured it against the reference votes.

**Setup**

- **Answer key:** 815 proposals where the specialist ESG houses gave a clear answer, 579 supporting and 236 opposing.
- **Split:** a fixed 237 for practice and 578 for the final test, assigned by a hash of the proposal ID.
- **Prompts:** three versions, written and revised using only the practice set. The final set was scored once, after the prompts were frozen.
- **Model:** `openai/gpt-oss-120b` through the Groq API, at temperature 0, with every answer cached in [`llm_eval/runs`](llm_eval/runs).

**Results on the final set (578 proposals)**

| Method | Accuracy | Opposing proposals caught | No clear answer |
|:--|--:|--:|--:|
| Keyword rules | 76.6% | 68.9% | 18.5% |
| LLM, plain prompt | 69.2% | 7.9% | 6.4% |
| LLM, prompt with written guidance | 76.5% | 36.0% | 6.1% |
| LLM, prompt with examples and a reframed task | 84.9% | 65.2% | 5.4% |
| Rules first, LLM where the rules give no answer | 91.0% | 76.2% | 2.9% |

Full tables, with precision and recall for both classes, are in [`llm_eval/results_test.md`](llm_eval/results_test.md). Every proposal a method got wrong is in [`llm_eval/errors_test.csv`](llm_eval/errors_test.csv).

**What this shows**

- **The prompt mattered more than anything else.** The same model went from 69.2% to 84.9%. With a plain prompt it labelled almost every proposal as supporting ESG, and caught 8% of the opposing ones.
- **The largest gain came from changing the question.** Asking "how would specialist responsible-investment funds vote on this?" worked better than asking whether a proposal "supports ESG", because opposing proposals are written in ESG vocabulary.
- **Rules and model fail in different places.** The rules are precise but silent on 18.5% of proposals. The model answers nearly all of them. Using the rules first and the model for the remainder beat both.
- **Practice scores were higher.** The combined method scored 93.7% on the practice set and 91.0% on the final set, which is the figure to quote.

**Limits of this test**

- The keyword rules were refined earlier against reference votes on many of these same proposals, so their 76.6%, and the combined 91.0% that builds on them, are optimistic. The LLM-only rows are a clean test.
- Even the best method misses about a quarter of opposing proposals.
- The answer key is the specialists' votes, which is a chosen yardstick and not ground truth.
- One model was tested. The published fund results do not use these LLM labels.

To rerun it, set a `GROQ_API_KEY` environment variable, then run `python llm_eval\run_llm.py --prompt v3_examples_and_reframing --split test` and `python llm_eval\score.py --split test`.

## In the cloud

**[Open the live dashboard](https://datastudio.google.com/reporting/018f69c4-a00a-4e0b-80dc-5e1085eabdd0)**, built on BigQuery and open to anyone with the link.

![Pipeline from SEC filings to the public dashboard](reports/figures/pipeline.gif)

The 73.8 million raw votes stay in DuckDB on a laptop. The curated tables go to BigQuery, where a second dbt project builds the reporting tables the dashboard reads.

| Layer | Where | What |
|:--|:--|:--|
| Raw and modelled votes | DuckDB, local | 73.8 million rows, 9 dbt models, 21 tests |
| Curated tables | BigQuery | 7 tables, about 1.1 million rows, including a summary of every fund vote by fund, year and topic |
| Reporting models | BigQuery, built by dbt | 4 tables and 11 tests, including a reconciliation of the fund scorecard against its source |
| Dashboard | Data Studio | Public, read-only |

**Why not put everything in the cloud?** The project runs on BigQuery's free sandbox, which allows 10 GB of storage over the project's lifetime, deletes tables after 60 days, and has no INSERT or MERGE statements. So the heavy layer stays local, and the curated layer, about 340 MB in BigQuery, is re-sent whole on each refresh. Each refresh also resets the 60-day clock, and the allowance covers roughly 29 refreshes.

**Every publish is checked.** `cloud/publish_to_bigquery.py` compares each table's row count in BigQuery with the local count and records the result in a `load_audit` table and in `cloud/publish_log.csv`. A dbt test fails if the curated tables are more than 45 days old, before the sandbox would delete them.

**Monthly refresh.** `cloud/refresh.py` runs the whole chain in one command: it fetches only SEC filings it has not seen before, appends their votes without re-reading the 73.8 million already loaded, rebuilds and tests the local models, re-publishes to BigQuery with the row-count audit, and rebuilds and tests the cloud models. Each run is logged in `cloud/refresh_log.csv`. Proposals first seen in new filings stay labelled "unclear" until the labelling step is re-run.

```
python cloud\refresh.py
```

To publish and rebuild the cloud layer on its own:

```
gcloud auth application-default login
python cloud\publish_to_bigquery.py --dry-run
python cloud\publish_to_bigquery.py
cd cloud\dbt_bigquery
dbt build --profiles-dir .
```

## How it is built

```
SEC EDGAR (33,929 filings)
   └─ download_votes.py     read each filing, save votes as compact files
       └─ load_raw.py           load into DuckDB (73.8 million rows)
           └─ dbt
               ├─ staging       clean votes, dates, topics, filer types
               ├─ fct_votes     every cleaned vote
               ├─ dim_funds     one row per fund, with the ESG-name label
               ├─ fct_fund_es_votes   one answer per fund per proposal
               └─ marts         support by direction, sibling comparison
scripts/label_proposals.py      match wordings, label direction  → seeds/proposal_labels.csv
scripts/make_charts.py          charts from reports/tables
llm_eval/                       LLM labelling test: answer key, prompts, cached runs, scores
```

- **dbt:** 9 models, 1 seed and 21 data tests, including a custom test that no fund has two answers for the same proposal.
- **Unit tests:** 8 pytest checks on the SEC file reader, the wording matcher and the direction rules, run by GitHub Actions on every push.
- **Runs on a laptop:** DuckDB with a 2 GB memory limit rebuilds every table from the 73.8 million rows in about ten minutes.

## Run it yourself

Needs Python 3.10 or newer and about 10 GB of free disk. Commands are for Windows CMD.

```
git clone https://github.com/AshokReddy010/fund-proxy-voting.git
cd fund-proxy-voting
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python download_votes.py --test
python download_votes.py
python load_raw.py
dbt build --profiles-dir .
python scripts\export_results.py
python scripts\make_charts.py
```

`download_votes.py --test` is a ten-minute trial on a sample of filings. The full download can be stopped and restarted. To rebuild the proposal labels from scratch, run `scripts\export_proposals.py` and then `scripts\label_proposals.py`, and copy `proposal_labels.csv` into `seeds`.

## Limitations

- Reference votes cover 84% of fund votes. The other 16%, mostly smaller and non-US companies, rely on wording rules, which are less reliable.
- Wordings are matched within a company meeting by word overlap. Very differently worded copies of one proposal can stay separate, and two similar proposals at one meeting can merge.
- Where a filer sent a corrected filing for the same fund and year, the latest one is used. Corrections that cover only part of the original are not handled separately.
- A few filings report exactly 500,000 votes, which suggests a cap in how they were filed. This was not investigated.
- The comparison between an ESG-named fund and its siblings is made within one filer. Fund families that file through several legal entities are not joined together.

## Related work

[proxy-voting-panel](https://github.com/slriggss/proxy-voting-panel) studies the same filings for 22 selected funds and labels proposal direction with keyword rules. This project covers all 12,416 funds, adds the within-filer sibling comparison, and checks keyword labels against an independent signal.

## Tools

Python, DuckDB, dbt, BigQuery, Data Studio, pandas, Matplotlib, pytest, GitHub Actions, Groq API (open-weight LLM).

## Author

Ashok Reddy Bhimavarapu · [Portfolio](https://ashokreddy010.github.io) · [LinkedIn](https://www.linkedin.com/in/ashokreddy1)
