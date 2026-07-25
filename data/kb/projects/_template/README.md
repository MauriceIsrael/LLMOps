# <Engagement name>

Instance directory. Contains only what is specific to this engagement: answers,
choices, deltas from the reusable core, and client-specific context.

```
answers/         copies of questionnaires with answers filled in
decisions/       engagement-local ADRs (candidates for promotion later)
deltas.md        where this engagement departs from the core, and why
claims.md        claims register (BID phase)
harvest/         one file per phase harvest
```

**Confidentiality:** this directory may carry client-identifying material. The
reusable core must not. Promotion out of here requires generalization.
