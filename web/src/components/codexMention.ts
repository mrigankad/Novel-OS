import { Mark, mergeAttributes } from "@tiptap/core";

export type CodexMentionAttrs = {
  entryId: string;
  entryType: string;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    codexMention: {
      setCodexMention: (attrs: CodexMentionAttrs) => ReturnType;
      unsetCodexMention: () => ReturnType;
    };
  }
}

/** Inline mark linking prose to a Codex entry (manual link only in v1). */
export const CodexMention = Mark.create({
  name: "codexMention",
  inclusive: false,
  excludes: "link",

  addAttributes() {
    return {
      entryId: {
        default: null,
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-codex-id"),
        renderHTML: (attrs) => (attrs.entryId ? { "data-codex-id": attrs.entryId } : {}),
      },
      entryType: {
        default: "character",
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-codex-type") || "character",
        renderHTML: (attrs) => ({ "data-codex-type": attrs.entryType || "character" }),
      },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-codex-id]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["span", mergeAttributes({ class: "pm-codex-mention" }, HTMLAttributes), 0];
  },

  addCommands() {
    return {
      setCodexMention:
        (attrs) =>
        ({ commands }) =>
          commands.setMark(this.name, attrs),
      unsetCodexMention:
        () =>
        ({ commands }) =>
          commands.unsetMark(this.name),
    };
  },
});
