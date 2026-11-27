# Pringlesmic — Clipping automático 24/7 (gratis)

Convierte streams y videos largos (YouTube, Twitch, Kick y +1000 sitios) en clips verticales
con subtítulos, los publica solos en tus cuentas de **TikTok** y tus páginas de **Facebook (Reels)**
y guarda los links de cada post para que los envíes a las **campañas de clipping** que te pagan por vistas.

- **Sin computador prendido**: corre en GitHub Actions cada 4 horas, procesando hasta 8 videos a la vez.
- **Radar de tendencias**: cada día Claude investiga tendencias de TikTok y lo último de cada creador y su
  comunidad, y con eso escribe el texto en pantalla, caption, hashtags e idea de sonido de cada clip.
- **Panel web / app** para el celular: crear campañas, procesar un video al instante y copiar links.
- **Costo**: $0 en infraestructura. Solo pagas Claude (unos centavos por video).

```
 Campañas (config.yaml / panel web)
        │  cada 6 h o con un botón
        ▼
 yt-dlp descarga el video o VOD nuevo  (YouTube, Twitch, Kick, TikTok, X, Facebook…)
        ▼
 Curva de volumen → encuentra reacciones (gritos, risas, explosiones)
        │  streams largos: solo transcribe los tramos con más reacción
        ▼
 Whisper transcribe con tiempo por palabra (cualquier idioma)
        ▼
 Claude elige los mejores momentos respetando las reglas de la campaña
        ▼
 OpenCV sigue la cara → facecam + juego, zoom a la cara, o fondo difuminado (auto)
        ▼
 ffmpeg + libass → 1080x1920 con subtítulos tipo karaoke y gancho arriba
        ▼
 TikTok + Facebook Reels → links guardados en state/submissions.json → panel → campañas
```

## Qué es gratis y qué no

| Pieza | Costo |
|---|---|
| GitHub Actions (el motor) | Gratis: ilimitado en repos públicos; 2.000 min/mes en privados |
| Panel web (GitHub Pages o Cloudflare Pages) | Gratis |
| Whisper, OpenCV, ffmpeg | Gratis (corren dentro de Actions) |
| APIs de TikTok y Facebook | Gratis |
| Claude (elegir los momentos) | ~$0,02–0,10 por video según el largo |

> **Repo privado y minutos**: en un repo privado tienes 2.000 min/mes gratis. Un video de 30 min usa
> ~15–25 min de Actions; un stream de 4 h, ~40–60. Si se te acaban, haz el repo **público**: el
> código y la configuración no tienen claves, ya que todas van en *Secrets*. Ojo: el registro de
> clips (`state/`) también quedaría visible.

## Campañas de clipping

Cada campaña es un bloque en `config.yaml`, o se crea desde el panel, con:
- **fuentes**: canales de YouTube, VODs de Twitch o Kick, playlists o videos sueltos
- **reglas**: texto que Claude respeta al elegir los clips (ej: "solo momentos del juego X")
- **texto y hashtags obligatorios**, que se agregan a cada post
- **duración**, **cantidad de clips**, **idioma** y **formato**
- **a qué cuentas** de TikTok y Facebook se publica
- **contenido pagado**: marca el post como promoción en TikTok, algo que muchas campañas exigen

### Agregar campañas con solo pegar el link
En el panel → **Campañas → "Agregar campaña desde su página"**, pega el link de la campaña (Whop, la
web del creador, un post de Discord, etc.). Si la página pide iniciar sesión, pega también el texto
de las reglas. En 1–2 minutos Claude:
1. lee la página y extrae de dónde sacar clips, reglas, hashtags y menciones obligatorias, duración,
   plataformas aceptadas, pago y fecha de término;
2. crea la campaña y la deja **activa** (`intake.auto_activate` en `config.yaml`);
3. te avisa en el panel lo que solo tú puedes hacer, como unirte a la campaña o vincular tu cuenta.

Por seguridad solo acepta fuentes de sitios de video conocidos (YouTube, Twitch, Kick, TikTok, X…)
e ignora cualquier instrucción escrita en la página. Las campañas vencidas se dejan de procesar solas.

### Cuentas que sigues siempre
En **Campañas → "Cuentas que sigo siempre"** agregas canales de YouTube, Twitch o Kick. Cada vez
que suban algo nuevo, se recorta y publica solo con las reglas de esa campaña.

Después de publicar, el panel muestra el link de cada post con un botón "copiar". Así los envías a
la plataforma de la campaña (Whop Content Rewards, Discord del creador, etc.). Estas plataformas
no tienen API pública para enviar links, por eso ese paso queda en un clic tuyo.

> ⚠️ Recorta solo contenido tuyo o de campañas que te autoricen. Subir clips ajenos sin
> permiso trae reclamos de copyright y baneos de cuenta.

## Formatos (`layout`)
- `auto` *(recomendado)*: con facecam pequeña usa `split`; con una cara grande usa `face`; sin cara usa `blur`.
- `split`: facecam arriba y juego o pantalla abajo (clips de streamers).
- `face`: recorte vertical que sigue a la persona con movimiento suave (podcasts, vlogs).
- `blur`: video completo con fondo difuminado.
- `crop`: recorte fijo al centro.

> 📘 **Guía paso a paso con todos los clics: [GUIA.md](GUIA.md)**

## Instalación (una sola vez, ~40 min)

> 🔒 **Nunca compartas tus contraseñas** (ni conmigo, ni en el repo). Las cuentas se conectan con el
> inicio de sesión oficial de TikTok y Facebook: tú inicias sesión y el sistema guarda un permiso
> cifrado para publicar. Ese permiso lo puedes revocar cuando quieras desde TikTok o Facebook.

