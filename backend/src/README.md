# backend/src/

"src layout": the importable package is `saathi/`. Keeping code under `src/` means tests run
against the installed package, not against whatever happens to be in the working directory.

- `saathi/main.py` - API entry (`uvicorn saathi.main:create_app --factory`)
- `saathi/worker.py` - background worker entry (`arq saathi.worker.WorkerSettings`)
- `saathi/platform/` - shared technical plumbing
- `saathi/modules/` - business modules
- `saathi/api/` - app-wide HTTP composition
- `saathi/bootstrap/` - dependency wiring
