# Research workspace

Reserved for experiments and reproducible evaluation. There are no ML dependencies,
notebooks, datasets, models, or inference features in this foundation.

- Use a separate dependency environment when experiments begin.
- Production code under apps/backend must never import research code.
- Do not add another application API or persistent application database here.
- Use synthetic fixtures or explicitly authorized, minimized research data.
- Keep learner records, recordings, datasets, checkpoints, and sensitive notebook
  outputs out of Git. Store protected data outside the repository.
- Record dataset/model provenance, licenses, experiment configuration, and seeds.
- Split evaluation by learner where appropriate to prevent train/test leakage.
- Research participation and data reuse require their own consent/governance process.
- Promote reviewed, tested components into the owning backend module explicitly.
- Educational performance estimates must not become medical diagnoses.
