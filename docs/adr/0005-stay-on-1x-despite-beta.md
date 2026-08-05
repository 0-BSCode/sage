# Stay on the 1.x version line despite beta maturity

The plugin shipped as 1.0.x from its first release, but the product is still beta — semver convention would put it at 0.x, where anything may change. We decided to stay on 1.x anyway: `1.0.2` is already installed in the wild, and retreating to 0.x would make every future version sort *before* the installed one in any tooling that compares versions. Instead, the 1.x line is treated as young — patch bumps are used liberally, and 1.x does not yet carry the full stability promise semver implies. The compatibility rules that make this workable (what counts as breaking, what's internal) are in the sage repo's `docs/RELEASING.md`.

We considered two alternatives:

- **Go 0.x** — the honest semver signal. Rejected: version ordering breaks for existing installs.
- **Declare 1.x fully stable** — rejected: it would force major-bump ceremony on a product still changing shape.
