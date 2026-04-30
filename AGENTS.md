# MediaHunt - Agent Instructions

MediaHunt é um web app self-hosted para buscar torrents e legendas, rodando via Docker/Dockge/CasaOS em servidores domésticos.

## Regras principais

- Não hardcodar IP local.
- Não salvar secrets no git.
- Não commitar .env nem config.json real.
- Manter porta padrão 5556 via variável PORT.
- Manter config persistente em /app/data/config.json.
- O app deve continuar funcionando mesmo se uma fonte falhar.
- Erros de fonte devem aparecer como avisos amigáveis.
- Não tentar burlar Cloudflare, anti-bot ou bloqueios de sites.
- Não implementar qBittorrent ativo agora; apenas salvar configurações.
- Não implementar Jellyfin/Plex agora.

## Melhorias desejadas

- Corrigir tratamento de erro do YTS quando houver falha DNS.
- Tratar 1337x 403 como aviso amigável.
- Melhorar busca com aliases, normalização, sinônimos e nomes PT/EN.
- Adicionar fontes customizadas RSS/Torznab nas configurações.
- Atualizar README com Docker, Dockge, OpenSubtitles e troubleshooting.