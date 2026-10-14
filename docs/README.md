<div align="center" markdown="1">

  [![Discord][badge-chat]][chat]
  <br>
  <br>

  | | ![Badges][label-badges] |
  |:-|:-|
  | ![Build][label-build] | [![Nox][badge-actions]][actions] [![semantic-release][badge-semantic-release]][semantic-release] [![PyPI][badge-pypi]][pypi] [![Read the Docs][badge-docs]][docs] |
  | ![Tests][label-tests] | [![coverage][badge-coverage]][coverage] [![pre-commit][badge-pre-commit]][pre-commit] [![asv][badge-asv]][asv] |
  | ![Standards][label-standards] | [![SemVer 2.0.0][badge-semver]][semver] [![Conventional Commits][badge-conventional-commits]][conventional-commits] |
  | ![Code][label-code] | [![uv][badge-uv]][uv] [![Ruff][badge-ruff]][ruff] [![Nox][badge-nox]][nox] [![Checked with mypy][badge-mypy]][mypy] |
  | ![Repo][label-repo] | [![GitHub issues][badge-issues]][issues] [![GitHub stars][badge-stars]][stars] [![GitHub license][badge-license]][license] [![All Contributors][badge-all-contributors]][contributors] [![Contributor Covenant][badge-code-of-conduct]][code-of-conduct] |
</div>

<!-- Badges -->
[badge-chat]: https://img.shields.io/badge/dynamic/json?color=green&label=chat&query=%24.approximate_presence_count&suffix=%20online&logo=discord&style=flat-square&url=https%3A%2F%2Fdiscord.com%2Fapi%2Fv10%2Finvites%2FYe9yJtZQuN%3Fwith_counts%3Dtrue
[chat]: https://discord.gg/Ye9yJtZQuN

<!-- Labels -->
[label-badges]: https://img.shields.io/badge/%F0%9F%94%96-badges-purple?style=for-the-badge
[label-build]: https://img.shields.io/badge/%F0%9F%94%A7-build-darkblue?style=flat-square
[label-tests]: https://img.shields.io/badge/%F0%9F%A7%AA-tests-darkblue?style=flat-square
[label-standards]: https://img.shields.io/badge/%F0%9F%93%91-standards-darkblue?style=flat-square
[label-code]: https://img.shields.io/badge/%F0%9F%92%BB-code-darkblue?style=flat-square
[label-repo]: https://img.shields.io/badge/%F0%9F%93%81-repo-darkblue?style=flat-square

<!-- Build -->
[badge-actions]: https://img.shields.io/github/actions/workflow/status/MicaelJarniac/pyktane/ci.yml?branch=main&style=flat-square
[actions]: https://github.com/MicaelJarniac/pyktane/actions
[badge-semantic-release]: https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079?style=flat-square
[semantic-release]: https://github.com/semantic-release/semantic-release
[badge-pypi]: https://img.shields.io/pypi/v/pyktane?style=flat-square
[pypi]: https://pypi.org/project/pyktane
[badge-docs]: https://img.shields.io/readthedocs/pyktane?style=flat-square
[docs]: https://pyktane.readthedocs.io

<!-- Tests -->
[badge-coverage]: https://img.shields.io/codecov/c/gh/MicaelJarniac/pyktane?logo=codecov&style=flat-square
[coverage]: https://codecov.io/gh/MicaelJarniac/pyktane
[badge-pre-commit]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=flat-square&logo=pre-commit&logoColor=white
[pre-commit]: https://github.com/pre-commit/pre-commit
[badge-asv]: https://img.shields.io/badge/benchmarked%20by-asv-blue?style=flat-square
[asv]: https://github.com/airspeed-velocity/asv

<!-- Standards -->
[badge-semver]: https://img.shields.io/badge/SemVer-2.0.0-blue?style=flat-square&logo=semver
[semver]: https://semver.org/spec/v2.0.0.html
[badge-conventional-commits]: https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow?style=flat-square
[conventional-commits]: https://conventionalcommits.org

<!-- Code -->
[badge-uv]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=flat-square
[uv]: https://github.com/astral-sh/uv
[badge-ruff]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square
[ruff]: https://github.com/astral-sh/ruff
[badge-nox]: https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg?style=flat-square
[nox]: https://github.com/wntrblm/nox
[badge-mypy]: https://img.shields.io/badge/mypy-checked-2A6DB2?style=flat-square
[mypy]: http://mypy-lang.org

