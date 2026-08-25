#!/usr/bin/env node
/**
 * Create or insert one editable visual-summary slide.
 *
 * The required `RUNTIME_NODE*` variables come exclusively from
 * codex_app__load_workspace_dependencies.  This file deliberately has no
 * dependency discovery or package-install fallback.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";

function usage() {
  return "Usage: build_summary_pptx.mjs --handoff <summary.handoff.json> --out <summary.pptx> [--into <existing.pptx> --after-slide <number>] [--template <designated.pptx> --template-map <frame-map.json>]";
}

function parseArgs(argv) {
  const values = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith("--")) throw new Error(usage());
    const key = argv[i].slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith("--")) throw new Error(`missing value for --${key}`);
    values[key] = value;
    i += 1;
  }
  if (!values.handoff || !values.out) throw new Error(usage());
  if (values["after-slide"] && !values.into) throw new Error("--after-slide requires --into");
  if (values.template && values.into) throw new Error("--template is destination-template mode and cannot be combined with --into");
  if (values.template && !values["template-map"]) throw new Error("--template requires an explicit --template-map produced from the complete source-slide inventory");
  if (values["template-map"] && !values.template) throw new Error("--template-map requires --template");
  return values;
}

function rasterDimensions(bytes, contentType) {
  if (contentType === "image/png" && bytes.length >= 24 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
  }
  if (contentType === "image/webp" && bytes.length >= 30 && bytes.toString("ascii", 0, 4) === "RIFF" && bytes.toString("ascii", 8, 12) === "WEBP" && bytes.toString("ascii", 12, 16) === "VP8X") {
    return [bytes.readUIntLE(24, 3) + 1, bytes.readUIntLE(27, 3) + 1];
  }
  if (contentType === "image/jpeg" && bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 0xff) { offset += 1; continue; }
      const marker = bytes[offset + 1];
      offset += 2;
      if (marker === 0xd8 || marker === 0xd9) continue;
      if (offset + 2 > bytes.length) break;
      const length = bytes.readUInt16BE(offset);
      if (length < 2 || offset + length > bytes.length) break;
      if ((marker >= 0xc0 && marker <= 0xc3) || (marker >= 0xc5 && marker <= 0xc7) || (marker >= 0xc9 && marker <= 0xcb) || (marker >= 0xcd && marker <= 0xcf)) {
        return [bytes.readUInt16BE(offset + 5), bytes.readUInt16BE(offset + 3)];
      }
      offset += length;
    }
  }
  throw new Error("embedded artwork has unsupported or mismatched raster bytes");
}

async function readBoundedJson(filePath) {
  const stat = await fs.lstat(filePath);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size <= 0 || stat.size > 8 * 1024 * 1024) {
    throw new Error("handoff must be a regular non-symlink JSON file no larger than 8 MiB");
  }
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

async function requireBoundedRegular(filePath, label, maximum) {
  const stat = await fs.lstat(filePath);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size <= 0 || stat.size > maximum) {
    throw new Error(`${label} must be a bounded regular local file`);
  }
  return stat;
}

function requireRuntime() {
  if (!process.env.RUNTIME_NODE || !process.env.RUNTIME_NODE_MODULES || !process.env.RUNTIME_BIN_DIR || !process.env.RUNTIME_PYTHON) {
    throw new Error("workspace runtime is unavailable; run codex_app__load_workspace_dependencies and set RUNTIME_NODE, RUNTIME_NODE_MODULES, RUNTIME_BIN_DIR, and RUNTIME_PYTHON");
  }
}

async function loadArtifactTool() {
  const moduleRoot = process.env.RUNTIME_NODE_MODULES;
  if (!moduleRoot) {
    throw new Error("RUNTIME_NODE_MODULES is required to load @oai/artifact-tool");
  }
  const entry = path.join(moduleRoot, "@oai", "artifact-tool", "dist", "artifact_tool.mjs");
  try {
    return await import(pathToFileURL(entry).href);
  } catch (error) {
    throw new Error(`unable to load @oai/artifact-tool from workspace runtime: ${error?.message || error}`);
  }
}

function color(value, fallback) {
  return typeof value === "string" && value ? value : fallback;
}

function addText(slide, name, text, position, style) {
  // Artifact Tool serializes all rectangles through OOXML transform extents.
  // A zero-width/zero-height line or malformed handoff coordinate otherwise
  // fails only at export time with an opaque "extents must be non-negative"
  // message.  Keep native text editable, but make its physical frame safe at
  // the builder boundary.
  const safePosition = {
    left: Math.max(0, Number(position.left) || 0),
    top: Math.max(0, Number(position.top) || 0),
    width: Math.max(1, Number(position.width) || 1),
    height: Math.max(1, Number(position.height) || 1),
  };
  const shape = slide.shapes.add({
    geometry: "textbox", name, position: safePosition, fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = String(text || "");
  shape.text.style = style;
  return shape;
}

function safeLinePosition(first, second) {
  // OOXML connector extents must be positive.  Keep exactly-horizontal and
  // exactly-vertical storyboard/feedback strokes visible with a one-pixel
  // physical extent instead of relying on a backend-specific zero-size line.
  return {
    left: Math.max(0, Math.min(Number(first.x) || 0, Number(second.x) || 0)),
    top: Math.max(0, Math.min(Number(first.y) || 0, Number(second.y) || 0)),
    width: Math.max(1, Math.abs((Number(second.x) || 0) - (Number(first.x) || 0))),
    height: Math.max(1, Math.abs((Number(second.y) || 0) - (Number(first.y) || 0))),
  };
}

function decodeDataUrl(dataUrl, options = {}) {
  const { context = "image", sha256, requireDigest = false, verifiedBy } = options;
  if (typeof dataUrl !== "string" || !dataUrl.startsWith("data:image/")) return null;
  const match = dataUrl.match(/^data:(image\/(?:png|jpeg|webp|svg\+xml));base64,([A-Za-z0-9+/=]+)$/);
  if (!match) throw new Error(`invalid embedded ${context}`);
  const bytes = Buffer.from(match[2], "base64");
  if (!bytes.length || bytes.length > 1024 * 1024) throw new Error(`embedded ${context} exceeds the bounded byte limit`);
  if (requireDigest && (typeof sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(sha256))) {
    throw new Error(`embedded ${context} lacks a digest receipt`);
  }
  if (requireDigest && createHash("sha256").update(bytes).digest("hex") !== sha256.toLowerCase()) {
    throw new Error(`embedded ${context} changed after approval`);
  }
  if (match[1] === "image/svg+xml") {
    if (verifiedBy !== "oci-visual-summary-passive-svg-v1") {
      throw new Error(`embedded ${context} lacks the verified passive-SVG token`);
    }
    const decoded = bytes.toString("utf8").toLowerCase();
    // The upstream Python allowlist is authoritative. Recheck the independent
    // no-external-reference boundary here so a tampered private handoff cannot
    // redirect the Office renderer even with a syntactically valid XML blob.
    if (!decoded.includes("<svg") || /<(script|style|foreignobject|iframe|object|embed|image|use)\b|<!doctype|<!entity|\bon[a-z]+\s*=|\bstyle\s*=|@import|\b(?:href|xlink:href|src)\s*=\s*["']\s*(?:https?:|data:|javascript:|\/|\.\.?\/)|\burl\(\s*(?:https?:|data:|javascript:|\/|\.\.?\/)/.test(decoded)) {
      throw new Error(`embedded ${context} is not a passive SVG`);
    }
  } else {
    const [pixelWidth, pixelHeight] = rasterDimensions(bytes, match[1]);
    if (pixelWidth <= 0 || pixelHeight <= 0 || pixelWidth > 8192 || pixelHeight > 8192 || pixelWidth * pixelHeight > 16_000_000) {
      throw new Error(`embedded ${context} exceeds the bounded pixel limit`);
    }
  }
  return { contentType: match[1], bytes };
}

function storyboardPageTitle(role) {
  const titles = {
    "project-promise": "Project promise",
    workflow: "Workflow",
    "capability-scenes": "Capability scenes",
    "oci-service-map": "OCI service map",
    "at-a-glance": "At a glance",
  };
  return titles[role] || role || "Storyboard page";
}

function serviceRenderingSemantics(serviceIcon) {
  if (serviceIcon?.rendered_as !== "neutral-service-glyph" || !serviceIcon?.fallback_reason) return "";
  return `Rendered as: neutral-service-glyph (${serviceIcon.fallback_reason})`;
}

function serviceAccessibilityText(serviceIcon, fallback) {
  const semantic = serviceRenderingSemantics(serviceIcon);
  return [serviceIcon?.alt_text || fallback, semantic].filter(Boolean).join(". ");
}

function storyboardSources(handoff, page) {
  const sourceByUrl = new Map((Array.isArray(handoff.source_register) ? handoff.source_register : []).map((item) => [String(item.url || ""), item]));
  const lines = [];
  for (const scene of Array.isArray(page.scenes) ? page.scenes : []) {
    for (const sourceId of Array.isArray(scene.source_ids) ? scene.source_ids : []) {
      const source = sourceByUrl.get(String(sourceId));
      lines.push(source ? `- ${source.title || "Official Oracle documentation"}: ${source.url}` : `- ${String(sourceId)}`);
    }
  }
  for (const serviceIcon of Array.isArray(page.services) ? page.services : []) {
    if (serviceIcon.display_name) {
      const semantic = serviceRenderingSemantics(serviceIcon);
      lines.push(`- ${serviceIcon.display_name}: ${serviceIcon.mapping_type || "service mapping"}${semantic ? `; ${semantic}` : ""}`);
    }
  }
  const unique = [...new Set(lines)];
  return unique.length ? unique.join("\n") : (handoff.evidence_footer || "No public source titles were supplied in the handoff.");
}

function storyboardPhysicalPages(pages) {
  // Mirror the portable renderer's capacity contract.  The public handoff
  // deliberately exposes five audience roles; the Office projection expands
  // only the physical pages needed to keep each editable slide readable.
  const expanded = [];
  for (const page of Array.isArray(pages) ? pages : []) {
    const audienceRole = String(page?.role || "");
    const scenes = Array.isArray(page?.scenes) ? page.scenes.filter(Boolean) : [];
    const services = Array.isArray(page?.services) ? page.services.filter(Boolean) : [];
    if (audienceRole === "capability-scenes") {
      for (const scene of scenes) {
        const matchedServices = services.filter((service) => service?.unit_id && service.unit_id === scene?.unit_id);
        expanded.push({ ...page, role: `capability-scenes-${scene.unit_id || expanded.length + 1}`,
          audience_role: audienceRole, page_number: 1, page_count: 1, scenes: [scene], services: matchedServices.slice(0, 1) });
      }
      continue;
    }
    const sceneChunks = Array.from({ length: Math.max(1, Math.ceil(scenes.length / 4)) }, (_unused, index) => scenes.slice(index * 4, index * 4 + 4));
    const serviceChunks = Array.from({ length: Math.max(1, Math.ceil(services.length / 8)) }, (_unused, index) => services.slice(index * 8, index * 8 + 8));
    const pageCount = Math.max(sceneChunks.length, serviceChunks.length);
    for (let index = 0; index < pageCount; index += 1) {
      expanded.push({ ...page, role: pageCount === 1 ? audienceRole : `${audienceRole}-${index + 1}`,
        audience_role: audienceRole, page_number: index + 1, page_count: pageCount,
        scenes: sceneChunks[index] || [], services: serviceChunks[index] || [] });
    }
  }
  return expanded;
}

async function addStoryboardSlides(presentation, handoff, after) {
  const storyboardPages = storyboardPhysicalPages(handoff.pages);
  let insertionIndex = after;
  for (const [pageIndex, page] of storyboardPages.entries()) {
    // `slides.add()` returns the added slide, while the imported-deck
    // `slides.insert()` mutator returns void. Resolve the inserted slide from
    // the collection so every physical storyboard page has a real canvas.
    let slide;
    if (insertionIndex === undefined) {
      slide = presentation.slides.add();
      insertionIndex = presentation.slides.items.length - 1;
    } else {
      presentation.slides.insert({ after: insertionIndex });
      insertionIndex += 1;
      slide = presentation.slides.items[insertionIndex];
    }
    const width = slide.frame?.width || 1280;
    const height = slide.frame?.height || 720;
    slide.background.fill = "#FFFDF8";
    const role = String(page.role || "");
    const title = page.title || storyboardPageTitle(role);
    addText(slide, `storyboard-title-${pageIndex + 1}`, title, { left: 60, top: 24, width: width - 120, height: 54 },
      { fontSize: 38, bold: true, color: "#18202B" });
    const takeaway = page.takeaway || handoff.takeaway || "";
    if (takeaway) {
      addText(slide, `storyboard-takeaway-${pageIndex + 1}`, takeaway, { left: 60, top: 80, width: width - 120, height: 34 },
        { fontSize: 19, color: "#3C4655" });
    }
    const scenes = Array.isArray(page.scenes) ? page.scenes : [];
    const services = Array.isArray(page.services) ? page.services : [];
    const addScene = (scene, sceneIndex, position, options = {}) => {
      const reviewedScene = scene?.reviewedScene || scene?.artwork || scene?.art;
      const artwork = decodeDataUrl(reviewedScene?.data_url, {
        context: `storyboard scene artwork for ${scene.unit_id || sceneIndex + 1}`,
        sha256: reviewedScene?.sha256,
        requireDigest: true,
      });
      if (artwork) {
        slide.images.add({
          name: `storyboard-scene-image-${pageIndex + 1}-${sceneIndex + 1}`,
          blob: artwork.bytes,
          contentType: artwork.contentType,
          alt: scene.alt_text || `Scene for ${scene.title || scene.unit_id || sceneIndex + 1}`,
          fit: "contain",
          position,
        });
      }
      if (options.titlePosition) {
        addText(slide, `storyboard-scene-heading-${pageIndex + 1}-${sceneIndex + 1}`, options.numbered === false ? (scene.title || "Capability") : `${sceneIndex + 1}. ${scene.title || "Capability"}`, options.titlePosition,
          { fontSize: options.titleSize || 20, bold: true, color: "#18202B" });
      }
      if (options.detailPosition) {
        addText(slide, `storyboard-scene-detail-${pageIndex + 1}-${sceneIndex + 1}`, `${scene.detail || ""}\n${String(scene.evidence_class || "code-backed").toUpperCase()}`, options.detailPosition,
          { fontSize: options.detailSize || 14, color: "#3C4655" });
      }
    };
    const addService = (serviceIcon, serviceIndex, iconPosition, textPosition, options = {}) => {
      const semantic = serviceRenderingSemantics(serviceIcon);
      addText(slide, `storyboard-service-text-${pageIndex + 1}-${serviceIndex + 1}`, [
        serviceIcon.display_name || "OCI service",
        ...(options.compact ? [] : [serviceIcon.mapping_type || "mappingType", semantic]),
      ].filter(Boolean).join("\n"), textPosition,
      { fontSize: options.fontSize || (semantic ? 13 : 15), bold: true, color: "#18202B" });
      const iconRecord = serviceIcon?.icon || serviceIcon?.serviceIcon;
      const icon = decodeDataUrl(iconRecord?.data_url, {
        context: `storyboard service icon for ${serviceIcon.canonical_service_id || serviceIndex + 1}`,
        sha256: iconRecord?.sha256,
        requireDigest: true,
        verifiedBy: iconRecord?.verified_by,
      });
      if (icon) {
        slide.images.add({
          name: `storyboard-service-icon-${pageIndex + 1}-${serviceIndex + 1}`,
          blob: icon.bytes,
          contentType: icon.contentType,
          alt: serviceAccessibilityText(serviceIcon, serviceIcon.display_name || `Service icon ${serviceIndex + 1}`),
          fit: "contain",
          position: iconPosition,
        });
      }
    };
    const roleKey = String(page.audience_role || role);
    if (roleKey === "project-promise" && scenes[0]) {
      addScene(scenes[0], 0, { left: 610, top: 142, width: 590, height: 350 }, {
        titlePosition: { left: 72, top: 180, width: 470, height: 40 }, detailPosition: { left: 72, top: 232, width: 470, height: 110 }, numbered: false, titleSize: 28, detailSize: 18,
      });
      addText(slide, `storyboard-promise-${pageIndex + 1}`, "ONE INCIDENT THREAD\nShared context  •  Clear ownership  •  Faster learning", { left: 72, top: 372, width: 460, height: 86 }, { fontSize: 20, bold: true, color: "#C74634" });
      if (services[0]) addService(services[0], 0, { left: 76, top: 494, width: 72, height: 72 }, { left: 162, top: 500, width: 330, height: 62 }, { fontSize: 18 });
    } else if (roleKey === "workflow") {
      scenes.forEach((scene, sceneIndex) => {
        const left = 45 + sceneIndex * 307;
        addScene(scene, sceneIndex, { left, top: 154, width: 275, height: 164 }, {
          titlePosition: { left, top: 330, width: 275, height: 54 }, numbered: true, titleSize: 19,
        });
        if (services[sceneIndex]) addService(services[sceneIndex], sceneIndex, { left: left + 4, top: 410, width: 62, height: 62 }, { left: left + 76, top: 416, width: 195, height: 52 }, { compact: true, fontSize: 16 });
      });
      addText(slide, `storyboard-workflow-thread-${pageIndex + 1}`, "DETECT  →  CORRELATE  →  DIAGNOSE  →  ROUTE", { left: 170, top: 510, width: 940, height: 50 }, { fontSize: 25, bold: true, color: "#C74634" });
    } else if (roleKey === "capability-scenes" && scenes[0]) {
      addScene(scenes[0], 0, { left: 560, top: 145, width: 650, height: 375 }, {
        titlePosition: { left: 70, top: 176, width: 430, height: 46 }, detailPosition: { left: 70, top: 234, width: 430, height: 126 }, numbered: false, titleSize: 28, detailSize: 18,
      });
      if (services[0]) addService(services[0], 0, { left: 82, top: 430, width: 90, height: 90 }, { left: 190, top: 440, width: 300, height: 70 }, { fontSize: 19 });
    } else if (roleKey === "oci-service-map") {
      services.forEach((serviceIcon, serviceIndex) => {
        const left = 80 + serviceIndex * 300;
        addService(serviceIcon, serviceIndex, { left, top: 190, width: 100, height: 100 }, { left: left - 12, top: 302, width: 220, height: 66 }, { compact: true, fontSize: 18 });
        addText(slide, `storyboard-service-role-${pageIndex + 1}-${serviceIndex + 1}`, ["OWNED SIGNAL", "SEARCHABLE CONTEXT", "TRACE + TOPOLOGY", "APPROVED ROUTE"][serviceIndex] || "OWNED TELEMETRY", { left: left - 12, top: 390, width: 220, height: 38 }, { fontSize: 16, bold: true, color: "#C74634" });
      });
      addText(slide, `storyboard-service-context-${pageIndex + 1}`, "SIGNALS  →  SHARED INCIDENT CONTEXT  →  ACTION", { left: 230, top: 490, width: 820, height: 58 }, { fontSize: 27, bold: true, color: "#18202B" });
    } else if (roleKey === "at-a-glance") {
      scenes.forEach((scene, sceneIndex) => {
        const column = sceneIndex % 2; const row = Math.floor(sceneIndex / 2);
        const left = 56 + column * 625; const top = 142 + row * 230;
        addScene(scene, sceneIndex, { left, top, width: 290, height: 172 }, { titlePosition: { left: left + 305, top: top + 10, width: 250, height: 55 }, numbered: true, titleSize: 18 });
        if (services[sceneIndex]) addService(services[sceneIndex], sceneIndex, { left: left + 310, top: top + 82, width: 56, height: 56 }, { left: left + 374, top: top + 88, width: 200, height: 48 }, { compact: true, fontSize: 15 });
      });
    }
    addText(slide, `storyboard-evidence-${pageIndex + 1}`, `Evidence: ${handoff.evidence_footer || "source ledger"}`, { left: 60, top: height - 32, width: width - 120, height: 16 },
      { fontSize: 10, color: "#53606E" });
    slide.speakerNotes.textFrame.setText(`[Sources]\n${storyboardSources(handoff, page)}`);
    slide.speakerNotes.setVisible(true);
  }
}

async function addCanvasStoryMapSlide(presentation, handoff, after) {
  // The canvas-story-map keeps artwork and explanatory copy as independent
  // slide objects.  Do not reuse the legacy callout/card composition here.
  const slide = after === undefined ? presentation.slides.add() : presentation.slides.insert({ after });
  const width = slide.frame?.width || 1280;
  const height = slide.frame?.height || 720;
  // Canvas authoring uses a deliberate 3 x 2 scene rhythm.  The source
  // composition plan is still preserved in the handoff/other formats, but a
  // 1920px source canvas is too dense when directly scaled into a 16:9 slide:
  // native text becomes unreadable and the headline collides with the scene
  // labels.  These bounded slide coordinates keep every object independently
  // editable while giving the six illustrated scenes room to breathe.
  const accent = "#C74634"; // Oracle-red story thread, independent of theme accent.
  const headline = handoff.headline_zone || {};
  const canvasLayout = handoff.canvas_layout || {};
  const canvas = handoff.canvas || { width: 1920, height: 1080 };
  const scaleX = width / Number(canvas.width || 1920);
  const scaleY = height / Number(canvas.height || 1080);
  const sourcePosition = (bounds) => ({
    left: Number(bounds.x || 0) * scaleX,
    top: Number(bounds.y || 0) * scaleY,
    width: Number(bounds.width || 0) * scaleX,
    height: Number(bounds.height || 0) * scaleY,
  });
  const grid = [
    { left: 42, top: 145, width: 382, height: 238 },
    { left: 449, top: 145, width: 382, height: 238 },
    { left: 856, top: 145, width: 382, height: 238 },
    { left: 42, top: 422, width: 382, height: 238 },
    { left: 449, top: 422, width: 382, height: 238 },
    { left: 856, top: 422, width: 382, height: 238 },
  ];
  const cardPosition = (bounds) => bounds;
  slide.background.fill = "#FFF8EC";
  addText(slide, "canvas-title", headline.title || handoff.title || "Project at a glance", { left: 48, top: 24, width: 1184, height: 44 },
    { fontSize: 38, bold: true, color: "#18202B" });
  addText(slide, "canvas-takeaway", headline.takeaway || handoff.takeaway || "A source-grounded visual summary.", { left: 50, top: 79, width: 1168, height: 30 },
    { fontSize: 20, color: "#3C4655" });
  const thread = canvasLayout.thread?.points?.length
    ? canvasLayout.thread.points.map((point) => ({ x: Number(point.x || 0) * scaleX, y: Number(point.y || 0) * scaleY }))
    : grid.map((item) => ({ x: item.left + item.width / 2, y: item.top + item.height / 2 }));
  for (let index = 1; index < thread.length; index += 1) {
    const first = thread[index - 1]; const second = thread[index];
    slide.shapes.add({ geometry: "line", name: `canvas-thread-${index}`, position: safeLinePosition(first, second),
      line: { style: "solid", fill: accent, width: 4, endArrowType: index === thread.length - 1 ? "triangle" : undefined } });
  }
  const clusters = Array.isArray(handoff.clusters) ? handoff.clusters.slice(0, 8) : [];
  for (const [clusterIndex, cluster] of clusters.entries()) {
    const card = grid[clusterIndex];
    if (!card) break;
    const textBounds = cluster.text_bounds || {};
    slide.shapes.add({ geometry: "roundRect", name: `canvas-scene-card-${cluster.anchor_id}`, position: cardPosition(card),
      fill: "#FFFDF8", line: { style: "solid", fill: "#E3CFC7", width: 1.2 }, borderRadius: "rounded-xl" });
    const artwork = cluster.artwork || cluster.art || {};
    const artBounds = cluster.art_bounds || cluster.art_slot;
    if (typeof artwork.data_url === "string" && artBounds && artwork.data_url.startsWith("data:image/")) {
      const match = artwork.data_url.match(/^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/);
      if (!match) throw new Error(`invalid embedded canvas scene artwork for ${cluster.anchor_id}`);
      const imageBytes = Buffer.from(match[2], "base64");
      if (imageBytes.length > 1024 * 1024) throw new Error(`embedded canvas scene artwork is too large for ${cluster.anchor_id}`);
      const [pixelWidth, pixelHeight] = rasterDimensions(imageBytes, match[1]);
      if (pixelWidth <= 0 || pixelHeight <= 0 || pixelWidth > 8192 || pixelHeight > 8192 || pixelWidth * pixelHeight > 16_000_000) throw new Error(`embedded canvas scene artwork has an unsafe pixel budget for ${cluster.anchor_id}`);
      slide.images.add({
        name: `canvas-scene-${cluster.anchor_id}`,
        blob: imageBytes,
        contentType: match[1],
        alt: artwork.alt_text || cluster.art_alt_text || `Scene for ${cluster.title || cluster.anchor_id}`,
        fit: "contain",
        position: { left: card.left + 16, top: card.top + 14, width: 126, height: 88 },
      });
    }
    const textLeft = card.left + 154;
    // Canvas handoffs preserve text_bounds for cross-format parity even though
    // PPTX reflows the copy into a bounded card-local layout.
    const textWidth = textBounds.width ? Math.min(card.width - 172, Math.max(130, Number(textBounds.width) * scaleX)) : card.width - 172;
    const title = String(cluster.title || "").replace(/^\d+\.\s*/, "");
    slide.shapes.add({ geometry: "ellipse", name: `canvas-stage-${cluster.anchor_id}`, position: { left: card.left + 15, top: card.top + 115, width: 24, height: 24 },
      fill: accent, line: { style: "solid", fill: accent, width: 1 } });
    addText(slide, `canvas-index-${cluster.anchor_id}`, String(cluster.index || clusterIndex + 1), { left: card.left + 22, top: card.top + 119, width: 12, height: 12 },
      { fontSize: 10, bold: true, color: "#FFFFFF" });
    addText(slide, `canvas-title-${cluster.anchor_id}`, title, { left: textLeft, top: card.top + 15, width: textWidth, height: 50 },
      { fontSize: 20, bold: true, color: "#18202B" });
    addText(slide, `canvas-detail-${cluster.anchor_id}`, cluster.detail || "", { left: textLeft, top: card.top + 70, width: textWidth, height: 62 },
      { fontSize: 14, color: "#3C4655" });
    const services = Array.isArray(cluster.service_names) ? cluster.service_names.filter(Boolean).join(" • ") : String(cluster.service_label || "");
    if (services) addText(slide, `canvas-services-${cluster.anchor_id}`, services, { left: card.left + 16, top: card.top + 166, width: card.width - 32, height: 34 },
      { fontSize: 12, bold: true, color: accent });
    addText(slide, `canvas-evidence-${cluster.anchor_id}`, String(cluster.evidence_class || "code-backed").toUpperCase(), { left: card.left + 16, top: card.top + 204, width: card.width - 32, height: 17 },
      { fontSize: 11, bold: true, color: accent });
  }
  addText(slide, "canvas-evidence-footer", `Evidence: ${handoff.evidence_footer || "source ledger"}`, { left: 48, top: height - 28, width: width - 96, height: 18 }, { fontSize: 12, color: "#53606E" });
  const sources = (Array.isArray(handoff.source_register) ? handoff.source_register : [])
    .filter((source) => source && source.url)
    .map((source) => `- ${source.title || "Official Oracle documentation"}: ${source.url}`)
    .join("\n");
  slide.speakerNotes.textFrame.setText(`[Sources]\n${sources || handoff.evidence_footer || "No public source titles were supplied in the handoff."}`);
  slide.speakerNotes.setVisible(true);
  return slide;
}

