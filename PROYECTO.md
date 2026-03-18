# Clasificador CIE-10 — Documentación del Proyecto

## Descripción general

Asistente de codificación médica que analiza informes clínicos en texto libre y sugiere los códigos CIE-10 (Clasificación Internacional de Enfermedades) correspondientes. Los médicos pueden validar o rechazar cada código, creando un historial auditado de sus sesiones de análisis.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| Backend | Elixir 1.15, Phoenix 1.8, Commanded (CQRS/Event Sourcing) |
| Base de datos | PostgreSQL 15 (app + event store) |
| AI Engine | FastAPI (Python) — modelo real o mock |
| Email | Swoosh + Mailpit (SMTP catcher local) |
| Infra | Docker Compose, Makefile |

---

## Arquitectura original (antes de los cambios)

### Frontend
- Una única página con un `ConversationProvider` que generaba un `userId` aleatorio en cada carga (no persistido).
- Chat lineal de mensajes sin distinción de tipos.
- Panel lateral derecho con códigos CIE-10 predichos y botones de validación/rechazo (usando `prompt()` del navegador para el motivo de rechazo).
- Sin autenticación — cualquiera podía acceder.
- Sin lista de conversaciones anteriores.
- `localhost:4000` hardcodeado en el código.

### Backend
- Canal WebSocket `conversation:*` con 4 handlers: `send_message`, `analyze_report`, `validate_code`, `reject_code`.
- El AI engine devolvía `{ codes: [...] }` — solo códigos.
- Sin usuarios, sin autenticación.
- Router API vacío (`/api` sin rutas).
- Sin soporte multi-idioma.

### AI Engine Mock
- Devolvía `{ codes: [...] }` con código, descripción y motivo.

---

## Cambios implementados

### 1. Autenticación completa (registro + login + email de confirmación)

**Backend:**
- Nueva tabla `users` con `first_name`, `last_name`, `username`, `email`, `password_hash`, `confirmation_token`, `confirmed_at`, `locale`.
- `App.Accounts` — módulo de contexto con `register_user/1`, `authenticate/2`, `confirm_user/1`, `update_locale/2`.
- `App.Accounts.User` — schema con changeset de registro (hash bcrypt, token de confirmación, validaciones).
- `AppWeb.AuthController` — `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/confirm/:token`, `PUT /api/users/locale`.
- `AppWeb.Plugs.RequireAuth` — verifica Bearer token (Phoenix.Token) en rutas protegidas.
- `AppWeb.UserSocket` — ahora verifica el token JWT en lugar de aceptar cualquier `user_id`.
- `App.Accounts.Emails` — email HTML de confirmación enviado mediante Swoosh.
- **Mailpit** añadido a docker-compose como SMTP catcher (UI en `:8025`, SMTP en `:1025`).

**Frontend:**
- `AuthContext` — gestiona `user`, `token`, `pendingEmail`; persiste sesión en `localStorage`; maneja el redirect de confirmación (`?confirmed=1`).
- `AuthPage` — formulario con tabs de "Iniciar sesión" / "Registrarse"; campos nombre, apellidos, username, email, contraseña; pantalla "Revisa tu email" tras el registro.
- `page.tsx` — muestra `AuthPage` si no hay sesión, `ChatInterface` si está autenticado.

---

### 2. Lista de análisis por usuario

**Backend:**
- `GET /api/conversations?user_id=` — devuelve las conversaciones del usuario ordenadas por fecha, con el último mensaje y el recuento.
- `AppWeb.Plugs.RequireAuth` protege esta ruta.

**Frontend:**
- `ConversationSidebar` — panel izquierdo oscuro con nombre del doctor, selector de idioma, botón de logout, botón "Nuevo análisis" y lista de análisis anteriores con fecha, preview del último mensaje y recuento.
- `ConversationContext` refactorizado: gestiona múltiples conversaciones, cambia de canal WebSocket al seleccionar una diferente, recarga la lista al recibir mensajes.
- `userId` ya no se regenera — proviene del backend tras la autenticación.

---

### 3. Sistema de tarjetas tipadas (mensajes multi-tipo)

**AI Engine Mock (`ai_engine_mock/main.py`):**
- Ahora devuelve `{ cards: [...], codes: [...] }`.
- Tres tipos de tarjeta generados por análisis:
  - `summary` — resumen textual del informe analizando palabras clave y recuento.
  - `codes` — lista de códigos CIE-10 con código, descripción, motivo y confianza.
  - `recommendations` — texto de recomendaciones clínicas basado en los códigos detectados.

**Backend:**
- Nueva tabla `analysis_cards` con `card_id`, `card_type`, `content` (JSON o texto), `position`, `message_id`, `conversation_id`.
- `AnalysisCardProjection` — schema y changeset.
- `ConversationProjector` — guarda cada tarjeta al procesar `AIPredictionReceived`; también guarda los `PredictedCode` desde el card de tipo `codes` (para validación/rechazo).
- `ConversationChannel` — difunde cada tarjeta individualmente con `analysis_card_received`, y emite `analysis_complete` al finalizar.
- `load_conversation_history` — incluye `analysis_cards` ordenadas por posición al reconectar.

