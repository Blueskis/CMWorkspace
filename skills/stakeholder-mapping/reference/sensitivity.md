# Sensitivity: handling informal relationship data

A stakeholder map of informal ties records what named employees said about colleagues and managers, usually in confidence. In Singapore government and GLC engagements that falls under the PDPA and the client's own confidentiality terms. Treat the master map like interview notes, not like a slide.

1. **Two copies.** The master `stakeholder_map.json` carries real names and stays with the CM team. Anything shown on a shared screen, sent to a client or loaded into a workshop is built with `--pseudonymise`, which replaces every name (and nicknames, and name fragments inside quotes) with `Person-NN`. Keep `pseudonym_key.json` private.
2. **QA before showing.** `qa_map.py map_shared.json --key pseudonym_key.json` fails the run if any real name survives. Do not skip it.
3. **The viewer says which copy it holds.** The header chip reads "Names pseudonymised" or "Names visible: do not screen-share".
4. **The viewer holds no client data.** The published page contains only a fictional example. A real map is opened from a local file and never uploaded.
5. **Ask sends data to Claude.** Questions send the selected group's summary and evidence to the model through the viewer's own account. For a map with real names, treat that as a data-protection decision for the client, the same as cloud transcription in the CIA skill. Use the pseudonymised copy if in doubt.
6. **Quotes can identify.** A pseudonymised quote can still point to one person ("the only night supervisor"). Read the quotes in the shared copy before it leaves the team.
7. **Speaker field is a role.** Record `speaker` as a role ("Head of Planning"), not a name, so the shared copy does not depend on scrubbing.
