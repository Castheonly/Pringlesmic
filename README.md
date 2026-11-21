# Pringlesmic — Clipping automático para TikTok y Facebook

Toma videos largos (YouTube, podcasts, streams), encuentra los mejores momentos con IA,
los convierte en clips verticales 9:16 con subtítulos animados y los publica solos en
tus cuentas de **TikTok** y tus **páginas de Facebook (Reels)**.

**No necesitas tener el computador prendido.** Todo corre gratis en la nube con
**GitHub Actions** cada 6 horas.

```
 Canal de YouTube ──► yt-dlp descarga el video nuevo
                          │
                          ▼
                 faster-whisper transcribe (con tiempos por palabra)
                          │
                          ▼
                 Claude elige los 3 mejores momentos + título, caption y hashtags
                          │
                          ▼
                 ffmpeg: corte, formato vertical 1080x1920, subtítulos tipo karaoke
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
     TikTok (API oficial)     Facebook Reels (Graph API)
```

## Costos

| Pieza | Costo |
|---|---|
| GitHub Actions | Gratis en repos públicos; 2.000 min/mes gratis en privados |
| Transcripción (Whisper local) | Gratis |
| Claude (elegir momentos) | Unos centavos de dólar por video |
| APIs de TikTok y Facebook | Gratis |

## Configuración (una sola vez)

### 1. Ajusta `config.yaml`
Pon tus canales en `sources`, cuántos clips quieres por video, su duración, el estilo de los subtítulos, etc.

> ⚠️ Usa solo contenido tuyo o que tengas permiso para recortar. TikTok y Facebook bajan
> (y pueden banear) cuentas que suben contenido ajeno sin derechos.

### 2. Crea los *secrets* en GitHub
En el repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Qué es |
|---|---|
| `ANTHROPIC_API_KEY` | Tu API key de https://console.anthropic.com |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | De tu app en https://developers.tiktok.com |
| `TIKTOK_ACCOUNTS_JSON` | Lista de cuentas: `[{"name":"cuenta1","refresh_token":"..."}, {"name":"cuenta2","refresh_token":"..."}]` |
| `FACEBOOK_PAGES_JSON` | Lista de páginas: `[{"name":"MiPagina","page_id":"123","access_token":"..."}]` |
| `YT_COOKIES` *(opcional)* | Cookies de YouTube en formato Netscape, si YouTube bloquea las descargas |

Puedes tener **varias cuentas de TikTok y varias páginas de Facebook**: el mismo clip se sube a todas.

### 3. TikTok: crea tu app de desarrollador
1. Entra a https://developers.tiktok.com → *Manage apps* → crea una app.
2. Agrega el producto **Content Posting API** y los permisos `video.upload` (y `video.publish` si quieres publicar directo).
3. Autoriza cada cuenta con el flujo OAuth (Login Kit) y guarda el `refresh_token` de cada una (dura 365 días).
4. Modos en `config.yaml → publish.tiktok.mode`:
   - `inbox` *(por defecto)*: el video llega como **borrador** a la app de TikTok y tú solo tocas "Publicar". Funciona sin que TikTok audite tu app.
   - `direct`: publica solo, 100% automático. **Requiere que TikTok apruebe (audite) tu app**; antes de eso los posts quedan privados.

### 4. Facebook: token de página
1. Crea una app en https://developers.facebook.com (tipo *Business*).
2. Con el Graph API Explorer pide los permisos `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
3. Cambia el token de usuario por uno de larga duración y luego llama a `GET /me/accounts`: el `access_token` de cada página **no vence**.

### 5. Activa el workflow
Los workflows programados solo corren desde la rama principal (`main`). Haz merge de esta rama a `main`
y entra a la pestaña **Actions** para habilitarlos.

Para probar sin publicar: **Actions → Auto Clipper → Run workflow**, marca *"Solo generar clips"*
y descarga los clips desde el artefacto de la corrida.

## Uso local (opcional)
```bash
pip install -r requirements.txt   # también necesitas ffmpeg instalado
export ANTHROPIC_API_KEY=...
python -m clipper.main --url "https://www.youtube.com/watch?v=XXXX" --no-publish
# los clips quedan en output/<id_video>/clip_01.mp4 (+ .txt con el caption)
```

## Cómo funciona por dentro
- `clipper/sources.py`: busca videos nuevos y los descarga (yt-dlp).
- `clipper/transcribe.py`: transcripción con faster-whisper en CPU.
- `clipper/highlights.py`: Claude elige los momentos (respuesta en JSON validado).
- `clipper/render.py`: ffmpeg recorta, pasa a vertical y quema subtítulos.
- `clipper/publishers/`: subida a TikTok y Facebook con las APIs oficiales.
- `state/processed.json`: registro de videos ya procesados, para no repetir clips.

## Problemas conocidos
- **YouTube bloquea descargas desde servidores** ("Sign in to confirm you're not a bot"): agrega el secret `YT_COOKIES` exportado desde tu navegador con una cuenta secundaria.
- **Encuadre**: el modo `blur` deja el video completo al centro con fondo difuminado (sirve para cualquier video). El modo `crop` recorta al centro; funciona bien si la persona está centrada.
- GitHub Actions corta a las 6 horas; con `max_video_minutes: 90` y el modelo `small` de Whisper hay margen de sobra.
