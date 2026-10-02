/** The living backdrop the glass refracts. Purely decorative. */
export function Wallpaper() {
  return (
    <div className="wallpaper" aria-hidden="true">
      <div className="wallpaper__blob" />
      <div className="wallpaper__blob" />
      <div className="wallpaper__blob" />
      <div className="wallpaper__blob" />
      <div className="wallpaper__grain" />
    </div>
  );
}
