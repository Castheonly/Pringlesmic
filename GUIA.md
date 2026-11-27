# Guía de configuración paso a paso

Configuración única, unos 60–90 minutos en total. Hazla en orden: algunos pasos usan datos de los anteriores.
Cuando un paso diga **"guárdalo"**, cópialo en tus notas; lo vas a pegar más adelante.

> 🔒 Nunca compartas contraseñas ni claves en chats. Las claves van solo en los *Secrets* de GitHub.

Tus direcciones (no cambian):
- **Repo:** https://github.com/Castheonly/Pringlesmic
- **Panel (después del paso 1):** https://castheonly.github.io/Pringlesmic/
- **Política de privacidad:** https://castheonly.github.io/Pringlesmic/privacidad.html
- **Términos:** https://castheonly.github.io/Pringlesmic/terminos.html

---

## Paso 1 — Activar el panel web (2 min)

1. Abre https://github.com/Castheonly/Pringlesmic/settings/pages
2. En **Build and deployment → Source** elige **GitHub Actions**.
3. Abre https://github.com/Castheonly/Pringlesmic/actions, entra a **"Publicar panel web"** → **Run workflow** → **Run workflow**.
4. Espera ~1 minuto a que aparezca ✅ y abre https://castheonly.github.io/Pringlesmic/ (verás la pantalla "Conectar con tu repositorio").

> Si en Actions aparece un botón verde *"I understand my workflows, go ahead and enable them"*, tócalo primero.

## Paso 2 — Clave de cifrado de tus cuentas (2 min)

1. Abre https://github.com/Castheonly/Pringlesmic/settings/secrets/actions
2. **New repository secret** → Name: `ACCOUNTS_KEY` → Secret: una frase larga inventada, por ejemplo
   `mi-gato-come-pizza-los-martes-en-marte-2026-xyz`. Mínimo 40 caracteres.
3. **Add secret**. Guárdala también en tus notas: si se pierde, tendrás que volver a conectar las cuentas.

## Paso 3 — Clave de Claude (opcional pero recomendado, 5 min)

Con esta clave, Claude elige los mejores momentos y escribe los captions. Sin ella el sistema
funciona igual, pero elige los clips solo por volumen. Cuesta centavos por video.

1. Entra a https://console.anthropic.com y crea tu cuenta.
2. **Billing** → agrega saldo (con $5 alcanza para cientos de videos).
3. **API Keys** → **Create Key** → copia la clave (empieza con `sk-ant-`).
4. En GitHub (mismo lugar que el paso 2): secret `ANTHROPIC_API_KEY` con esa clave.

## Paso 4 — Conectar el panel a GitHub (3 min)

1. Abre https://github.com/settings/personal-access-tokens/new
2. **Token name:** `clipper-panel` · **Expiration:** 1 año.
3. **Repository access:** *Only select repositories* → **Pringlesmic**.
4. **Permissions → Repository permissions:**
   - **Actions:** Read and write
   - **Contents:** Read and write
5. **Generate token** → copia el token (`github_pat_...`).
6. Abre el panel → Usuario: `Castheonly` · Repositorio: `Pringlesmic` · Rama: `main` · pega el token → **Conectar**.
7. En el celular: menú del navegador → **"Agregar a pantalla de inicio"** y queda como app.

## Paso 5 — App de TikTok (20 min + espera de revisión)

### 5.1 Crear la app
1. Entra a https://developers.tiktok.com → **Log in** con tu cuenta de TikTok de clips.
2. Arriba a la derecha: **Manage apps** → **Connect an app** → elige tu cuenta individual → **Confirm**.
3. Completa **App details**:
   - **App icon:** cualquier imagen cuadrada de 1024×1024.
   - **App name:** `Clipper Personal` (no uses "TikTok" en el nombre).
   - **Category:** *Entertainment* o *Video*.
   - **Description:** `Herramienta personal para subir mis clips a mi propia cuenta de TikTok como borradores.`
   - **Terms of Service URL:** https://castheonly.github.io/Pringlesmic/terminos.html
   - **Privacy Policy URL:** https://castheonly.github.io/Pringlesmic/privacidad.html
   - **Platforms:** marca **Web** → Website URL: https://castheonly.github.io/Pringlesmic/

