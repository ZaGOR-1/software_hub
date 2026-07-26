# Protected download delivery

Phase 12 adds the public file-delivery boundary for published `ReleaseFile`
records. FastAPI authorizes metadata and accounts the start; Nginx serves the
physical bytes. Python never reads the download body.

## Routes

```text
GET  /download/{public_uuid}/{safe_filename}
HEAD /download/{public_uuid}/{safe_filename}
```

The public UUID is an unguessable lookup identifier, not an authorization token.
The requested filename must exactly match the stored display filename. This keeps
URLs readable while preventing alternate filename aliases from being accepted.

## Authorization chain

A request is granted only when every relevant layer is eligible:

```text
Software
└── Release
    └── ReleaseFile
```

The service verifies:

1. the public UUID exists;
2. the cosmetic URL filename exactly matches metadata;
3. the complete Software, Release and ReleaseFile policy allows delivery;
4. private content has a valid administrator session;
5. the physical file resolves inside managed storage;
6. the file is in permanent `software` storage, never quarantine or temporary;
7. the physical byte size matches metadata.

Denied public requests receive the same generic `404` response. The response does
not reveal whether a UUID, filename, lifecycle state, visibility state or physical
file caused the denial.

## Visibility semantics

- `public`: available without authentication when the full lifecycle chain is
  published and enabled;
- `unlisted`: omitted from future catalog listings but available by direct URL;
- `private`: available only when the request carries a valid active administrator
  session.

The administrator session cookie uses `Path=/` because `/download/...` is outside
`/admin`. It remains opaque, `HttpOnly`, `SameSite=Lax` and `Secure` in production.
Routes that do not explicitly declare an authentication dependency do not resolve
or use the session.

## X-Accel-Redirect flow

```text
Client
→ GET /download/{uuid}/{filename}
→ FastAPI metadata and storage checks
→ empty upstream response + X-Accel-Redirect
→ Nginx internal location
→ file bytes from permanent storage
```

The internal header has the form:

```text
X-Accel-Redirect: /protected-downloads/aa/bb/<server-generated-name>.zip
```

Nginx maps that URI through an `internal` alias. A client request to the same
internal URI is rejected with `404`.

FastAPI deliberately does **not** set the physical file length on its empty
response. Doing so would violate the ASGI response contract because the upstream
body contains zero bytes. After processing `X-Accel-Redirect`, Nginx reads the
file metadata and emits the actual `Content-Length`.

## Response metadata

The application emits only header-safe values:

- `Content-Disposition: attachment` with an ASCII fallback and RFC 5987 UTF-8
  `filename*` value;
- a validated simple media type or `application/octet-stream` fallback;
- `ETag` derived from the stored SHA-256 value;
- `Accept-Ranges: bytes`;
- `Cache-Control: no-store`, or `private, no-store` for private content.

User-controlled data never becomes an internal storage path. The Nginx redirect
uses only the stored server-generated relative path.

## GET, HEAD and range semantics

### GET

After all checks pass, the service atomically increments:

- `ReleaseFile.download_count`;
- daily `DownloadStat.download_count`;
- daily `DownloadStat.successful_download_count`.

The increment happens before Nginx sends the body. Therefore the MVP metric means
**authorized download start**, not confirmed transfer completion.

A range request is still an authorized GET start and increments the counter once.
Nginx handles the byte range and returns `206 Partial Content`.

### HEAD

HEAD runs the same authorization and physical-file checks but never increments
successful or total download counters. Nginx returns the actual file headers,
including the physical `Content-Length`, without a body.

### Blocked attempts

Known records denied because of a filename mismatch or lifecycle/visibility chain
increment only the UTC daily `blocked_download_count`. Unknown UUIDs and storage
integrity failures do not create a statistic row because no safe successful
identity is available or the problem is operational rather than a client policy
denial.

Accounting failure for a blocked request is best-effort and never changes the
public generic `404`. Authorized-start accounting is part of the required grant
flow and fails closed if the transaction cannot be committed.

## Nginx configuration

Phase 12 provides a non-TLS integration configuration:

```nginx
location ^~ /protected-downloads/ {
    internal;
    alias /srv/software-hub/storage/software/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
}

location ^~ /download/ {
    limit_req zone=download_requests burst=40 nodelay;
    include /etc/nginx/snippets/proxy_headers.conf;
    proxy_pass http://$software_hub_app;
}
```

The production container phase must ensure:

- the app and Nginx agree on the internal prefix;
- Nginx has read-only access to permanent software storage;
- Nginx has no mount for temporary, quarantine, database or backup data;
- shared UID/GID and directory permissions permit read access without broadening
  storage permissions;
- TLS, HTTP redirect and final security headers are enabled;
- the application port is not exposed directly to the public network.

## Rate limiting

A dedicated Nginx `limit_req_zone` protects the `/download/` authorization path.
The initial integration configuration permits 20 requests per second per client
address with a burst of 40. These values are deployment defaults, not an upstream
volumetric DDoS solution.

## Test coverage

Phase 12 tests cover:

- public, unlisted and private files;
- valid and invalid administrator sessions;
- file, release and software lifecycle denial;
- exact filename matching and Unicode attachment names;
- missing, quarantined and size-mismatched physical files;
- total/daily successful and blocked counters;
- HEAD without successful accounting;
- safe media-type fallback and Content-Disposition generation;
- direct internal URI denial;
- real Uvicorn → Nginx internal redirect;
- actual Nginx `Content-Length`;
- byte range response `206` and resumed body bytes.

## Out of scope

Phase 12 does not add:

- public catalog pages or a download button in the public UI;
- confirmed-completion analytics from Nginx access logs;
- CDN or object storage;
- signed expiring public URLs;
- TLS/certbot or final production container permissions;
- reconciliation of missing/orphan files.