### 1. Secrets en GitHub
Repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Qué es |
|---|---|
| `ANTHROPIC_API_KEY` | API key de https://console.anthropic.com |
| `ACCOUNTS_KEY` | Cualquier frase larga y aleatoria (40+ caracteres). Cifra los permisos de tus cuentas. **No la pierdas** |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | De tu app en https://developers.tiktok.com |
| `FACEBOOK_APP_ID` / `FACEBOOK_APP_SECRET` | De tu app en https://developers.facebook.com |
| `YT_COOKIES` *(opcional)* | Cookies de YouTube si YouTube bloquea las descargas |

### 2. Publica el panel (tu "app")
**Opción A — GitHub Pages** (gratis si el repo es público): Settings → Pages → Source: *GitHub Actions*.
Queda en `https://TU_USUARIO.github.io/Pringlesmic/`.

**Opción B — Cloudflare Pages** (gratis con repo privado): dash.cloudflare.com → Workers & Pages →
Create → Pages → conecta el repo, sin comando de build, carpeta de salida `web`.

Abre el panel y conecta tu repo con un token *fine-grained* (github.com → Settings → Developer settings →
Fine-grained tokens): solo este repo, con *Contents: Read and write* y *Actions: Read and write*.
En el celular: menú del navegador → **"Agregar a pantalla de inicio"**.

### 3. TikTok (tu cuenta de clips que ya tienes)
1. https://developers.tiktok.com → *Manage apps* → crea una app con **Login Kit** y **Content Posting API**.
2. Scopes: `user.info.basic`, `user.info.profile`, `video.upload`, `video.publish`.
3. En *Login Kit → Redirect URI* pega la URL que muestra el panel en **Cuentas** (botón "copiar").
4. En el panel → **Cuentas**: guarda tu *Client Key* → **Conectar TikTok** → inicias sesión y aceptas.
5. Modo de publicación (`defaults.publish.tiktok.mode`):
   - `inbox` *(por defecto)*: llega como **borrador** a tu app de TikTok y tocas "Publicar". No requiere auditoría.
   - `direct`: se publica solo y el link queda listo para las campañas. **Requiere que TikTok audite tu app**
     (en el portal: *Submit for review*); antes de eso los posts quedan privados.

### 4. Facebook (cuenta de clips nueva)
1. Con tu Facebook personal crea una **Página** para los clips (facebook.com/pages/create). Es gratis
   y no necesitas otra cuenta personal; tener cuentas personales extra va contra las reglas de Facebook.
2. https://developers.facebook.com → crea una app tipo *Business* → agrega **Facebook Login for Business**.
3. En la app, *App Domains* y *Allowed Domains for the JavaScript SDK*: agrega el dominio de tu panel.
4. En el panel → **Cuentas**: guarda tu *App ID* → **Conectar Facebook** → eliges tu página y aceptas.
   El permiso de página que se guarda **no vence**.

### 5. Plataformas de campañas (QuantyClips, Reach Clipping, Content Rewards)
Entra tú a cada una y **conecta ahí tu TikTok y tu página de Facebook**; así miden tus vistas y te pagan.
Después pega el link de cada campaña en el panel → **Campañas** y el sistema la revisa y la agrega sola.
La campaña de Content Rewards que compartiste ya está en la cola de revisión (`state/campaign_inbox.json`).

### 6. Activar
Haz merge a `main` y habilita los workflows en la pestaña **Actions**.

## Uso local (opcional)
```bash
pip install -r requirements.txt     # requiere ffmpeg
export ANTHROPIC_API_KEY=...
python -m clipper.main --url "https://www.twitch.tv/videos/123" --campaign mi-canal --no-publish
```

## Estructura
- `config.yaml`: campañas y ajustes (también se edita desde el panel).
- `clipper/accounts.py`: conexión de cuentas (OAuth) y permisos cifrados en `state/accounts.enc`.
- `clipper/campaign_intake.py`: lee las páginas de campañas que pegas y las convierte en campañas.
- `state/campaign_inbox.json`: campañas por revisar y su resultado.
- `clipper/sources.py`: busca y descarga videos (yt-dlp).
- `clipper/audio.py`: curva de volumen, reacciones y tramos clave en streams largos.
- `clipper/transcribe.py`: Whisper en CPU, completo o por tramos.
- `clipper/highlights.py`: Claude elige los momentos (JSON validado).
- `clipper/tracking.py`: seguimiento facial con OpenCV (YuNet) y movimiento de cámara suave.
- `clipper/render.py`: formato vertical y subtítulos.
- `clipper/publishers/`: TikTok y Facebook con las APIs oficiales.
- `state/processed.json`: videos ya procesados, para no repetir.
- `state/submissions.json`: cada clip con sus links publicados (lo que muestra el panel).
- `web/`: panel web instalable como app.

## De la lista de 22 repos del post
Usa yt-dlp, OpenCV, Whisper (faster-whisper), libass y ffmpeg, más las ideas de AI Shorts Generator
y Norfair. Quedan fuera los editores de escritorio (OBS, Kdenlive, Shotcut, OpenCut) y los modelos
que necesitan GPU (Real-ESRGAN, RIFE, Demucs, pyannote), porque no corren gratis en la nube.

## Problemas conocidos
- **YouTube bloquea descargas desde servidores** ("Sign in to confirm you're not a bot"): agrega
  `YT_COOKIES` exportadas desde tu navegador con una cuenta secundaria. Twitch y Kick no suelen bloquear.
- **GitHub pausa los workflows programados** tras 60 días sin actividad en el repo. Como cada
  corrida hace un commit al registro, mientras haya clips nuevos no pasa.
- Actions corta a las 6 h por corrida; los streams largos se procesan por tramos, así que alcanza.
