/**
 * Icon registry Lucide static SVGs (ISC) downloaded from unpkg lucide-static@0.525.0
 * Brand mark is original Novel OS art in ../assets/brand/
 */
import library from "../assets/icons/library.svg?raw";
import search from "../assets/icons/search.svg?raw";
import bookOpen from "../assets/icons/book-open.svg?raw";
import layoutDashboard from "../assets/icons/layout-dashboard.svg?raw";
import layers from "../assets/icons/layers.svg?raw";
import layoutGrid from "../assets/icons/layout-grid.svg?raw";
import folderTree from "../assets/icons/folder-tree.svg?raw";
import stickyNote from "../assets/icons/sticky-note.svg?raw";
import users from "../assets/icons/users.svg?raw";
import mapPin from "../assets/icons/map-pin.svg?raw";
import landmark from "../assets/icons/landmark.svg?raw";
import pkg from "../assets/icons/package.svg?raw";
import shield from "../assets/icons/shield.svg?raw";
import shieldAlert from "../assets/icons/shield-alert.svg?raw";
import triangleAlert from "../assets/icons/triangle-alert.svg?raw";
import circleCheck from "../assets/icons/circle-check.svg?raw";
import circleAlert from "../assets/icons/circle-alert.svg?raw";
import pencil from "../assets/icons/pencil.svg?raw";
import penLine from "../assets/icons/pen-line.svg?raw";
import scissors from "../assets/icons/scissors.svg?raw";
import palette from "../assets/icons/palette.svg?raw";
import compass from "../assets/icons/compass.svg?raw";
import sparkles from "../assets/icons/sparkles.svg?raw";
import messageSquare from "../assets/icons/message-square.svg?raw";
import image from "../assets/icons/image.svg?raw";
import history from "../assets/icons/history.svg?raw";
import gitBranch from "../assets/icons/git-branch.svg?raw";
import fileText from "../assets/icons/file-text.svg?raw";
import download from "../assets/icons/download.svg?raw";
import upload from "../assets/icons/upload.svg?raw";
import plus from "../assets/icons/plus.svg?raw";
import chevronRight from "../assets/icons/chevron-right.svg?raw";
import arrowLeft from "../assets/icons/arrow-left.svg?raw";
import eye from "../assets/icons/eye.svg?raw";
import focus from "../assets/icons/focus.svg?raw";
import bot from "../assets/icons/bot.svg?raw";
import brain from "../assets/icons/brain.svg?raw";
import scrollText from "../assets/icons/scroll-text.svg?raw";
import notebookPen from "../assets/icons/notebook-pen.svg?raw";
import clapperboard from "../assets/icons/clapperboard.svg?raw";
import waypoints from "../assets/icons/waypoints.svg?raw";

export const ICONS = {
  library,
  search,
  "book-open": bookOpen,
  "layout-dashboard": layoutDashboard,
  layers,
  "layout-grid": layoutGrid,
  "folder-tree": folderTree,
  "sticky-note": stickyNote,
  users,
  "map-pin": mapPin,
  landmark,
  package: pkg,
  shield,
  "shield-alert": shieldAlert,
  "triangle-alert": triangleAlert,
  "circle-check": circleCheck,
  "circle-alert": circleAlert,
  pencil,
  "pen-line": penLine,
  scissors,
  palette,
  compass,
  sparkles,
  "message-square": messageSquare,
  image,
  history,
  "git-branch": gitBranch,
  "file-text": fileText,
  download,
  upload,
  plus,
  "chevron-right": chevronRight,
  "arrow-left": arrowLeft,
  eye,
  focus,
  bot,
  brain,
  "scroll-text": scrollText,
  "notebook-pen": notebookPen,
  clapperboard,
  waypoints,
} as const;

export type IconName = keyof typeof ICONS;

/** Feature → icon mapping for P1–P7 surfaces */
export const FEATURE_ICONS = {
  library: "library",
  search: "search",
  dashboard: "layout-dashboard",
  binder: "folder-tree",
  corkboard: "layout-grid",
  outliner: "layers",
  research: "sticky-note",
  architect: "compass",
  scribe: "pen-line",
  editor: "scissors",
  guardian: "shield",
  curator: "palette",
  continuity: "shield-alert",
  continuityOk: "circle-check",
  continuityWarn: "triangle-alert",
  continuityCrit: "circle-alert",
  codex: "book-open",
  character: "users",
  location: "map-pin",
  worldbuilding: "landmark",
  item: "package",
  comments: "message-square",
  portraits: "image",
  provenance: "git-branch",
  consequence: "waypoints",
  snapshots: "history",
  export: "download",
  focus: "focus",
  agents: "bot",
  manuscript: "scroll-text",
  draft: "notebook-pen",
  scene: "clapperboard",
  spark: "sparkles",
  preview: "eye",
  add: "plus",
  back: "arrow-left",
  next: "chevron-right",
  upload: "upload",
  file: "file-text",
  write: "pencil",
  think: "brain",
} as const satisfies Record<string, IconName>;