async function addSummarySlide(presentation, handoff, after) {
  if (handoff.concept === "illo-storyboard-sequence-v1") {
    return addStoryboardSlides(presentation, handoff, after);
  }
  if (handoff.visual_style?.variant === "canvas-story-map") {
    return addCanvasStoryMapSlide(presentation, handoff, after);
  }
  const slide = after === undefined ? presentation.slides.add() : presentation.slides.insert({ after });
  const width = slide.frame?.width || 1280;
  const height = slide.frame?.height || 720;
  const profile = handoff.profile || {};
  const accent = color(profile.primary_accent, "#C74634");
  const secondary = color(profile.secondary_accent, "#E6B9AE");
  const headline = handoff.headline_zone || {};
  const title = headline.title || handoff.title || "Project at a glance";
  const takeaway = headline.takeaway || handoff.takeaway || "A source-grounded visual summary.";
  const clusters = Array.isArray(handoff.clusters) ? handoff.clusters.slice(0, 8) : [];
  slide.background.fill = "#FFFDF8";

  const lifecycleLayout = clusters.length === 6 ? [
    { left: 72, top: 224, width: 350, height: 166 },
    { left: 465, top: 248, width: 350, height: 166 },
    { left: 858, top: 218, width: 350, height: 178 },
    { left: 858, top: 447, width: 350, height: 166 },
    { left: 465, top: 469, width: 350, height: 154 },
    { left: 72, top: 443, width: 350, height: 174 },
  ] : null;
  // A single visible journey is the organising device, not a set of disconnected
  // card-to-card arrows. Six-stage lifecycle summaries use a spacious serpentine
  // route; other archetypes retain the deterministic handoff path.
  const points = lifecycleLayout
    ? lifecycleLayout.map((item) => ({ x: item.left + item.width / 2, y: item.top + item.height / 2 }))
    : (handoff.dominant_path?.points || []).map((point) => ({ x: point.x / 1920 * width, y: point.y / 1080 * height }));
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1]; const b = points[i];
    const ax = a.x; const ay = a.y;
    const bx = b.x; const by = b.y;
    slide.shapes.add({ geometry: "line", name: `journey-stroke-${i}`, position: safeLinePosition({ x: ax, y: ay }, { x: bx, y: by }),
      line: { style: "solid", fill: accent, width: 5, endArrowType: "triangle" } });
  }
  if (lifecycleLayout) {
    // The return stroke makes recovery-and-learning visibly feed the next
    // detection cycle without implying that OCI provides a monolithic incident
    // management product.
    const returnSegments = [
      [{ x: 72, y: 530 }, { x: 48, y: 530 }],
      [{ x: 48, y: 530 }, { x: 48, y: 308 }],
      [{ x: 48, y: 308 }, { x: 72, y: 308 }],
    ];
    for (const [index, [a, b]] of returnSegments.entries()) {
      slide.shapes.add({ geometry: "line", name: `journey-return-${index + 1}`, position: safeLinePosition(a, b),
        line: { style: "solid", fill: secondary, width: 3, dash: "dash", endArrowType: index === returnSegments.length - 1 ? "triangle" : undefined } });
    }
  }
  addText(slide, "summary-title", title, { left: 72, top: 34, width: width - 144, height: 68 },
    { fontSize: 34, bold: true, color: "#18202B" });
  addText(slide, "summary-takeaway", takeaway, { left: 76, top: 105, width: width - 152, height: 50 },
    { fontSize: 18, color: "#3C4655" });
  slide.shapes.add({ geometry: "roundRect", name: "journey-ribbon", position: { left: 72, top: 166, width: 330, height: 31 },
    fill: secondary, line: { style: "solid", fill: "none", width: 0 }, borderRadius: "rounded-xl" });
  addText(slide, "journey-label", (handoff.dominant_path_phrase || "guided path").toUpperCase(), { left: 87, top: 172, width: 300, height: 18 },
    { fontSize: 11, bold: true, color: accent });
  if (lifecycleLayout) {
    slide.shapes.add({ geometry: "roundRect", name: "proposal-evidence-badge", position: { left: width - 362, top: 166, width: 290, height: 31 },
      fill: "#FFF3EF", line: { style: "solid", fill: secondary, width: 1.4 }, borderRadius: "rounded-xl" });
    addText(slide, "proposal-evidence-label", "DESIGN PROPOSAL • NOT DEPLOYMENT EVIDENCE", { left: width - 348, top: 173, width: 262, height: 16 },
      { fontSize: 8, bold: true, color: accent });
  }
  // Small native doodles provide an editable, text-free visual rhythm.
  for (const [index, x] of [1010, 1040, 1070].entries()) {
    slide.shapes.add({ geometry: "ellipse", name: `headline-doodle-${index}`, position: { left: x, top: 90 + (index % 2) * 13, width: 9, height: 9 },
      fill: secondary, line: { style: "solid", fill: secondary, width: 1 } });
  }

  for (const [clusterIndex, cluster] of clusters.entries()) {
    const b = cluster.bounds || {};
    const fixed = lifecycleLayout?.[clusterIndex];
    const x = fixed?.left ?? (Number(b.x) || 0) / 1920 * width;
    const y = fixed?.top ?? (Number(b.y) || 0) / 1080 * height;
    const w = fixed?.width ?? (Number(b.width) || 360) / 1920 * width;
    const h = fixed?.height ?? (Number(b.height) || 170) / 1080 * height;
    const callout = String(cluster.callout_shape || "ribbon");
    const geometry = callout === "speech-tail" ? "ellipse" : callout === "bracket" ? "rightArrow" : callout === "torn-note" ? "parallelogram" : callout === "ribbon" ? "roundRect" : "ellipse";
    // Opaque paper fills keep the journey behind each scene instead of letting
    // the route cut through editable labels on ribbon/arrow callouts.
    const fill = callout === "speech-tail" ? "#FFF9F4" : callout === "torn-note" ? "#FFF5EC" : "#FFFDF8";
    const titleTop = lifecycleLayout ? y + 13 : (callout === "bracket" ? y + 32 : y + 10);
    const detailTop = lifecycleLayout ? y + 53 : (callout === "bracket" ? y + 73 : y + 53);
    const markerTop = lifecycleLayout ? y + 12 : (callout === "bracket" ? y + 30 : y + 10);
    slide.shapes.add({ geometry, name: `anchor-shell-${cluster.anchor_id}`, position: { left: x, top: y, width: w, height: h },
      fill, line: { style: "solid", fill: secondary, width: callout === "bracket" ? 2.4 : 1.6 },
      ...(geometry === "roundRect" ? { borderRadius: "rounded-xl" } : {}) });
    if (callout === "speech-tail") {
      slide.shapes.add({ geometry: "triangle", name: `anchor-tail-${cluster.anchor_id}`, position: { left: x + w * .17, top: y + h - 8, width: 25, height: 20 },
        fill: "#FFF9F4", line: { style: "solid", fill: secondary, width: 1.2 } });
    }
    // Supporting artwork may be produced by the active LLM, but the title,
    // detail, evidence, journey, and scene shell remain native editable slide
    // objects. Private prompts are never attached to the image relationship.
    const artwork = cluster.artwork || cluster.art || {};
    const artSlot = cluster.art_slot || {};
    let imageBytes;
    let contentType;
    if (typeof artwork.data_url === "string" && artwork.data_url.startsWith("data:image/")) {
      const match = artwork.data_url.match(/^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/);
      if (!match) throw new Error(`invalid embedded artwork for ${cluster.anchor_id}`);
      contentType = match[1];
      imageBytes = Buffer.from(match[2], "base64");
      if (imageBytes.length > 1024 * 1024) throw new Error(`embedded artwork is too large for ${cluster.anchor_id}`);
      const [pixelWidth, pixelHeight] = rasterDimensions(imageBytes, contentType);
      if (pixelWidth <= 0 || pixelHeight <= 0 || pixelWidth > 8192 || pixelHeight > 8192 || pixelWidth * pixelHeight > 16_000_000) {
        throw new Error(`embedded artwork has an unsafe pixel budget for ${cluster.anchor_id}`);
      }
    }
    if (imageBytes && ["x", "y", "width", "height"].every((key) => Number.isFinite(Number(artSlot[key])))) {
      const artPosition = lifecycleLayout
        ? { left: x + w - 122, top: y + 38, width: 108, height: h - 48 }
        : {
          left: Number(artSlot.x) / 1920 * width,
          top: Number(artSlot.y) / 1080 * height,
          width: Number(artSlot.width) / 1920 * width,
          height: Number(artSlot.height) / 1080 * height,
        };
      slide.images.add({
        blob: imageBytes,
        contentType,
        alt: artwork.alt_text || cluster.art_alt_text || "Supporting hand-drawn illustration",
        fit: "contain",
        position: artPosition,
      });
    }
    // A numeral marker and a tiny domain doodle make each scene feel authored,
    // while all explanatory text remains editable.
    slide.shapes.add({ geometry: "ellipse", name: `anchor-stage-${cluster.anchor_id}`, position: { left: x + 10, top: markerTop, width: 25, height: 25 },
      fill: accent, line: { style: "solid", fill: accent, width: 1 } });
    addText(slide, `anchor-index-${cluster.anchor_id}`, String(cluster.index || ""), { left: x + 17, top: markerTop + 5, width: 12, height: 14 },
      { fontSize: 10, bold: true, color: "#FFFDF8" });
    slide.shapes.add({ geometry: "ellipse", name: `anchor-doodle-${cluster.anchor_id}`, position: { left: x + w - 32, top: y + 15, width: 11, height: 11 },
      fill: secondary, line: { style: "solid", fill: accent, width: 1 } });
    const cleanTitle = String(cluster.title || "").replace(/^\d+\.\s*/, "");
    const textWidth = lifecycleLayout && imageBytes ? w - 154 : w - 52;
    addText(slide, `anchor-title-${cluster.anchor_id}`, cleanTitle, { left: x + 42, top: titleTop, width: textWidth, height: 34 },
      { fontSize: 18, bold: true, color: "#18202B" });
    addText(slide, `anchor-detail-${cluster.anchor_id}`, cluster.detail, { left: x + 18, top: detailTop, width: lifecycleLayout && imageBytes ? w - 150 : w - 36, height: lifecycleLayout ? 43 : h - (detailTop - y) - (callout === "bracket" ? 30 : 35) },
      { fontSize: lifecycleLayout ? 15 : (callout === "bracket" ? 10 : 12), color: "#3C4655" });
    const serviceNames = Array.isArray(cluster.service_names) ? cluster.service_names.map(String) : [String(cluster.service_label || "")];
    const proposedIntegrations = serviceNames.filter((service) => service.startsWith("Proposed integration:"));
    const services = serviceNames.filter((service) => !service.startsWith("Proposed integration:")).join("  •  ");
    if (services) {
      addText(slide, `anchor-services-${cluster.anchor_id}`, services, { left: x + 18, top: y + h - 55, width: lifecycleLayout && imageBytes ? w - 150 : w - 36, height: 36 },
        { fontSize: lifecycleLayout ? 10 : 11, bold: true, color: accent });
    }
    if (proposedIntegrations.length) {
      addText(slide, `anchor-integrations-${cluster.anchor_id}`, proposedIntegrations.join(" • "), { left: x + 18, top: y + h - 31, width: w - 72, height: 18 },
        { fontSize: 8, bold: true, color: "#6A727D" });
    }
    if (!lifecycleLayout) {
      addText(slide, `anchor-evidence-${cluster.anchor_id}`, String(cluster.evidence_class || "code-backed").toUpperCase(), { left: x + 18, top: y + h - 22, width: w - 36, height: 13 },
        { fontSize: 8, bold: true, color: "#6A727D" });
    }
  }
  // Draw stage nodes above the varied callouts: the route reads as one guided
  // journey even when it moves through quiet space around a scene.
  for (const [index, point] of (lifecycleLayout ? [] : points).entries()) {
    const x = point.x; const y = point.y;
    slide.shapes.add({ geometry: "ellipse", name: `journey-node-${index + 1}`, position: { left: x - 9, top: y - 9, width: 18, height: 18 },
      fill: "#FFFDF8", line: { style: "solid", fill: accent, width: 3 } });
    slide.shapes.add({ geometry: "ellipse", name: `journey-pulse-${index + 1}`, position: { left: x - 3, top: y - 3, width: 6, height: 6 },
      fill: accent, line: { style: "solid", fill: accent, width: 1 } });
  }
  const visibleEvidence = lifecycleLayout
    ? "Evidence: official Oracle documentation • full scene-to-source map in slide notes"
    : `Evidence: ${handoff.evidence_footer || "source ledger"}`;
  addText(slide, "evidence-footer", visibleEvidence, { left: 72, top: height - 42, width: width - 144, height: 20 },
    { fontSize: 10, color: "#53606E" });
  const sourceRegister = Array.isArray(handoff.source_register) ? handoff.source_register : [];
  const sourceByUrl = new Map(sourceRegister.map((item) => [String(item.url || ""), item]));
  const sceneMap = clusters.map((cluster) => {
    const sourceLines = (Array.isArray(cluster.source_ids) ? cluster.source_ids : [])
      .map((sourceId) => sourceByUrl.get(String(sourceId)))
      .filter(Boolean)
      .map((source) => `  - ${source.title}: ${source.url}`);
    return `${cluster.index}. ${String(cluster.title || "").replace(/^\d+\.\s*/, "")}\n${sourceLines.join("\n") || "  - Source mapping unavailable in this handoff"}`;
  }).join("\n\n");
  slide.speakerNotes.textFrame.setText(`[Sources]\n${sceneMap || handoff.evidence_footer || "No public source titles were supplied in the handoff."}\n\nEvidence class: ${handoff.evidence_class || "code-backed"}\nExternal HTTPS/ITSM is a proposed integration target, not an OCI service.`);
  slide.speakerNotes.setVisible(true);
  return slide;
}

