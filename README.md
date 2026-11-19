# Bookstore API — автентифікація і захист

## Варіант

- Номер варіанта: **10**
- Схема: JWT
- Право: P2 (закритий каталог: усе тільки для авторизованих, DELETE лише для `is_staff`)
- Throttle: 7 запитів/год для аноніма · 140 запитів/добу для користувача
- Інтеграція: I5 (CORS для фронтенду на `http://localhost:3000`)
- Відеозахист: не робив

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
python manage.py test
```

Тестові користувачі (`python manage.py seed`), пароль `pass12345`:

| Користувач | Пошта | Акаунт | Група / роль |
|---|---|---|---|
| alice | alice@kpi.edu.ua | 30 днів | Editors, власниця третини книг |
| bob | bob@lnu.edu.ua | 30 днів | Editors |
| carol | carol@gmail.com | 30 днів | — |
| newbie | newbie@kpi.edu.ua | щойно | Editors |
| moder | moder@gmail.com | 30 днів | Moderators |
| staff | staff@gmail.com | 30 днів | `is_staff` |
| admin | admin@example.com | — | суперкористувач, пароль `admin` |

## Що я зробив

1. **JWT.** Підключив `simplejwt`, додав маршрути `/api/v1/auth/jwt/create/`, `/refresh/` і `/logout/`. Для виходу взяв готовий `TokenBlacklistView`, він кладе refresh у чорний список. Access живе 15 хвилин. Єдиним класом автентифікації поставив `JWTAuthentication`, тому анонім отримує 401, а не 403.
2. **Право P2.** Написав свій клас `ClosedCatalog` у `bookstore/permissions.py`. Він пускає лише автентифікованих (навіть на GET), а для DELETE ще перевіряє `is_staff`. Підключив у `BookViewSet.permission_classes`.
3. **Throttling.** Додав `AnonRateThrottle` і `UserRateThrottle` з лімітами `7/hour` і `140/day`.
4. **CORS (I5).** Підключив `django-cors-headers`, дозволив тільки `http://localhost:3000`, додав заголовок `X-Client-Version`. `CorsMiddleware` поставив вище за `CommonMiddleware`, щоб редирект зі слешем теж ніс CORS-заголовок.

## Результат тестів

```
Ran 59 tests in 10.8s

OK (skipped=37)
```

## Журнал `curl -i`

### 1. Вхід і вихід

```
$ curl -i -X POST http://127.0.0.1:8000/api/v1/auth/jwt/create/ -H "Content-Type: application/json" -d '{"username":"alice","password":"pass12345"}'
HTTP/1.1 200 OK
Content-Type: application/json
{"refresh":"eyJhbGciOiJI...","access":"eyJhbGciOiJI..."}

$ curl -i -X POST http://127.0.0.1:8000/api/v1/auth/jwt/logout/ -H "Content-Type: application/json" -d '{"refresh":"<REFRESH>"}'
HTTP/1.1 200 OK
Content-Type: application/json
{}

$ curl -i -X POST http://127.0.0.1:8000/api/v1/auth/jwt/refresh/ -H "Content-Type: application/json" -d '{"refresh":"<REFRESH>"}'
HTTP/1.1 401 Unauthorized
{"detail":"Token is blacklisted","code":"token_not_valid"}
```

### 2. Право доступу: дозволено і заборонено

```
$ curl -i http://127.0.0.1:8000/api/v1/books/
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api"

$ curl -i http://127.0.0.1:8000/api/v1/books/ -H "Authorization: Bearer <ACCESS alice>"
HTTP/1.1 200 OK

$ curl -i -X DELETE http://127.0.0.1:8000/api/v1/books/1/ -H "Authorization: Bearer <ACCESS alice>"
HTTP/1.1 403 Forbidden

$ curl -i -X DELETE http://127.0.0.1:8000/api/v1/books/1/ -H "Authorization: Bearer <ACCESS staff>"
HTTP/1.1 204 No Content
```

### 3. Throttling: останній дозволений запит і `429`

```
$ curl -i http://127.0.0.1:8000/api/v1/authors/      (запити 1-7)
HTTP/1.1 200 OK

$ curl -i http://127.0.0.1:8000/api/v1/authors/      (запит 8)
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
```

### 4. Інтеграційна вимога (CORS)

```
$ curl -i -X OPTIONS http://127.0.0.1:8000/api/v1/books/ -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization, content-type, x-client-version"
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:3000
access-control-allow-headers: accept, authorization, content-type, user-agent, x-csrftoken, x-requested-with, x-client-version
access-control-allow-methods: DELETE, GET, OPTIONS, PATCH, POST, PUT

$ curl -i -X OPTIONS http://127.0.0.1:8000/api/v1/books/ -H "Origin: http://evil.example" -H "Access-Control-Request-Method: POST"
HTTP/1.1 200 OK
(заголовка Access-Control-Allow-Origin немає)
```

## Журнал помилок

| Що побачили | Причина | Що змінили |
|---|---|---|
| `zsh: command not found: python` | на macOS поза venv є тільки `python3` | створив venv через `python3 -m venv venv`, активував його, після цього `python` працює |
| Після JWT і права впало 7 тестів: `(None, None) != (7, 3600)` у throttling і `401 != 200` на preflight у CORS | у settings іще не було лімітів і `corsheaders` | додав `DEFAULT_THROTTLE_RATES` і CORS, `CorsMiddleware` поставив над `CommonMiddleware` |

## Дослідницькі питання

**1. Claims у access і refresh.** Я розкодував обидва токени. В обох є `token_type`, `exp`, `iat`, `jti` і `user_id`. Відрізняє їх сервер за `token_type`: там або `access`, або `refresh`. Тому якщо підставити refresh у `Authorization: Bearer`, буде 401. Дивився в `rest_framework_simplejwt/tokens.py` і документацію simplejwt.

**2. ROTATE_REFRESH_TOKENS і BLACKLIST_AFTER_ROTATION.** Разом вони працюють так: кожен запит на `/refresh/` повертає новий refresh, а старий одразу йде в чорний список. Тобто один refresh можна використати лише раз. Якщо його вкрадуть, після використання він уже не спрацює. Джерело: розділ Settings у документації simplejwt.

**3. Старий access після logout.** Я зробив запит `GET /api/v1/books/` зі старим access після logout і отримав **200 OK**. Так виходить, бо logout кладе в чорний список тільки refresh, а access JWT перевіряється лише за підписом і `exp`, сервер його ніде не зберігає. Тому відкликати access до кінця строку не можна, і `ACCESS_TOKEN_LIFETIME` треба тримати коротким (у мене 15 хв). Джерело: документація simplejwt, розділ про blacklist.

**4. Порядок перевірок.** У методі `APIView.initial()` DRF спочатку викликає `perform_authentication`, потім `check_permissions`, і лише потім `check_throttles` (файл `rest_framework/views.py`). Тому анонім, якого право вже відхилило з 401, до throttling не доходить і ліміт не витрачає. У моєму варіанті анонім на `/books/` отримує 401 і не рахується, а ліміт 7/год рахується на відкритому `/authors/`.

## Якщо користувались ШІ

та там просто якшо якась помилка то я кидав АІ і він мені пояснював як т пофіксити 