// M5 is a fully anonymized competition dataset - there's no real product
// name anywhere in it, only category/department/item numbers and
// state/store numbers. These format the codes into readable text; they
// are not real product names (those don't exist in this dataset).

const STATE_NAMES: Record<string, string> = {
  CA: "California",
  TX: "Texas",
  WI: "Wisconsin",
};

const CATEGORY_NAMES: Record<string, string> = {
  FOODS: "Foods",
  HOUSEHOLD: "Household",
  HOBBIES: "Hobbies",
};

export function formatStoreLabel(storeId: string): string {
  const [state, num] = storeId.split("_");
  if (!num) return storeId;
  return `${STATE_NAMES[state] ?? state} · Store ${num}`;
}

export function formatItemLabel(itemId: string): string {
  const parts = itemId.split("_");
  if (parts.length < 3) return itemId;
  const [category, dept, item] = parts;
  return `${CATEGORY_NAMES[category] ?? category} · Dept ${dept} · Item ${item}`;
}

export function formatSeriesLabel(storeId: string, itemId: string): string {
  return `${formatStoreLabel(storeId)} — ${formatItemLabel(itemId)}`;
}