function markOperation() {
  const marker = process.env.PRESENTATIONS_SKILL_DIR
    ? path.join(process.env.PRESENTATIONS_SKILL_DIR, "container_tools", "mark_artifact_operation_started.mjs")
    : null;
  if (!marker) throw new Error("PRESENTATIONS_SKILL_DIR is required to run mark_artifact_operation_started");
  // Required authoring marker: execute exactly once, immediately before mutation/export.
  execFileSync(process.env.RUNTIME_NODE, [marker, "--operation-kind", "create", "--expected-output-count", "1", "--output-format", "pptx"], { stdio: "inherit" });
}

function runQa(out) {
  const skillDir = process.env.PRESENTATIONS_SKILL_DIR;
  if (!skillDir) throw new Error("PRESENTATIONS_SKILL_DIR is required for render_slides.py and slides_test.py");
  const tools = path.join(skillDir, "container_tools");
  // These are delivery gates, not optional preview helpers: render every slide
  // and reject off-canvas content before the deck is returned.
  execFileSync(process.env.RUNTIME_PYTHON, [path.join(tools, "render_slides.py"), out], { stdio: "inherit" });
  execFileSync(process.env.RUNTIME_PYTHON, [path.join(tools, "slides_test.py"), out], { stdio: "inherit" });
}

