import { Fragment, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

/** What kind of thing a purchase is (8.22), from its name, brand and shop: a sort for lists, not a record, so a miss lands in Other. */
const CATEGORIES: [string, RegExp][] = [
  ["Computers and electronics", /\b(macbook|laptop|computer|pc|monitor|keyboard|mouse|ipad|iphone|phone|tablet|tv|television|speaker|soundbar|headphones?|earbuds?|airpods?|airtag|camera|router|switch|unifi|mesh|deco|synology|nas|hard ?drive|hdd|ssd|usb|hub|cable|charger|printer|console|playstation|xbox|nintendo|gaming|tp-?link|wifi|controller|jb ?hi-?fi|scorptec|officeworks|noel leeming|harvey norman|good guys|apple|sony|samsung|logitech)\b/i],
  ["Appliances", /\b(fridge|freezer|dishwasher|washing machine|washer|dryer|oven|microwave|vacuum|dyson|kettle|toaster|coffee machine|air ?fryer|heater|air ?con|fan|purifier|dehumidifier|bbq|barbecue|barbeques?|cooktop|rangehood|blender|shaver|trimmer|hair ?dryer|cpap|sleep apnea)\b/i],
  ["Tools and garden", /\b(drill|saw|tools?|toolbox|ladder|mower|blower|hose|garden|spanner|wrench|workbench|workstand|bunnings|ryobi|makita|dewalt|milwaukee|stihl|plants?)\b/i],
  ["Furniture and home", /\b(sofa|couch|chair|table|desk|bed|mattress|pillow|bedding|sheets?|sht|quilt|qlt|doona|towels?|twl|bth mat|bath mat|rug|lamp|light|shelf|shelves|storage|drawer|cabinet|wardrobe|curtain|blind|neon|sign|frame|mirror|ikea|kitchen|cookware|steamer|dinner set|plates|pan|knife|bath|sheridan|house|adairs)\b/i],
  ["Clothing and accessories", /\b(shirts?|t-shirt|pants|jeans|jacket|coat|shoes?|boots?|sneakers?|footwear|dress|suit|tie|belt|wallet|bag|sunglass(es)?|ray-?ban|rb\d{4}|clothing|apparel|activewear|knitwear|jumpsuit|top|shorts|pyjamas?|lululemon|lskd|tarocash|connor|aquila|yd|uniqlo|nike|adidas|myer|river island|mani[eè]re de voir|mountain warehouse|endura|torpedo7)\b/i],
  ["Sport and outdoors", /\b(bike|bicycle|e-?bike|cycling|cycles|helmet|saddle|bontrager|gym|weights|dumbbell|kettlebell|treadmill|yoga|sport|golf|tennis|fitness|macpac|sleeping (bag|mat)|inflate|tent|hiking|camping)\b/i],
  ["Health and care", /\b(skin|doctor|medical|pharmacy|chemist|dental|dentist|physio|optometrist|opsm|optical|eyewear|eyeglass(es)?|glasses|contact lens|health|clinic|consultation|spot check|spa|massage)\b/i],
  ["Travel and stays", /\b(hotel|motel|resort|accommodation|airbnb|flight|airline|qantas|jetstar|mantra|vibe|hostel|car hire|rental car)\b/i],
  ["Car and fuel", /\b(fuel|petrol|unleaded|diesel|shell|otr|bp|ampol|caltex|tyres?|car service|rego|registration|parking|toll|repco|subaru|outback|automotive|auto parts|wiper|globe-h7)\b/i],
  ["Home and bills", /\b(rent|lease|property|real estate|mcgrath|council|rates|electricity|gas|water bill|internet|insurance)\b/i],
  ["Software and subscriptions", /\b(claude|anthropic|openrouter|soundiiz|subscription|prepaid|credits|software|licen[cs]e|app store|google one|icloud|netflix|spotify)\b/i],
  ["Food and drink", /\b(pasta|grill'?d|meal|restaurant|cafe|pizza|burger|uber eats|menulog|doordash|takeaway)\b/i],
  ["Going out and gift cards", /\b(tickets?|movie world|theme parks?|hoyts|cinemas?|eventbrite|tour|concert|game|gift card|grand theft auto|gta|steam|voucher)\b/i],
  ["Courses and learning", /\b(nmit|course|tafe|university|training|tuition|enrol(ment)?)\b/i],
];
export const OTHER = "Other";

/** The first of `words` that says what it is wins: a thing's own name before its brand or shop, so a dishwasher from an
 * electronics shop is still an appliance. */
export function categoryOf(...words: (string | null | undefined)[]): string {
  for (const text of words) {
    const found = text && CATEGORIES.find(([, re]) => re.test(text));
    if (found) return found[0];
  }
  return OTHER;
}

/** The latest few (`latest` sorts newest first), with a button to see every item sorted into categories (8.22). */
export function LatestThenGrouped<T>({ items, latest = 5, label, category, newest, render }: {
  items: readonly T[]; latest?: number; label: string; category: (item: T) => string; newest: (a: T, b: T) => number; render: (item: T) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const sorted = [...items].sort(newest);
  const groups = new Map<string, T[]>();
  for (const item of sorted) {
    const c = category(item);
    groups.set(c, [...(groups.get(c) ?? []), item]);
  }
  const names = [...groups.keys()].sort((a, b) => (a === OTHER ? 1 : b === OTHER ? -1 : a.localeCompare(b)));
  return (
    <>
      {open ? (
        names.map((name) => (
          <Fragment key={name}>
            <h3 className="grouped__head">{name} <span className="muted">{groups.get(name)!.length}</span></h3>
            <ul className="items" aria-label={`${label}: ${name}`}>{groups.get(name)!.map(render)}</ul>
          </Fragment>
        ))
      ) : (
        <ul className="items" aria-label={`Latest ${label}`}>{sorted.slice(0, latest).map(render)}</ul>
      )}
      {sorted.length > latest && (
        <button type="button" className="show-more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
          {open ? `Just the latest ${latest}` : `Show all ${sorted.length}, by category`}
        </button>
      )}
    </>
  );
}