<!-- Repo -->
[badge-issues]: https://img.shields.io/github/issues/MicaelJarniac/pyktane?style=flat-square
[issues]: https://github.com/MicaelJarniac/pyktane/issues
[badge-stars]: https://img.shields.io/github/stars/MicaelJarniac/pyktane?style=flat-square
[stars]: https://github.com/MicaelJarniac/pyktane/stargazers
[badge-license]: https://img.shields.io/github/license/MicaelJarniac/pyktane?style=flat-square
[license]: https://github.com/MicaelJarniac/pyktane/blob/main/LICENSE
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[badge-all-contributors]: https://img.shields.io/badge/all_contributors-0-orange.svg?style=flat-square
<!-- ALL-CONTRIBUTORS-BADGE:END -->
[contributors]: #Contributors-✨
[badge-code-of-conduct]: https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa?style=flat-square
[code-of-conduct]: CODE_OF_CONDUCT.md
<!---->

# PyKTANE

Welcome to **PyKTANE's** documentation!

Solvers for [*Keep Talking and Nobody Explodes*](https://keeptalkinggame.com):
you describe the bomb, **PyKTANE** reads the manual. It only asks for what a
rule actually needs, tracks strikes and per-module state, supports undo, and
can be extended with modded module packs.

It also ships an optional [MCP](https://modelcontextprotocol.io) server, so an
AI assistant can play the expert for you.

[Read the Docs][docs]

## Installation

### PyPI
[*pyktane*][pypi] is available on PyPI:

```bash
# With uv
uv add pyktane
# With pip
pip install pyktane
# With Poetry
poetry add pyktane
```

For the MCP server, add the `mcp` extra: `pyktane[mcp]`.

### GitHub
You can also install the latest version of the code directly from GitHub:
```bash
# With uv
uv add git+https://github.com/MicaelJarniac/pyktane
# With pip
pip install git+git://github.com/MicaelJarniac/pyktane
# With Poetry
poetry add git+git://github.com/MicaelJarniac/pyktane
```

## Usage
For more examples, see the [full documentation][docs].

### As a library

```python
from pyktane import NeedsInfo, Session

bomb = Session()
simon = bomb.add_module("Simon Says")
try:
    bomb.solve(simon, {"flashes": ["red", "green"]})
except NeedsInfo as missing:
    print(missing.fact.question)  # What is the serial number?

bomb.set_fact("serial", "AB3CD4")
bomb.solve(simon, {"flashes": ["red", "green"]}).instruction  # 'Press blue, yellow.'
bomb.strike()  # Simon Says changes with strikes.
bomb.solve(simon, {"flashes": ["red", "green"]}).instruction  # 'Press yellow, blue.'
```

Mistakes can be fixed wherever they happened, not just undone:

```python
wires = bomb.add_module("Wires")
bomb.solve(wires, {"wires": ["red"] * 6})
bomb.correct(wires, {"wires": ["red"] * 5})  # "6 wires... wait, 5"

bomb.set_fact("serial", "AB3CD5")  # Misheard? Fixed from the start.

for entry in bomb.history:  # "That wasn't a strike": find it,
    print(entry.describe())  # e.g. "3: strike"
revision = bomb.remove_action(3)  # remove just that action,
for change in revision.changed:  # and hear which answers were wrong.
    print(change.instance, change.before.instruction, "->", change.after.instruction)
    # Simon#1 Press yellow, blue. -> Press blue, yellow.

bomb.undo()  # Every change, corrections included, can be undone.
```

Every module in the base game is supported: Wires, The Button, Keypads,
Simon Says, Who's on First, Memory, Morse Code, Complicated Wires, Wire
Sequences, Mazes and Passwords, plus the needy Venting Gas, Capacitor
Discharge and Knobs. Their rules are checked against the official manual
(v1, verification code 241).

### With an AI assistant (MCP)

Add this to your MCP client's configuration (Claude Desktop, Claude Code,
Cursor, opencode...):

```json
{
  "mcpServers": {
    "pyktane": {
      "command": "uvx",
      "args": ["--from", "pyktane[mcp]", "pyktane-mcp"]
    }
  }
}
```

Then ask your assistant to be the expert, or use the server's `defuse`
prompt. It records the edgework, asks you what it needs, and tells you what
to do.

| Tool | What it does |
|---|---|
| `new_bomb` | Start a new round |
| `get_bomb` | Facts, strikes and modules so far |
| `list_facts` / `set_facts` | What can be recorded about the bomb, and recording it |
| `list_modules` / `describe_module` | Supported modules, and what to report for each |
| `add_module` / `solve` | Add a module, then get the answer (or a question to ask first) |
| `strike` / `mark_solved` | Keep the bomb's state in sync; `mark_solved` takes a module name when the defuser solved it alone |
| `solve` with `correction: true` | Replace a module's misread report |
| `get_history` / `edit_history` | Find and fix any past mistake (a strike that wasn't one, ...) |
| `forget_fact` / `remove_module` / `undo` | Take back facts, modules, or the latest change |

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

More details can be found in [CONTRIBUTING](CONTRIBUTING.md).

## Contributors ✨
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License
[MIT](../LICENSE)

This project was created with the [MicaelJarniac/crustypy](https://github.com/MicaelJarniac/crustypy) template.