function assertCompleteTemplateMap(map, sourceSlideCount) {
  if (!Number.isInteger(sourceSlideCount) || sourceSlideCount < 1) {
    throw new Error("template inspection did not report a valid source slide count");
  }
  const outputSlides = Array.isArray(map.outputSlides) ? map.outputSlides : [];
  const omittedSlides = Array.isArray(map.omittedSourceSlides) ? map.omittedSourceSlides : [];
  const covered = new Set();
  for (const entry of outputSlides) {
    if (!Number.isInteger(entry?.sourceSlide) || entry.sourceSlide < 1 || entry.sourceSlide > sourceSlideCount) {
      throw new Error(`template map sourceSlide must be within 1-${sourceSlideCount}`);
    }
    if (covered.has(entry.sourceSlide)) throw new Error("template map may not map one source slide more than once");
    covered.add(entry.sourceSlide);
  }
  for (const entry of omittedSlides) {
    if (!Number.isInteger(entry?.sourceSlide) || entry.sourceSlide < 1 || entry.sourceSlide > sourceSlideCount || typeof entry.reason !== "string" || !entry.reason.trim()) {
      throw new Error("template map omittedSourceSlides must contain each omitted sourceSlide and a non-empty reason");
    }
    if (covered.has(entry.sourceSlide)) throw new Error("template map may not both map and omit a source slide");
    covered.add(entry.sourceSlide);
  }
  if (covered.size !== sourceSlideCount) {
    throw new Error("template map must account for every inspected source slide through outputSlides or omittedSourceSlides");
  }
}

