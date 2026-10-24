import type { NetNode } from "../api/house";

/** What a device looks like in the house: the small model drawn for it (scene.ts). */
export type DeviceType =
  | "gateway" | "switch" | "ap" | "phone" | "tablet" | "watch" | "laptop" | "desktop" | "server" | "console"
  | "streamer" | "tv" | "frame" | "speaker" | "hub" | "plug" | "light" | "climate" | "vacuum" | "camera"
  | "sensor" | "appliance" | "printer" | "device";

/** Words in a device's name, checked in order (so "Hub - Blink" is a hub, not a camera). */
const BY_NAME: [DeviceType, RegExp][] = [
  ["watch", /\bwatch\b/],
  ["tablet", /\bipad|\btablet|\bgalaxy tab/],
  ["phone", /\biphone|\bphone\b|\bpixel\b|\bgalaxy\b|\bandroid\b/],
  ["laptop", /\bmacbook|\blaptop|\bnotebook|\bthinkpad/],
  ["console", /\bplaystation|\bps[45]\b|\bxbox|\bnintendo/],
  ["streamer", /\bapple tv|\bchromecast|\broku\b|\bshield\b|\bfire ?stick/],
  ["tv", /\btv\b|\btelevision/],
  ["frame", /\bframe\b/],
  ["speaker", /\bhomepod|\becho\b|\bsonos|\bspeaker|\bnest (mini|audio)|\bgoogle home/],
  ["hub", /\bhub\b|\bbridge\b|\bzigbee|\bz-?wave/],
  ["plug", /\bplug\b|\bp1[01]0\b|\bp11\d\b|\bsocket|\boutlet/],
  ["light", /\blight|\bbulb|\blamp\b|\bstrip\b/],
  ["climate", /\bac\b|\baircon|\bair con|\bclimate|\bheat ?pump|\bthermostat/],
  ["vacuum", /\bvacuum|\broomba|\broborock/],
  ["camera", /\bcamera|\bcam\b|\bdoorbell|\bblink\b|\barlo\b/],
  ["sensor", /\bbutton|\bsensor|\bgarage door|\bcontact\b|\bmotion\b/],
  ["appliance", /\bfridge|\bfreezer|\bwasher|\bdryer|\bdishwasher|\boven\b/],
  ["printer", /\bprinter/],
  ["server", /\bserver|\bnas\b|\bsynology|\bunraid|\bproxmox|\bpi\b|\braspberry|\bhome ?assist[ae]nt|\btorrent/],
  ["desktop", /\bwindows|\bdesktop|\bgaming pc|\bpc\b|\bimac|\bmac (mini|studio)/],
];

/** Home Assistant control kinds (the node's model) that have a look of their own. */
const BY_CONTROL: Record<string, DeviceType> = {
  light: "light", switch: "plug", climate: "climate", fan: "climate", media_player: "speaker", vacuum: "vacuum",
  camera: "camera", lock: "sensor", cover: "sensor", binary_sensor: "sensor", sensor: "sensor",
};

export function deviceType(node: Pick<NetNode, "name" | "kind" | "model">): DeviceType {
  if (node.kind === "gateway") return "gateway";
  if (node.kind === "switch") return "switch";
  if (node.kind === "access_point") return "ap";
  const name = node.name.toLowerCase();
  for (const [type, re] of BY_NAME) if (re.test(name)) return type;
  return (node.model && BY_CONTROL[node.model]) || "device";
}
