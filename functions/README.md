# functions

One OpenFaaS function per directory (`functions/<name>/`), each with a thin
`handler.py`, its logic in separate modules, a `requirements.txt`, and
co-located `tests/`. Directory names use underscores so they import as Python
packages; the deployed function names in `stack.yml` use hyphens.