**Frontend:**
- `ConversationContext` — `chatItems: ChatItem[]` unifica mensajes del usuario y tarjetas en un único stream.
- `ChatInterface` — renderiza cada `ChatItem` con su componente específico:
  - `SummaryCard` — borde azul, icono de clipboard.
  - `CodesCard` — borde índigo, lista de códigos con botones validar/rechazar inline (sin `prompt()`; campo de texto inline para el motivo de rechazo).
  - `RecommendationsCard` — borde ámbar, icono de bombilla.
  - `TextCard` — fallback genérico.

---

### 4. Internacionalización (i18n)

**Backend:**
- `priv/translations/es.yml` y `en.yml` — ficheros YAML con todas las cadenas traducidas (auth, app, sidebar, chat, cards).
- `App.Translations` — GenServer que carga los YAMLs al arrancar y los sirve en memoria; expone `t(locale, key, vars)` con interpolación `{var}`.
- `AppWeb.TranslationController` — `GET /api/translations/:locale` parsea el YAML y devuelve JSON.
- `AppWeb.Plugs.SetLocale` — detecta el locale del header `Accept-Language` o del param `?locale=`; lo asigna a `conn.assigns.locale`.
- `AuthController` y `Emails` usan `App.Translations.t/3` para mensajes de error y emails localizados.
- Campo `locale` en `users` — persiste la preferencia del usuario; endpoint `PUT /api/users/locale`.

**Frontend:**
- `I18nContext` — carga traducciones desde el backend al arrancar; cachea en memoria; expone `t(key, vars)` con interpolación `{var}`; detecta idioma del navegador; persiste en `localStorage`.
- `setLocale(locale, token)` — sincroniza el idioma con el backend si el usuario está autenticado.
- `ConversationSidebar` — selector de idioma (toggle ES ↔ EN) con icono de globo.
- `AuthPage` y `ChatInterface` — todas las cadenas pasadas por `t()`.

---

### 5. Configuración centralizada y calidad de código

- `frontend/src/lib/config.ts` — `config.apiUrl` y `config.wsUrl` con defaults; sobreescribibles con variables de entorno `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL`.
- `socket.ts` — usa `config.wsUrl` en lugar de hardcode.
- `page.tsx` — `userId` eliminado; se usa el `id` del usuario autenticado.
- `Makefile` — añadidos `logs-mail` y `make mailpit` (abre Mailpit en el navegador); URLs de todos los servicios actualizadas incluyendo Mailpit (`:8025`).
- `docker-compose.yml` — servicio Mailpit, variables SMTP, dependencia del backend en Mailpit.
- `.env.example` — variables SMTP y APP_HOST documentadas.

---

## Flujo completo

```
Doctor abre la app
  → AuthPage (login / registro)
    → Registro: email de confirmación via Mailpit
    → Login: token JWT devuelto por el backend
  → ChatInterface + ConversationSidebar

Doctor crea un nuevo análisis
  → Frontend genera un conversation_id
  → WebSocket join → backend crea la conversación (CQRS)

Doctor pega un informe clínico y pulsa "Analizar informe"
  → push "analyze_report"
  → Backend: AnalyzeReport command → evento → proyector
  → Backend: Task llama al AI engine POST /predict
  → AI engine devuelve { cards: [summary, codes, recommendations] }
  → Backend: ReceiveAIPrediction command → proyector guarda cards + codes
  → Backend difunde analysis_card_received x3 (uno por card)
  → Backend difunde analysis_complete
  → Frontend renderiza cada card en el stream con su componente

Doctor valida o rechaza un código
  → push "validate_code" / "reject_code"
  → Backend: ValidateCode/RejectCode command → evento → proyector
  → Backend difunde code_validated / code_rejected
  → Frontend actualiza el estado del código en el CodesCard

Doctor cambia de idioma
  → I18nContext fetchea /api/translations/:locale
  → PUT /api/users/locale persiste la preferencia
  → Toda la UI se re-renderiza en el nuevo idioma

Doctor selecciona un análisis anterior
  → switchConversation → WebSocket join al canal anterior
  → Backend devuelve history (messages + predicted_codes + analysis_cards)
  → Frontend reconstruye el stream de chatItems
```

---

## Servicios y puertos

| Servicio | URL |
|---------|-----|
| Frontend (Next.js) | http://localhost:3000 |
| Backend (Phoenix) | http://localhost:4000 |
| AI Engine (FastAPI) | http://localhost:8000 |
| Mailpit UI | http://localhost:8025 |
| PostgreSQL | localhost:5432 |

**Comandos útiles:**
```bash
make up          # Levantar todo
make mailpit     # Abrir bandeja de email de prueba
make backend-migrate  # Ejecutar migraciones
make logs-backend     # Ver logs del backend
```
