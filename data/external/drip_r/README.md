---
task_categories:
- text-generation
language:
- en
tags:
- agent
- benchmarking
- policy-adherence
size_categories:
- n<1K
---



# DRIP-R: Decision-making and Reasoning In ambiguous Policy for Retail

[📄 Paper (arXiv:2605.07699)](https://arxiv.org/abs/2605.07699) ·  [💻 Code](https://github.com/ITU-NLP/drip-r-bench)

## Dataset Summary

DRIP-R is a benchmark for evaluating LLM customer-service agents when the governing policy is ambiguous. It pairs 40 return tasks, each built on at least one ambiguous clause of Amazon's return policy so that no single resolution is "correct", with 10 customer personas, giving 400 scenarios.

## Dataset at a Glance


| Attribute       | Value                                                                                                       |
|-----------------|-------------------------------------------------------------------------------------------------------------|
| Domain          | Retail order returns (Amazon return policy + one related third-party-seller policy)                         |
| Scenarios       | 400 (10 personas × 40 tasks)                                                                                |
| Tasks           | 40                                                      |
| Personas        | 10                                                                                      |
| Task complexity | Very High: 23 · High: 16 · Medium: 1                                                                        |
| Ambiguity types | Vagueness, Coordination Ambiguity, Incompleteness, Missing Condition, Semantic Ambiguity (about 3 per task) |
| Outcome space   | 7 categories; **no gold label by design**                                                                   |
| Language        | English                                                                                                     |
| Origin          | Synthetic (LLM-generated, human-validated)                                                                  |


## Supported Tasks and Evaluation

The intended use is to simulate a customer–agent conversation (agent has tool access) and score the agent's behavior and final resolution. The paper's judge pipeline scores five dimensions (policy adherence, dialogue quality, behavioral alignment, task-resolution adherence, interest alignment) and classifies each resolution into one of seven outcomes: Full Refund, Partial Refund, Refund with Gift Card, Deny Refund, Replacement, Escalate to Human, User Abort.

> Headline result from the paper: across four frontier models, only 4.2% of scenarios ended in the same resolution for all four models.

## Dataset Structure

### Repository files


| File              | Config                | Records | Contents                                                                                      |
|-------------------|-----------------------|---------|-----------------------------------------------------------------------------------------------|
| `scenarios.jsonl` | `scenarios` (default) | 400     | Full simulation inputs: policy text + persona + task + opening customer message + role briefs |
| `tasks.jsonl`     | `tasks`               | 40      | Ambiguity-grounded return tasks                                                               |
| `personas.jsonl`  | `personas`            | 10      | Synthetic customer personas                                                                   |

### Data Instances

**Task** (`tasks`, long strings truncated with `…`):

```json
{
  "task_id": "task_000",
  "is_stratified": true,
  "stratified_task_idx_aliases": ["task_000"],
  "detail": "Customer purchased the \"OmniPro Wireless Security Camera System (2 Cameras, 1 Hub)\" and the \"SafePad Outdoor Power Extension Cable\" in a single order. The extension cable was delivered one week later than the cameras due to a carrier delay. … The customer requires a swift resolution due to scheduled travel in three days, and is conflicted whether to seek a replacement (if eligible) for only the malfunctioning camera or an exchange for a different model.",
  "reason": "Customer needs clarity on return window for delayed partial shipment, eligibility and degree of refund for opened/used and sealed items, reconciliation of used item condition, and bundle rebate calculation—plus replacement versus exchange options.",
  "task": "Order with mixed delivery dates and item conditions (one camera used/opened, others sealed, extension cable unopened) is subject to return request involving timing, condition, refund calculation, and product swap ambiguities.",
  "related_policy_issues": "[\"No specifics on what constitutes 'certain circumstances' warranting a longer refund timeframe.\", \"Borderline scenarios (such as limited item use, light wear, or opened packaging) are not addressed, resulting in workflow friction for return eligibility determination.\", …]",
  "complexity_level": "Very High Complexity",
  "complexity_ordinal": 4,
  "primary_ambiguity_type": "Coordination Ambiguity",
  "all_ambiguity_types": "[\"Coordination Ambiguity\", \"Incompleteness\", \"Vagueness\"]",
  "stratum_label": "Coordination Ambiguity__High"
}

```

**Persona** (`personas`):

```json
{
  "Name": "Janet Rogers",
  "Age-range": "45-50",
  "Location": "United States",
  "Gender": "Female",
  "Job Sector": "Nutrition",
  "Income range": "60,000-80,000 USD",
  "Person description": "Janet is the nutrition director for a mid-sized county school district. She is committed to providing healthy, balanced meals to students and is an expert in school nutrition policy, compliance, and federal regulations. …",
  "Language Style": "Terse",
  "Personality Style": "{'Openness': 2, 'Conscientiousness': 2, 'Extraversion': 2, 'Agreeableness': 2, 'Neuroticism': 3}",
  "Communication style": "Dismissive",
  "Persona_id": "Janet_Nutrition_USA_01"
}

```

**Scenario** (`scenarios`, this is `task_000` × Janet; policy text truncated):

```json
{
  "scenario_id": "Janet_t000_47a3",
  "task_id": "task_000",
  "source": "427",
  "Policy": {
    "Primary Policy": {"url": null, "text": "Amazon Return Policy\nEasy shopping, simple returns - that's our promise. …"},
    "Related policies": [{"url": null, "text": "Returns to Third-Party Sellers\nWhen you order from a third-party seller that fulfills and ships its own inventory, … "}]
  },
  "persona": { /* all fields of the persona record above */ },
  "task": { /* all fields of the task record above, except task_id / is_stratified / aliases */ },
  "first_customer_message": "Hi, I need to return the cameras from my order. One of them doesn’t work with my Wi-Fi, I think I messed up the setup a bit, but the other one and the extension cord are sealed. I'm not sure about the return timing for the extension, since it came later. Can you help with that?",
  "detail_agent": "Customer wants to return the cameras from their order and is asking about the return timing for the extension cord.",
  "customer_task_detail": {
    "basic_info": "Customer ordered the 'OmniPro Wireless Security Camera System (2 Cameras, 1 Hub)' and the 'SafePad Outdoor Power Extension Cable.' The cameras were delivered first, and the extension cable arrived a week later due to a delay.",
    "private_info": "One camera was opened and set up, revealing it doesn't support the local Wi-Fi frequency. It was then repacked with minor signs of use. The second camera and hub are unopened, while the extension cable box is also unopened.",
    "behavior": "Customer withholds details about the specific status of the used camera and their uncertainty about eligibility for returning opened items until an agent inquires about the setup process or details surrounding the condition of each item."
  }
}

```

### Data Fields

#### Task

| Field                          | Type                       | Description                                                                 |
|--------------------------------|----------------------------|-----------------------------------------------------------------------------|
| `task_id`                      | string                     | e.g. `task_000`; `task_E01`–`task_E06` are additional, non-stratified tasks |
| `is_stratified`                | bool                       | Drawn from stratified selection (true) or additional task (false)           |
| `stratified_task_idx_aliases`  | list[string]               | Original stratified indices collapsed into this task during de-duplication  |
| `detail`                       | string                     | Full narrative of the customer's return situation                           |
| `reason`                       | string                     | Short summary of the customer's concern                                     |
| `task`                         | string                     | One-line classification of the return type                                  |
| `related_policy_issues`        | string (JSON-encoded list) | Policy ambiguities this task depends on                                     |
| `complexity_level`             | string                     | Medium, High, or Very High Complexity                                       |
| `complexity_ordinal`           | int                        | Numerical complexity level (see note on ordinals)                           |
| `primary_ambiguity_type`       | string                     | Main ambiguity type targeted                                                |
| `all_ambiguity_types`          | string (JSON-encoded list) | All ambiguity types present                                                 |
| `stratum_label`                | string                     | Primary ambiguity type + diversity tier used for stratified sampling       |


#### Persona
| Field                 | Description                                                |
|-----------------------|------------------------------------------------------------|
| `Name`                | Persona name                                               |
| `Age-range`           | Age range of the persona                                   |
| `Location`            | Geographic location                                        |
| `Gender`              | Gender of the persona                                      |
| `Job Sector`          | Employment sector                                          |
| `Income range`        | Income range of the persona                                |
| `Person description`  | Narrative description of the persona                       |
| `Language Style`      | Joos' Five Clocks language register                        |
| `Personality Style`   | Big Five traits (1–5), stored as a Python-dict string      |
| `Communication style` | Preferred communication style                              |
| `Persona_id`          | Unique persona identifier                                  |


#### Scenario

| Field                    | Description                                                                                                      |
|--------------------------|------------------------------------------------------------------------------------------------------------------|
| `scenario_id`            | Persona first-name token + task index + short hash; use `persona.Persona_id` for identification of "Dr." personas |
| `task_id`                | Links to `tasks.task_id`                                                                                         |
| `source`                 | Internal provenance marker (`"427"` or `"516_extra"`) <!-- TODO: explain or drop -->                               |
| `Policy`                 | `Primary Policy` and `Related policies`: full policy text repeated in every record                               |
| `persona`                | Embedded copy of the persona record                                                                              |
| `task`                   | Embedded copy of the task record                                                                                 |
| `first_customer_message` | LLM-generated opening message that seeds the conversation                                                       |
| `detail_agent`           | Brief, CRM-style framing of the request given to the agent                                                       |
| `customer_task_detail`   | Customer-simulator briefing: `basic_info` (shared), `private_info` (withheld until asked), `behavior` (strategy)   |


### Data Splits

One `train` split per config. DRIP-R is an evaluation benchmark and has no train/validation/test partition.

## Dataset Creation

### Source Data

-   **Policy:** Amazon's public return policy and its "Returns to Third-Party Sellers" page. <!-- TODO: add retrieval date; the text references the 2025 holiday window -->
-   **Products:** two or three items per task sampled from an open Amazon product-description dataset on Hugging Face (no product combination reused).
-   **Personas:** drawn from PersonaHub (Ge et al., 2024), then augmented with Big Five traits, communication style, language register, and demographics.


### Annotations

Three expert annotators validated task realism and plausible outcomes (10 tasks; annotators disagreed on at least one outcome for 9 of them, which is evidence of genuine ambiguity) and labeled conversations to calibrate the LLM judge. **These annotations are not included in this release.**

### Personal and Sensitive Information

All persona attributes are synthetic. 

## Considerations

### Intended Use

Evaluating how LLM agents interpret, justify, and act on ambiguous policies. It is intended as an evaluation benchmark; avoid mixing it into training data.

### Out-of-Scope Use

Not a source of "correct" return decisions and not validated for production customer-service deployment.

### Avoid Evaluation Leakage

The evaluated agent should see only `Policy`, `detail_agent`, and the simulated customer's messages. The `task` object (especially `related_policy_issues`) and `customer_task_detail.private_info` are designer/simulator-side information and should not be shown to the agent.




## Usage

```python
import ast, json
from datasets import load_dataset

scenarios = load_dataset("hsuvaskakoty/DRIP-R", "scenarios", split="train")
tasks     = load_dataset("hsuvaskakoty/DRIP-R", "tasks", split="train")
personas  = load_dataset("hsuvaskakoty/DRIP-R", "personas", split="train")

row = scenarios[0]
print(row["first_customer_message"])
print(json.loads(row["task"]["all_ambiguity_types"]))
print(ast.literal_eval(row["persona"]["Personality Style"]))

```

## Additional Information


### Citation

```bibtex
@misc{borkakoty2026dripr,
  title         = {{DRIP-R}: A Benchmark for Decision-Making and Reasoning Under Real-World Policy Ambiguity in the Retail Domain},
  author        = {Borkakoty, Hsuvas and Pohl, Sebastian and Wang, Cheng and Chen, Bei and Hou, Yufang},
  year          = {2026},
  eprint        = {2605.07699},
  archivePrefix = {arXiv}
}

```

### Authors and Contact

Hsuvas Borkakoty*, Sebastian Pohl* (*equal contribution), Cheng Wang, Bei Chen, Yufang Hou. IT:U Interdisciplinary Transformation University Austria; Amazon, Berlin. Contact: hsuvas.borkakoty@it-u.at

### Acknowledgements

Funded by the RobustLLMAgents project in partnership with Amazon Science, Berlin.

### Version

v1.0.0