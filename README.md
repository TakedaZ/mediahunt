# MediaHunt

**MediaHunt** é um buscador integrado de torrents e legendas com interface
web moderna, pensado para rodar em servidores domésticos como
**CasaOS**, **Unraid**, **TrueNAS**, ou em qualquer host com Docker.

- Buscas em **YTS**, **Nyaa.si** e **1337x** com filtros de tipo, idioma e qualidade
- Busca de legendas via **OpenSubtitles REST API**
- Configurações persistentes (`config.json`) em volume Docker
- Interface dark estilo Plex/Sonarr, responsiva e em português ou inglês

> Aviso: MediaHunt apenas indexa fontes públicas. O download e o uso de
> conteúdo protegido por direitos autorais é de responsabilidade exclusiva
> do usuário. Respeite as leis da sua região.

## Stack

- Backend: **FastAPI** (Python 3.11)
- Frontend: **React 19** + Tailwind + shadcn/ui (build estático servido pelo backend)
- Banco de dados: **MongoDB** (persistência das configurações)
- Container único: backend + frontend estático na porta `5556`

## Como obter a API key do OpenSubtitles (gratuita)

1. Crie uma conta em <https://www.opensubtitles.com>.
2. Acesse <https://www.opensubtitles.com/consumers> e clique em **"New Consumer"**.
3. Preencha nome do app (ex.: `MediaHunt`) e descrição.
4. Copie a chave (**API Key**) gerada.
5. Cole a chave em `.env` (`OPENSUBTITLES_API_KEY=...`) **ou** em
   `Configurações → API Keys` no app. Use *"Testar conexão"* para validar.

## Deploy com Docker

```bash
git clone <seu-fork> mediahunt && cd mediahunt
cp .env.example .env   # opcional, ajuste PORT/OPENSUBTITLES_API_KEY
docker compose up -d --build
# Acesse http://localhost:5556
```

Configurações persistem no volume `mediahunt_data` (montado em `/app/data`).

### Variáveis de ambiente

| Variável                | Padrão       | Descrição                                                |
| ----------------------- | ------------ | -------------------------------------------------------- |
| `PORT`                  | `5556`       | Porta exposta pelo container                             |
| `OPENSUBTITLES_API_KEY` | *(vazio)*    | Chave OpenSubtitles                                      |
| `MONGO_URL`             | (auto)       | Definido pelo compose                                    |
| `DB_NAME`               | `mediahunt`  | Nome do banco                                            |
| `CORS_ORIGINS`          | `*`          | Origens permitidas                                       |

## Endpoints da API

| Método | Path                            | Descrição                                                                      |
| ------ | ------------------------------- | ------------------------------------------------------------------------------ |
| GET    | `/api/search/torrents`          | params: `query`, `type`, `language`, `quality`, `max_results`                  |
| GET    | `/api/search/subtitles`         | params: `query`, `language`                                                    |
| GET    | `/api/subtitles/download`       | param: `file_id`                                                               |
| GET    | `/api/torrent/proxy`            | param: `url` (proxy para `.torrent`)                                           |
| GET    | `/api/settings`                 | Retorna configurações                                                          |
| POST   | `/api/settings`                 | Atualiza configurações                                                         |
| GET    | `/api/settings/test-connection` | Testa a API key do OpenSubtitles                                               |

## Roadmap (futuro)

- Integração ativa com qBittorrent
- Histórico de buscas
- Integração com Jellyfin / Plex

## Licença

MIT — uso por sua conta e risco.
