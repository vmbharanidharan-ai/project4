# project3 puzzle toolkit

Small helper to map and probe the `carlodoroff.com` puzzle flow.

## quick start

```bash
python3 -m pip install requests
python3 project3/puzzle_solver.py --probe-claims --probe-guestbook
```

## what it does

- Fetches `/, /rabbit, /cra-0004, /signal, /signal.json` by default.
- Saves raw page responses under `project3/out/pages/`.
- Extracts:
  - `__puzzle.claim("level", "answer")`
  - `__puzzle.mark("key")`
  - HTML comments
  - route-like strings
  - candidate base64/hex strings
- Writes reports:
  - `project3/out/report.json`
  - `project3/out/report.md`
- Optional probes:
  - `--probe-claims` to test discovered level/answer pairs
  - `--probe-guestbook` to inspect server missing-level responses

## extra manual probes

Add known or guessed pairs:

```bash
python3 project3/puzzle_solver.py \
  --probe-claims \
  --probe L4_ship:SHIP \
  --probe L6_carlo:CARLO
```
