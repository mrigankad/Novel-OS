/** Relationship labels offered in the Add Relationship form. */
export const BOND_OPTIONS = [
  ...(
    [
      "ally",
      "rival",
      "family",
      "romantic",
      "mentor",
      "enemy",
      "owes debt",
      "secret",
      "unknown",
    ] as const
  ).map((v) => ({
    value: v,
    label: v[0].toUpperCase() + v.slice(1),
  })),
  { value: "other" as const, label: "Other" },
];
