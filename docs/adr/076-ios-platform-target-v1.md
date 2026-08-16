# ADR 076 — iOS Platform Target v1

## Status

Accepted.

## Context

SirisOS's Flutter client (`apps/mobile`) had only ever been built and run as `flutter run -d web-server`. Brad confirmed mid-sprint that SirisOS is intended to eventually be a native iOS app, not just a web client, so the mobile app needs an actual iOS platform target to build against rather than adding that scaffolding later as a bigger, riskier one-off migration.

Standing this up surfaced a real, non-obvious environment problem rather than just a Flutter config change:

- The default `IPHONEOS_DEPLOYMENT_TARGET` (13.0) that `flutter create` writes is incompatible with this machine's Xcode 27 beta, whose SDK requires 15.0–27.0.x.
- No CocoaPods/Homebrew are installed on this machine. Flutter 3.44.9's Swift Package Manager support for iOS plugin dependencies works as a CocoaPods-free path and was used instead — confirmed resolving `file_picker`'s transitive deps (`DKImagePickerController`, `DKCamera`, `DKPhotoGallery`, `SDWebImage`, `SwiftyGif`, `TOCropViewController`) via SPM.
- `codesign` reliably rejected the built `Flutter.framework` with "resource fork, Finder information, or similar detritus not allowed." Root cause, confirmed by comparing extended attributes across several candidate locations: the project worktree lived under `~/Documents`, which is synced by iCloud Drive's "Desktop & Documents Folders" feature. macOS's File Provider extension tags files and directories it manages with `com.apple.FinderInfo` and `com.apple.fileprovider.fpfs#P` in addition to the otherwise-harmless `com.apple.provenance` — and that combination is what `codesign` rejects. This also explained earlier apparent flakiness: the sync daemon re-applies the attributes periodically, so a one-off `xattr -c` only ever held briefly.

## Decision

Two changes:

1. Scaffold `apps/mobile/ios/` via `flutter create --platforms=ios .`, with `IPHONEOS_DEPLOYMENT_TARGET` raised from 13.0 to 16.0 across the three build configurations in `Runner.xcodeproj/project.pbxproj` to match this Xcode toolchain's supported range. `pubspec.lock`, `.metadata`, and the mobile-root `.gitignore` that `flutter create` generates are committed alongside it, matching standard Flutter-app (not package) convention.
2. The git worktree this project lives in was relocated from `~/Documents/sirisos-worktrees/next-slice` to `~/dev/sirisos-worktrees/next-slice` — outside any iCloud Drive-synced folder — via `git worktree move`, which correctly updates git's own worktree bookkeeping rather than leaving a stray filesystem copy. This is the actual fix for the codesign failure; the deployment-target bump was necessary but not sufficient on its own.

The default `flutter create` boilerplate widget test (`apps/mobile/test/widget_test.dart`, a counter-app smoke test referencing a nonexistent `MyApp`) was deliberately not committed — it doesn't match this app and would fail if run.

## Consequences

- `flutter run -d <simulator-udid>` now builds, code-signs, installs, and launches SirisOS on the iOS Simulator (verified end-to-end on an iPhone 17 Pro simulator: the app launched to the real sign-in screen).
- Any future clone or worktree of this repo used for iOS development must live outside an iCloud Drive-synced directory (or any other File-Provider-managed location) on macOS, or it will hit the same codesign failure. This is a machine/filesystem-placement constraint, not something fixable from within the repo.
- The local Flutter SDK patch made earlier during diagnosis (`flutter_tools/lib/src/ios/mac.dart`, adding an `xattr -c` fallback) is machine-local, outside this repo, and turned out not to be the actual fix — it's harmless extra insurance and was left in place rather than reverted, but the worktree relocation is the change that matters.
- Android platform support was not scaffolded — out of scope for this ADR; the only confirmed target is iOS.
- Pre-existing `" 2.py"` / `" 2.dart"`-suffixed files scattered through the tree (from an earlier, unrelated iCloud sync conflict, predating the relocation) were left untouched and uncommitted — cleanup is a separate, smaller task from standing up the iOS target.
