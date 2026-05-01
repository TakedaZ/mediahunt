# MediaHunt

MediaHunt é um buscador self-hosted de torrents e legendas.

## Docker Compose / Dockge

```yaml
services:
  mediahunt:
    build: .
    ports:
      - "${PORT:-5556}:5556"
    environment:
      PORT: "${PORT:-5556}"
      MEDIAHUNT_DATA_DIR: "/app/data"
    dns:
      - 1.1.1.1
      - 8.8.8.8
    volumes:
      - mediahunt_data:/app/data
```

Suba com:

```bash
docker compose up -d --build
```

Acesse em `http://IP_DO_SERVIDOR:5556`.

## OpenSubtitles

Use `OPENSUBTITLES_API_KEY` no `.env` ou em Configurações. Sem API key, o app mostra aviso amigável.

## Fontes RSS/Torznab customizadas

Em **Configurações → Fontes customizadas** você pode cadastrar:
- Nome
- Tipo (RSS genérico / Torznab)
- URL base
- Ativo/desativo
- Categorias (Filme/Série/Anime)

Você pode adicionar fontes RSS ou Torznab compatíveis com Prowlarr/Jackett. Para encontrar fontes, procure pelo nome do indexador + RSS ou Torznab. Algumas fontes exigem API key ou login. Use apenas fontes que você tenha permissão para acessar.

## Troubleshooting

- Erro DNS no Docker (YTS/Nyaa): configure DNS públicos no compose (`1.1.1.1`, `8.8.8.8`).
- 1337x 403: o app mostra aviso amigável e continua nas outras fontes.

Limpar imagens antigas:

```bash
docker image prune -a -f
```
