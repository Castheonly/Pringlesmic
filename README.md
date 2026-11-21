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
                 faster-whisper transcribe + detecta picos de volumen (reacciones)
                          │
                          ▼
                 Claude elige los 3 mejores momentos + título, caption y hashtags
                          │
                          ▼
                 OpenCV sigue la cara → facecam arriba + juego abajo (o zoom a la cara)
                          │
                          ▼
                 ffmpeg + libass: vertical 1080x1920, subtítulos tipo karaoke
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
     TikTok (API oficial)     Facebook Reels (Graph API)
```

## Qué usa de la lista de los 22 repos

El flujo es "VOD → encontrar la reacción → cortar → acercar → subtitular → enviar", pero
**automático y en la nube**. Por eso usa solo las herramientas que corren sin pantalla y sin GPU:

| # | Herramienta | Para qué la usa aquí |
|---|---|---|
| 01 | yt-dlp | Descargar los VODs / videos fuente |
| 03 | OpenCV | Detectar y seguir la cara (YuNet) para el recorte vertical |
| 05 | AI Shorts Generator (idea) | Encontrar destacados: aquí lo hace Claude con la transcripción + picos de audio |
| 07 | Whisper (faster-whisper) | Transcripción con tiempo por palabra |
| 12 | Norfair (idea) | Suavizado del movimiento de cámara, implementado simple con zona muerta |
| 16 | libass (vía ffmpeg) | Subtítulos ASS con estilo y palabra resaltada |
| 22 | PyAV/ffmpeg | Decodificar y codificar video |

Quedan fuera a propósito: **OBS, Kdenlive, Shotcut y OpenCut** son editores de escritorio (manuales);
**Real-ESRGAN, RIFE, Demucs y pyannote** necesitan GPU o tardan demasiado en los servidores gratis.
Se pueden agregar después si consigues un servidor con GPU.

## Layouts (`render.layout`)
- `split`: facecam arriba + gameplay abajo. Es el formato típico de clips de streamers.
- `face`: recorte vertical que sigue la cara con movimiento suave (podcasts, reacciones).
- `blur`: video completo con fondo difuminado (sirve para gameplay sin cámara).
- `crop`: recorte fijo al centro.

Si no detecta ninguna cara, `split` y `face` pasan solos a `blur`.

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
- `clipper/audio.py`: marca los segundos con volumen alto (gritos, risas = reacciones).
- `clipper/tracking.py`: seguimiento facial con OpenCV y suavizado de cámara.
- `clipper/highlights.py`: Claude elige los momentos (respuesta en JSON validado).
- `clipper/render.py`: ffmpeg recorta, pasa a vertical y quema subtítulos.
- `clipper/publishers/`: subida a TikTok y Facebook con las APIs oficiales.
- `state/processed.json`: registro de videos ya procesados, para no repetir clips.

## Problemas conocidos
- **YouTube bloquea descargas desde servidores** ("Sign in to confirm you're not a bot"): agrega el secret `YT_COOKIES` exportado desde tu navegador con una cuenta secundaria.
- **Derechos de autor**: subir clips de streams de otras personas sin permiso trae reclamos y baneos. Lo más seguro es usar tu propio gameplay (grabado con OBS y subido a YouTube como no listado) o tener acuerdo con el streamer.
- GitHub Actions corta a las 6 horas; con `max_video_minutes: 90` y el modelo `small` de Whisper hay margen de sobra.
