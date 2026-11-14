# modules/tenancy

Owns: `tenant`, `bot`, `user_account`, `bot_config_versions` (Bot Studio). Phases 1, 4, 5.

| Layer | File | Responsibility |
|---|---|---|
| domain | `entities.py` | Tenant/Bot rules (supported languages, name rules) - pure Python |
| application | `services.py` | Use cases: create bot, get bot (role checks here) |
| ports | `repositories.py` | `BotRepository` interface |
| adapters | `orm.py`, `repository.py` | SQLAlchemy tables + repository implementation |
| api | `routes.py`, `schemas.py` | `/api/v1/bots` endpoints + request/response DTOs |

## Bot Studio configuration

| Layer | File | Responsibility |
|---|---|---|
| domain | `bot_config.py` | `PromptSettings`, `GenerationSettings` (presets + advanced), `Branding`, immutable `BotConfigVersion` (draft -> published -> archived) |
| application | `config_service.py` | save draft, publish, roll back, list versions, model options per plan; public widget config |
| ports | `repositories.py` | `BotConfigRepository`, `TenantRepository`, `PublicBotLookup` |
| adapters | `config_repository.py`, `config_mapper.py`, `public_lookup.py` | versions table, JSON mapping, SECURITY DEFINER key lookup |
| api | `config_routes.py`, `public_routes.py` | `/api/v1/bots/{id}/config/...`, `/api/v1/model-options`, `/public/v1/widgets/{key}/config` |