### 5.2 Productos y permisos
1. **Add products** → agrega **Login Kit** y **Content Posting API**.
2. En **Login Kit** → **Redirect URI** → Web: `https://castheonly.github.io/Pringlesmic/`
   (exactamente así, con la barra final; también la ves en el panel → Cuentas → "Redirect URI").
3. En **Scopes** verifica que estén: `user.info.basic`, `user.info.profile`, `video.upload`.
   (`video.publish` no es necesario: tú vas a publicar desde la app.)

### 5.3 Claves
1. En la página de la app copia **Client key** y **Client secret**.
2. En GitHub Secrets crea:
   - `TIKTOK_CLIENT_KEY` = Client key
   - `TIKTOK_CLIENT_SECRET` = Client secret
3. En el panel → **Cuentas** → pega el **Client key** en "TikTok Client Key" → **Guardar**.

### 5.4 Activar la app
- **Opción rápida (Sandbox):** en el portal cambia a **Sandbox** → **Target users** → agrega tu cuenta de TikTok.
  Así puedes conectar y probar de inmediato.
- **Definitiva:** botón **Submit for review**. En "¿cómo usas los permisos?" explica:
  *"Uso personal: subo como borrador a mi propia cuenta los clips que edito; luego los termino y publico desde la app de TikTok."*
  Graba un video corto de la pantalla del panel tocando "Conectar TikTok" y adjúntalo. La revisión tarda de días a 2 semanas.

### 5.5 Conectar tu cuenta
Panel → **Cuentas** → **Conectar TikTok** → inicias sesión en TikTok → **Autorizar**.
En ~1 minuto toca ↻: debe aparecer tu `@usuario`.

## Paso 6 — Página y app de Facebook (20 min)

### 6.1 Crear tu página de clips
1. Entra a https://www.facebook.com/pages/create con tu Facebook personal (no hace falta otra cuenta).
2. **Nombre:** el de tu marca de clips · **Categoría:** *Creador de contenido digital* o *Entretenimiento*.
3. **Crear página**. Puedes poner foto de perfil y portada después.

### 6.2 Crear la app
1. Entra a https://developers.facebook.com → **Mis apps** → **Crear app**.
2. Si te lo pide, regístrate como desarrollador (verifica tu teléfono).
3. **Caso de uso:** elige **"Administrar todo en tu página"** (*Manage everything on your Page*).
4. **Nombre de la app:** `Clipper Personal` → **Crear app**.

### 6.3 Configurar
1. **Configuración de la app → Básica:**
   - **Dominios de la app:** `castheonly.github.io`
   - **URL de la política de privacidad:** https://castheonly.github.io/Pringlesmic/privacidad.html
   - **URL de las condiciones del servicio:** https://castheonly.github.io/Pringlesmic/terminos.html
   - **Categoría:** Entretenimiento → **Guardar cambios**.
   - Copia el **Identificador de la app** (App ID) y el **Clave secreta de la app** (botón "Mostrar").
2. **Casos de uso → Administrar todo en tu página → Personalizar:** verifica que estén
   `pages_show_list`, `pages_read_engagement` y `pages_manage_posts`.
3. **Inicio de sesión con Facebook → Configuración:**
   - **Inicio de sesión con el SDK para JavaScript:** Sí
   - **Dominios permitidos para el SDK para JavaScript:** `https://castheonly.github.io/`
   - **URI de redireccionamiento de OAuth válidos:** `https://castheonly.github.io/Pringlesmic/`
   - **Guardar cambios**.
4. Arriba, cambia el **Modo de la app** de *Desarrollo* a **Activo / Publicado** (si lo dejas en Desarrollo,
   tus Reels solo los verías tú). No necesitas "Revisión de la app": solo tú la usas.

### 6.4 Claves y conexión
1. En GitHub Secrets crea:
   - `FACEBOOK_APP_ID` = Identificador de la app
   - `FACEBOOK_APP_SECRET` = Clave secreta de la app
