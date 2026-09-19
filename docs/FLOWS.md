# Agora flows

Sequence diagrams of the three processes between the owner, ChatGPT, Agora, Keycloak, Google and OLX. Diagrams are Mermaid, rendered by GitHub. Design background: [DESIGN.md](DESIGN.md), section 7 (auth) and section 4 (tools).

Legend: **User** is the owner and their browser. **ChatGPT** means OpenAI's servers, not the browser. **Agora** is this MCP server. **Keycloak** handles the login into Agora. **Google** is one way to log in to Keycloak (linked to the existing owner user). **OLX** holds the listings.

## 1. ChatGPT connects to Agora

Status: **verified** in the Traefik and Agora logs on 2026-09-19. Happens once, when the connector is added. After that ChatGPT sends the token with every call.

```mermaid
sequenceDiagram
  autonumber
  participant O as User
  participant C as ChatGPT
  participant A as Agora
  participant K as Keycloak
  participant G as Google

  rect rgba(10, 111, 124, 0.09)
  Note over C,K: Виявлення
  C->>A: POST /mcp без токена
  A-->>C: 401 і WWW-Authenticate з адресою метаданих
  C->>A: GET /.well-known/oauth-protected-resource
  A-->>C: resource /mcp, authorization server це Keycloak
  C->>K: GET /.well-known/oauth-authorization-server/realms/home
  K-->>C: адреси авторизації, токена і реєстрації, PKCE S256
  end

  rect rgba(10, 111, 124, 0.09)
  Note over C,K: Реєстрація клієнта (DCR)
  C->>K: POST /clients-registrations/openid-connect
  K-->>C: 201 і client_id
  end

  rect rgba(10, 111, 124, 0.09)
  Note over O,K: Вхід, один раз
  C->>O: відкриває вікно входу
  O->>K: відкриває сторінку входу Keycloak
  alt вхід через Google
    K-->>O: перенаправлення на Google
    O->>G: входить у Google
    G-->>O: перенаправлення назад на Keycloak з code
    O->>K: code від Google
    K->>G: обмінює code, отримує ідентичність
    K->>K: прив’язує до наявного користувача, нового не створює
  else пароль з OTP
    O->>K: пароль і одноразовий код
  end
  O->>K: дає згоду
  K-->>O: перенаправлення на chatgpt.com з code
  O->>C: code
  C->>K: POST /token: code і PKCE verifier
  K-->>C: access token, aud це origin Agora, sub це ви
  end

  rect rgba(10, 111, 124, 0.09)
  Note over C,A: Кожен виклик інструмента
  C->>A: POST /mcp з Bearer токеном
  A->>K: JWKS, кешується
  A->>A: підпис, iss, aud, exp, sub дорівнює власнику
  A-->>C: 200, ping повертає pong
  end
```

Notes:

- Google only confirms who the owner is. The token for Agora is issued by Keycloak, not Google, so dropping Google later breaks nothing.
- The token belongs to ChatGPT and arrives as a header from OpenAI's servers, not from the owner's browser.
- Agora never issues tokens, it only verifies them. The owner check (`sub`) and the mandatory `exp` are added by Agora on top of FastMCP's JWT verifier.
- Keycloak's RFC 8414 metadata URL must be public, or ChatGPT reports that OAuth is not supported.
- Cost: Cloudflare Bot Fight Mode blocked the registration request, so it is disabled for the whole zone.

## 2. Agora connects to OLX

Status: **planned**, not implemented. A separate OAuth relationship: the token is issued by OLX and lets Agora act on the owner's behalf. Keycloak is not involved.

```mermaid
sequenceDiagram
  autonumber
  participant O as User
  participant C as ChatGPT
  participant A as Agora
  participant L as OLX

  rect rgba(10, 111, 124, 0.09)
  Note over C,A: Початок автентифікований токеном Keycloak
  O->>C: підключи мій OLX
  C->>A: інструмент olx_connect з Bearer токеном
  A->>A: створює випадковий state, одноразовий, на кілька хвилин
  A-->>C: посилання на OLX зі state
  C-->>O: показує посилання
  end

  rect rgba(10, 111, 124, 0.09)
  Note over O,L: Згода на боці OLX
  O->>L: відкриває посилання, входить в OLX, дозволяє
  L-->>O: перенаправлення на callback Agora з code і state
  end

  rect rgba(10, 111, 124, 0.09)
  Note over O,A: Callback. Токена Keycloak тут немає, запит іде з браузера
  O->>A: GET /oauth/olx/callback з code і state
  alt state невідомий, прострочений або вже використаний
    A-->>O: 400, нічого не зберігається
  else state дійсний
    A->>L: POST /api/open/oauth/token з code, client_id і client_secret
    L-->>A: access token і refresh token
    A->>A: зберігає токени, не в моделі і не в логах
    A-->>O: Готово, вкладку можна закрити
  end
  end

  rect rgba(10, 111, 124, 0.09)
  Note over A,L: Далі без вас
  A->>L: запити з access token, refresh раз на місяць
  L-->>A: нові токени, зберегти найновіший refresh
  end
```

Notes:

- The callback is requested by the browser, so a Keycloak token cannot be required on it. It is protected by `state`: without a known, unexpired, unused value the request is rejected.
- The callback can be served on the LAN only, in which case it is not public at all.
- OLX's refresh token may change on refresh, so the newest one is always stored.
- Unverified: whether OLX approves an application from a private person, and whether it accepts a local or `http` callback.

## 3. Creating a listing with photos from the conversation

Status: **planned**, not implemented. Two steps on purpose (preview, then confirm): no tool changes OLX from a single call.

```mermaid
sequenceDiagram
  autonumber
  participant O as User
  participant C as ChatGPT
  participant F as Файли ChatGPT
  participant A as Agora
  participant L as OLX

  rect rgba(10, 111, 124, 0.09)
  Note over O,A: Фото з розмови
  O->>C: продай це, з фото
  C->>A: images_stage з файлами, що мають download_url
  A->>F: GET download_url, лише https, без приватних адрес, ліміт розміру
  F-->>A: байти файлу
  A->>A: тип за вмістом, прибирає EXIF з GPS, зберігає на короткий час
  A-->>C: image_id для кожного фото
  end

  rect rgba(10, 111, 124, 0.09)
  Note over O,A: Попередній перегляд, нічого не змінено в OLX
  C->>A: listing_create_preview з чернеткою і image_id
  A->>A: перевіряє чернетку, зберігає план під одноразовим токеном на 10 хвилин
  A-->>C: перегляд і токен підтвердження
  C-->>O: показує, що буде опубліковано
  end

  rect rgba(10, 111, 124, 0.09)
  Note over O,L: Підтвердження, і лише тоді запис
  O->>C: підтверджую
  C->>A: write_confirm лише з токеном
  A->>A: токен відомий, не прострочений, не використаний, запис дозволено
  A->>L: створення оголошення і фото з токеном OLX
  L-->>A: оголошення створено
  A-->>C: результат, можлива модерація
  end
```

Notes:

- Photo bytes never pass through the model, only `image_id` values.
- The confirmation token is bound to the exact plan payload, so it cannot be altered between preview and write.
- Writes are disabled until `AGORA_WRITES` is enabled, and have a daily cap.
- Unverified: what ChatGPT sends for attached photos on web and on mobile; whether OLX accepts photos as files or by URL; how long moderation takes.