function resolveTemplateEditText(handoff, output, edit) {
  const binding = edit?.handoffBinding;
  if (!binding || typeof binding.audienceRole !== "string" || !binding.audienceRole.trim() || typeof binding.semanticBlock !== "string") {
    throw new Error("template edit target must declare an audienceRole and handoff semanticBlock");
  }
  if (output.audienceRole !== binding.audienceRole) throw new Error("template edit target audienceRole must match its output slide");
  const sourceIds = Array.isArray(binding.sourceIds) ? binding.sourceIds : [];
  const knownSources = new Set((Array.isArray(handoff.source_register) ? handoff.source_register : []).map((source) => String(source?.url || "")));
  if (!sourceIds.length || sourceIds.some((sourceId) => typeof sourceId !== "string" || !knownSources.has(sourceId))) {
    throw new Error("template edit target must map to accepted handoff source IDs");
  }
  const values = {
    title: handoff.headline_zone?.title || handoff.title,
    takeaway: handoff.headline_zone?.takeaway || handoff.takeaway,
    "evidence-footer": handoff.evidence_footer,
  };
  const value = values[binding.semanticBlock];
  if (typeof value !== "string" || !value.trim()) throw new Error("template edit target semanticBlock is unavailable in the accepted handoff");
  if (edit.replacementText !== value) throw new Error("template replacementText must exactly originate from its accepted handoff semanticBlock");
  return value;
}

