# Brand: the SirisOS mark

The mark is an ice-blue S inside a HUD ring: two glowing arcs with a dot at
each end on a faint full ring, on black. The wordmark beside it is
**SIRIS**<b>OS</b>: light, widely spaced capitals, with OS in bold ice blue.

## The two S's

| Style | Look | Files |
| --- | --- | --- |
| `bolt` (current, October 2026) | A faceted lightning-bolt S: sharp corners and tapered tips, white at the top through ice to deep blue, darker lower faces and bright top edges | `apps/web/public/siris-mark-bolt.svg`, `siris-icon-bolt.png` |
| `classic` | The original curved S, a round-capped ice-blue stroke | `apps/web/public/siris-mark-classic.svg`, `siris-icon-classic.png` |

Both are drawn in `apps/web/src/components/Logo.tsx` (`LogoMark`, with its
`variant` prop), and `LOGO_STYLE` there picks the one shown everywhere: the
sidebar, the top bar and the sign-in screen. `siris-mark.svg` (the browser
tab icon) and `siris-icon.png` (512 px, the home-screen and PWA icon) are
copies of the chosen style's files.

## Switching

```bash
scripts/use-logo.sh classic   # back to the original S
scripts/use-logo.sh bolt      # the lightning S
make up                       # rebuild
```

iOS keeps a home-screen icon from when the app was added. To see a new one,
remove SirisOS from the home screen and add it again from Safari.

## Exploration

The concepts that led here (eight directions, eight S treatments, and six
lightning takes, of which "Faceted bolt" was chosen) are on the canvas
*SirisOS logo concepts* in Claude.
