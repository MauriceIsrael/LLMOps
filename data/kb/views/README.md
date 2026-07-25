# Views as code

Diagram generators. A new engagement reuses a generator and changes labels; it
does not redraw.

```
lib/            shared drawing helpers (SVG and drawio emitters)
generators/     one script per view family
```

Rendered outputs are not committed except when attached to a released document,
in which case they live in the project instance alongside the document they
illustrate.
