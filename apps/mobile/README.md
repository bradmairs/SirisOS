# SirisOS Flutter App

Cross-platform SirisOS client targeting iOS, Android, web, macOS, and Windows.

## First-time setup

Generate the local Flutter platform wrappers, then install dependencies:

```bash
cd apps/mobile
flutter create --platforms=ios,android,web,macos,windows .
flutter pub get
```

## Run with the backend

Start the backend from the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Then run Flutter with the address that the target device can use to reach the backend.

Desktop or web on the same computer:

```bash
flutter run --dart-define=SIRISOS_API_URL=http://localhost:8000
```

Android emulator:

```bash
flutter run --dart-define=SIRISOS_API_URL=http://10.0.2.2:8000
```

iOS simulator generally supports `http://localhost:8000`. For a physical phone, replace the URL with the LAN address of the computer or server running FastAPI, for example:

```bash
flutter run --dart-define=SIRISOS_API_URL=http://192.168.1.50:8000
```

## Current milestone

- Material 3 dark theme
- Responsive live dashboard
- Functional bottom navigation with retained tab state
- Live Homelab Docker summary and container list
- Container running, stopped, and health badges
- Loading, retry, offline, and empty states
- Pull-to-refresh
- Configurable API base URL

The Homelab tab reads from `GET /api/v1/homelab/docker`. Docker access remains read-only through the socket proxy configured in the repository-level Compose stack.
