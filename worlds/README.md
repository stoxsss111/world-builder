# `worlds/` — build outputs

Each subfolder is one built world. Created by `build-world` skill.

```
worlds/
├── _examples/           # example scenarios checked into git (not real builds)
│   └── banjo-island/    # the seed brief — see prompts.md
└── <world-slug>/        # real builds — gitignored except for _examples
    ├── source/reference.png
    ├── plan.json
    ├── assets/
    ├── iterations/
    ├── final.blend
    ├── final.render.png
    └── cost.json
```

See `docs/PIPELINE.md` for the full layout and what each file contains.

`worlds/*/` is git-ignored by default (see `.gitignore`); only `_examples/` is committed.
