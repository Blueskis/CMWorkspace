"""deckkit — the parts of the deck pipeline that are not specific to one skill.

`cm-proposal-generator` and `training-material-generator` build different documents from
different sources, but they share three mechanics exactly:

  * `template_profile` — what layouts a template has and what each one can hold
  * `manifest`         — validating a plan against that profile and sequencing the build
  * `htmlkit`          — filling a layout's {{tokens}} for the HTML render target

Those live here so the two skills cannot drift apart. A plan written by either skill is
checked against a template by the same code, which is what makes the HTML and .pptx render
targets interchangeable.

Stdlib only, like everything else in this repo. Each skill's scripts/ keeps its own CLI
entry points; this package holds no argument parsing and prints nothing.
"""

__all__ = ["template_profile", "manifest", "htmlkit"]
