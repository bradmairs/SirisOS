# ADR 077 — iOS Sign-In UI Test v1

## Status

Accepted.

## Context

ADR 076 got SirisOS building, code-signing and launching on the iOS Simulator, but stopped short of verifying the sign-in flow itself — interactive testing (tapping fields, typing, submitting) went through Claude Code's built-in iOS Simulator control tool, which turned out to be running in a disabled state on this installation. Device-level logs confirmed touches were reaching the app and even triggering genuine UIKit keyboard-focus requests, but no typed text ever landed in a field and the tool eventually stopped responding entirely ("Claude Code iOS Simulator has stopped retrying after repeated crashes"). That tool is a third-party convenience layer, not part of the iOS toolchain itself, so its failure blocked *interactive verification*, not the app.

## Decision

Added a standard Apple XCUITest target (`RunnerUITests`, via the `xcodeproj` Ruby gem rather than hand-editing `project.pbxproj`) that drives the real sign-in flow through `xcodebuild test` — completely independent of Claude Code's simulator tool. `RunnerUITests/RunnerUITests.swift` launches the app, fills in the username/password fields, taps "Sign in", and lets the flow run.

Two non-obvious things had to be worked around to make it pass:
- Flutter's `obscureText` password field does not expose itself as `XCUIElementTypeSecureTextField` on this iOS version — XCTest reports an "Automation type mismatch: computed TextField from legacy attributes vs Other from modern attribute" and the field is only reliably found via a broad `NSPredicate` match on label/value across `app.descendants(matching: .any)`, not a typed `secureTextFields` or `textFields` query.
- The username field arrives pre-filled (persisted from a prior session), so blindly tapping and typing into it produces a corrupted value (`bradbrad`) and a 401 — the test now clears existing content first.

Test parallelization was also disabled in the scheme (`parallelizable = "NO"` on both testables, plus `-disable-concurrent-testing`): `xcodebuild` was cloning the simulator to run tests in parallel, and the second clone reliably failed to launch and burned a fixed 600-second timeout on every run for no benefit with a single test method.

## Consequences

- `xcodebuild test -workspace Runner.xcworkspace -scheme Runner -destination "id=<udid>" -only-testing:RunnerUITests -disable-concurrent-testing` is now a real, repeatable way to verify the iOS build's interactive behavior in CI or locally, independent of any third-party tooling.
- Verified end-to-end against the real backend: the test's login submission produced an actual `POST /api/v1/auth/login` → `200 OK`, followed by the app's normal authenticated dashboard requests — not just a UI-level pass.
- This is a smoke test for one flow (sign-in), not a general UI testing framework — extending coverage to other screens would hit the same "Other" accessibility-type quirk and should reuse the same broad-predicate lookup pattern rather than assuming `textFields`/`secureTextFields` will match.
- Not wired into the `flutter test`/pytest suites or CI (`.github/workflows`) — it requires a booted simulator and is run manually via `xcodebuild`. Wiring it into CI is future work, not part of this slice.
