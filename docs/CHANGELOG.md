# CHANGELOG

<!-- version list -->

## v0.5.0 (2026-10-14)

### Features

- Tune the MCP server for voice play
  ([`e754d7e`](https://github.com/MicaelJarniac/pyktane/commit/e754d7e0693168ca4459ce780dd3753cac686d68))

### Breaking Changes

- MCP write tools (set_facts, forget_fact, remove_module, strike, mark_solved, edit_history) return
  `{done, strikes, unsolved, changed}` instead of the full bomb summary, and `undo` returns
  `{undone, strikes, unsolved}`; call `get_bomb` for the full state. `add_module` returns `{id,
  name, needy, guide, examples}`. `solve`'s `needs_fact` result has `facts` (a list) and `partial`
  instead of `fact`. Complicated Wires asks for `has_parallel_port` instead of `port_plates`.


## v0.4.1 (2026-10-14)

### Bug Fixes

- Let defusers report self-solved modules, and never solve needy ones
  ([`6338209`](https://github.com/MicaelJarniac/pyktane/commit/6338209198e39215e8ea8791832cd349254f31c9))

### Continuous Integration

- Keep pre-commit off the saved copy of the official manual
  ([`02ad8bd`](https://github.com/MicaelJarniac/pyktane/commit/02ad8bd28de38bedc0f66a4a71a87793cc16088c))


## v0.4.0 (2026-10-14)

### Features

- Support every vanilla module, checked against the official manual
  ([`37ad422`](https://github.com/MicaelJarniac/pyktane/commit/37ad422632710e89bd3a95238d6890d7ed87c2ef))


## v0.3.0 (2026-10-13)

### Documentation

- Record and verify the manual source for every module
  ([`4bb9446`](https://github.com/MicaelJarniac/pyktane/commit/4bb944642cd28823d0e01f04f5b48032f2a96ae1))

### Features

- Fix any past mistake by replaying an action log
  ([`f57a706`](https://github.com/MicaelJarniac/pyktane/commit/f57a706253f7b9121b3ff8aa77489815e5f2d8ac))

### Breaking Changes

- Saves use format_version 2 (the action log plus undo splices); version 1 saves no longer load.
  `Session(manual, actions)` takes actions instead of snapshots, `Session.history` returns
  HistoryEntry items, changing methods return a Revision, `BombState.solve_order` holds instance
  IDs, and the MCP `set_facts`/`strike`/`mark_solved` tools return `{bomb, changed}` instead of the
  bare bomb summary.


## v0.2.0 (2026-10-13)

### Features

- Add The Button and an optional MCP server
  ([`a836997`](https://github.com/MicaelJarniac/pyktane/commit/a8369971b496fe6d1cd9bf81ad60475e019d2b98))


## v0.1.1 (2026-10-13)

### Bug Fixes

- Expose every input constraint in JSON schemas
  ([`fcaa2ee`](https://github.com/MicaelJarniac/pyktane/commit/fcaa2ee449979a4076af5fe7d21f87a8fde9b0ba))


## v0.1.0 (2026-10-13)

### Chores

- Port template improvements from repeaterbook
  ([`876d955`](https://github.com/MicaelJarniac/pyktane/commit/876d9551ecc7ac15623424dc55f8aed67e74b320))

- **lint**: Ignore CPY001
  ([`cf2e579`](https://github.com/MicaelJarniac/pyktane/commit/cf2e57972c4ad269c30f0c1f8ae8ff3cab7acf85))

### Features

- Add core solver framework with vanilla Wires, Simon Says and Memory
  ([`bd6e41b`](https://github.com/MicaelJarniac/pyktane/commit/bd6e41bd30c8e5732f20b271d0e1944fad0ed102))


## v0.0.0 (2026-10-13)