2. Panel → **Cuentas** → pega el **App ID** → **Guardar** → **Conectar Facebook** → elige tu página → **Continuar**.
3. En ~1 minuto toca ↻: debe aparecer tu página.

> Los Reels de Facebook se publican **solos**. Si también quieres editarlos a mano, dímelo y desactivo la publicación automática en Facebook.

## Paso 7 — Plataformas de campañas (10 min)

En **QuantyClips**, **Reach Clipping** y **Content Rewards**, entra con tu usuario y:
1. **Conecta tu TikTok** y tu **página de Facebook** desde tu perfil (así miden tus vistas y te pagan).
2. **Únete** a las campañas que te interesan y acepta sus términos.
3. Copia el link de cada campaña → panel → **Campañas** → "Agregar campaña desde su página" → **Revisar y agregar**.
   Si la página pide iniciar sesión para ver las reglas, pega también el texto de las reglas.

> La campaña de Content Rewards que me pasaste ya está en la cola: se revisa sola en la primera corrida.

## Paso 8 — Primera prueba (10 min)

1. Panel → **Procesar video** → pega el link de un video o stream → marca **"Solo generar clips"** → **Crear clips**.
2. Panel → **Corridas** → espera ✅ (5–40 min según el largo) → **"ver detalle y descargar clips"** →
   abajo, en **Artifacts**, descarga el zip con los clips.
3. Si te gustan, ya está todo listo: el sistema corre solo cada 6 horas.

---

## Qué hace el sistema solo

| Cada | Qué hace |
|---|---|
| 20 min | Revisa quién está **en vivo** (Kick y YouTube). Graba tramos de 45 min y los recorta. Si varios están en el mismo stream (se mencionan o es el mismo evento), graba solo el de más viewers. |
| 4 horas | Revisa **VODs** de Kick (los que no alcanzó a recortar en vivo) y **videos nuevos** de YouTube (solo lo que suban desde ahora). |
| 1 día | **Radar de tendencias** (TikTok + noticias y comunidades de cada creador) y **busca campañas nuevas** en QuantyClips, Reach y Content Rewards. |

**Campañas:** las nuevas aparecen en el panel → **Campañas → 🆕 Campañas encontradas**. Tú entras con "Abrir y unirme",
aceptas los términos en la web y vuelves a tocar **"Ya me uní ✓"**. Desde ahí el sistema lee las reglas y recorta ese canal solo.
(El sistema nunca inicia sesión ni acepta términos por ti.)

## Tu rutina diaria (5–10 min)

1. **Panel → Clips y links:** cada clip trae, escrito por Claude según el video, las tendencias y la comunidad del creador:
   - **Texto en pantalla** (botón "copiar") → para ponerlo con la herramienta de texto de TikTok.
   - **Idea de sonido** y **tendencia** a la que se engancha.
   - **Caption + hashtags** (botón "copiar") → los borradores de TikTok llegan **sin caption**, así que lo pegas tú.
2. **TikTok:** abre la app → **Bandeja de entrada / Notificaciones** → "tu video está listo para editar" →
   ábrelo → pega el **texto en pantalla**, agrega el **sonido** si aplica → pega el **caption** → **Publicar**.
3. **Campañas:** copia el link de cada TikTok publicado y envíalo en la plataforma de la campaña
   (si conectaste tu cuenta ahí, algunas lo detectan solas).
4. **Panel → Inicio → Tendencias de hoy:** lo que está pegando hoy en TikTok (se actualiza solo cada día).

## Si algo falla

| Problema | Solución |
|---|---|
| La corrida sale ❌ | Panel → Corridas → "ver detalle" → copia el error y pásamelo |
| "Sign in to confirm you're not a bot" (YouTube) | Agrega el secret `YT_COOKIES` (exporta cookies de YouTube con la extensión "Get cookies.txt LOCALLY" usando una cuenta secundaria) |
| TikTok no conecta | Revisa que la Redirect URI sea exactamente `https://castheonly.github.io/Pringlesmic/` y que tu cuenta esté en Sandbox → Target users |
| Facebook no conecta | Revisa dominios del SDK y que la app esté en modo Activo |
| No aparecen clips nuevos | Revisa que la campaña esté **activa** y tenga fuentes |
