# SirisOS Flutter App

Cross-platform SirisOS client targeting iOS, Android, web, macOS, and Windows.

## First-time setup

Generate the local Flutter platform wrappers, then install dependencies:

```bash
cd apps/mobile
flutter create --platforms=ios,android,web,macos,windows .
flutter pub get
flutter run
```

The committed SirisOS code lives under `lib/`; generated platform files can then be committed in a later milestone once the target platforms are confirmed.

## Current milestone

- Material 3 dark theme
- Responsive dashboard layout
- Reusable dashboard cards
- Bottom navigation shell
- Initial daily briefing panel

The dashboard currently uses placeholder data. The next frontend milestone will connect it to the FastAPI backend.