async function prepareTemplateFollowingAdapter(args, handoff) {
  // Destination-template mode is deliberately distinct from icon-source use.
  // It never falls through to `slides.add()`: the Presentation skill's helper
  // workflow must inventory every source slide and construct a mapped starter
  // deck before inherited elements can be edited.  This builder currently has
  // no safe semantic mapping from arbitrary template placeholders to the
  // visual-summary handoff, so it prepares and validates that workflow, then
  // fails closed rather than emitting an unbranded blank-slide overlay.
  if (!args.template) return null;
  await Promise.all([
    requireBoundedRegular(args.template, "destination template", 64 * 1024 * 1024),
    requireBoundedRegular(args["template-map"], "template map", 2 * 1024 * 1024),
  ]);
  const skillDir = process.env.PRESENTATIONS_SKILL_DIR;
  if (!skillDir) throw new Error("PRESENTATIONS_SKILL_DIR is required for destination-template mode");
  const helpers = path.join(skillDir, "template_following_scripts");
  const inspect = path.join(helpers, "inspect_template_deck.mjs");
  const prepare = path.join(helpers, "prepare_template_starter_deck.mjs");
  const workspace = await fs.mkdtemp(path.join(tmpdir(), "oci-visual-summary-template-"));
  const starter = path.join(workspace, "template-starter.pptx");
  try {
    const map = JSON.parse(await fs.readFile(args["template-map"], "utf8"));
    if (!Array.isArray(map.outputSlides) || !map.outputSlides.length || map.outputSlides.some((item) => !Number.isInteger(item.sourceSlide) || item.reuseMode !== "duplicate-slide" || typeof item.audienceRole !== "string" || !item.audienceRole.trim() || !Array.isArray(item.editTargets) || !item.editTargets.length || item.editTargets.some((target) => !target || !(target.sourceElementId || target.shapeId) || typeof target.replacementText !== "string"))) {
      throw new Error("template map must contain complete duplicate-slide mappings, audience roles, and explicit inherited-element replacementText edit targets");
    }
    for (const output of map.outputSlides) for (const edit of output.editTargets) resolveTemplateEditText(handoff, output, edit);
    execFileSync(process.env.RUNTIME_NODE, [inspect, "--workspace", workspace, "--pptx", args.template], { stdio: "inherit" });
    const inspected = JSON.parse(await fs.readFile(path.join(workspace, "template-inspect", "template-manifest.json"), "utf8"));
    assertCompleteTemplateMap(map, Number(inspected.slideCount));
    execFileSync(process.env.RUNTIME_NODE, [prepare, "--workspace", workspace, "--pptx", args.template, "--map", args["template-map"], "--out", starter], { stdio: "inherit" });
    return { workspace, starter, map };
  } catch (error) {
    await fs.rm(workspace, { recursive: true, force: true });
    throw error;
  }
}

