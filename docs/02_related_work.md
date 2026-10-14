# Related work and novelty audit

Initial primary-source reading list, checked 2026-10-14. This is not an exhaustive
novelty review. No claim of being the first intent/execution model is established.

| Area | Source | Relation and comparison to develop |
| --- | --- | --- |
| Longitudinal EHR representation / Transformers | Li et al., [BEHRT: Transformer for Electronic Health Records](https://www.nature.com/articles/s41598-020-62922-y), Scientific Reports 10, 7155 (2020) | Architecture background; motivates a strong type-aware sequence comparator. Different clinical task, not a direct matched experiment. |
| EHR foundation models / survival pretraining | Steinberg et al., [MOTOR: A Time-To-Event Foundation Model For Structured Medical Records](https://arxiv.org/abs/2301.03150); [ICLR 2024 paper](https://openreview.net/pdf?id=NialiwI2V6) | Close methodological neighbor: TTE representation learning. Distinguish order-conditioned execution from generic multi-task survival. |
| Competing risks | Lee, Zame, Yoon, van der Schaar, [DeepHit](https://ojs.aaai.org/index.php/AAAI/article/view/11842), AAAI (2018) | Direct survival-method comparator candidate. Learns event-time distributions with competing outcomes; does not by itself establish the proposed intention/execution contribution. |
| Temporal events / neural point processes | Mei and Eisner, [The Neural Hawkes Process](https://proceedings.neurips.cc/paper_files/paper/2017/hash/6463c88460bd63bbe256e495c63aa40b-Abstract.html), NeurIPS (2017) | Marked-event baseline family; history-conditioned intensities are background, not a new contribution here. |
| Medication representation and external data | [MIMIC-IV v3.1 data documentation](https://physionet.org/content/mimiciv/3.1/) | Documents orders, prescriptions and eMAR as distinct sources. Dataset reference, not a modeling baseline; access requirements apply. |

Clinical workflow modeling and order-to-administration delay modeling still need a
targeted primary-literature search before selecting the method. Record search terms,
inclusion criteria, actual medication setting, links, input cutoffs, target labels,
censoring treatment, and the closest prior contribution in a comparison table.
Do not treat “uses a different event name” as a research gap. A substantive overlap
with a prior method is a redesign trigger, even if it appears after Phase 0.