function applyInheritedTemplateEdits(presentation, map, handoff) {
  // Template mode changes only explicitly mapped inherited source elements.
  // Refusing to add blank summary slides over a template, it intentionally
  // never calls slides.add/insert or lays a fresh summary
  // canvas over a copied frame.
  for (const output of map.outputSlides) {
    for (const edit of output.editTargets) {
      const element = presentation.resolve(edit.sourceElementId || edit.shapeId);
      if (!element || !element.text) throw new Error("template edit target did not resolve to an inherited editable text element");
      element.text = resolveTemplateEditText(handoff, output, edit);
    }
  }
}

async function main() {
  requireRuntime();
  const { FileBlob, Presentation, PresentationFile } = await loadArtifactTool();
  const args = parseArgs(process.argv.slice(2));
  const handoff = await readBoundedJson(args.handoff);
  if (args.into) await requireBoundedRegular(args.into, "source presentation", 64 * 1024 * 1024);
  const templateMode = await prepareTemplateFollowingAdapter(args, handoff);
  await fs.mkdir(path.dirname(path.resolve(args.out)), { recursive: true });
  let presentation;
  let after;
  if (templateMode) {
    presentation = await PresentationFile.importPptx(await FileBlob.load(templateMode.starter));
    applyInheritedTemplateEdits(presentation, templateMode.map, handoff);
  } else if (args.into) {
    // Imported masters, layouts, and theme are retained by the artifact-tool import/export surface.
    presentation = await PresentationFile.importPptx(await FileBlob.load(args.into));
    after = args["after-slide"] ? Number(args["after-slide"]) - 1 : 0;
    if (!Number.isInteger(after) || after < 0 || after >= presentation.slides.items.length) throw new Error("--after-slide is outside the source deck");
  } else {
    presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  }
  markOperation();
  if (!templateMode) await addSummarySlide(presentation, handoff, after);
  const file = await PresentationFile.exportPptx(presentation);
  // Some file providers append ZIP members when a path already exists. Remove
  // only this declared output before saving so a rebuild cannot retain stale
  // slide objects from an earlier summary.
  await fs.rm(args.out, { force: true });
  await file.save(args.out);
  runQa(args.out);
  if (templateMode) await fs.rm(templateMode.workspace, { recursive: true, force: true });
}

main().catch((error) => { console.error(error?.stack || error); process.exitCode = 1; });
