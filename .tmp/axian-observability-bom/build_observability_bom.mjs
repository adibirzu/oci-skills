import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = "/Users/abirzu/Library/CloudStorage/OneDrive-OracleCorporation/00-FY27-Customers/Axian/Oracle  Centralized AIOPS_Commercial.xlsx";
const outputDir = "/Users/abirzu/dev/oci-skills/.tmp/axian-observability-bom/outputs/019fb240-515b-7152-b9bb-472642eef1bc";
const outputPath = `${outputDir}/Oracle  OCI Observability_Commercial.xlsx`;

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const commercial = workbook.worksheets.getItem("Commercials");
const overview = workbook.worksheets.getItem("Bill of Material");
const priceInputs = workbook.worksheets.getOrAdd("OCI Price Inputs");

const darkBlue = "#002060";
const headerBlue = "#0B556B";
const inputBlue = "#DFECF9";
const categoryGray = "#F2F2F2";
const totalPeach = "#FCE4D6";
const borderGray = "#B7C9D6";
const currencyFormat = '_-[$$-409]* #,##0.00_ ;_-[$$-409]* \\-#,##0.00\\ ;_-[$$-409]* "-"??_ ;_-@_ ';

commercial.showGridLines = false;
commercial.freezePanes.freezeRows(12);

// Remove the legacy category merges while retaining the customer workbook's
// title, instruction area, colors, and five-year column structure.
for (const range of [
  "B13:B19", "C13:C19", "B20:B23", "C20:C23", "B24:B31", "C24:C31",
  "B32:B33", "C32:C33", "B34:B38", "C34:C38", "B39:B40", "C39:C40",
  "C42:D42",
]) {
  try { commercial.unmergeCells(range); } catch { /* already unmerged */ }
}

commercial.getRange("B13:N48").clear({ applyTo: "contents" });
commercial.getRange("B2").values = [["Axian - Centralized Monitoring & Observability | OCI Observability Commercial"]];
commercial.getRange("B3").values = [["OCI Observability Commercials"]];
commercial.getRange("B8:E8").values = [["This separate BOM contains OCI Observability services only. Enter monthly usage or storage quantities in the blue quantity cells. All values are USD public PAYG estimates; the final Oracle quote and applicable agreement govern.", null, null, null]];

const headers = [[
  "#", "Cost Category", "Cost Component\n(Part number)", "Description", "Pricing Unit",
  "No Licenses", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "5-Year Total", "Comments / Notes",
]];
commercial.getRange("B12:N12").values = headers;

commercial.mergeCells("B13:B24");
commercial.mergeCells("C13:C24");
commercial.getRange("B13").values = [[1]];
commercial.getRange("C13").values = [["OCI Observability Cloud Services"]];

const lineItems = [
  ["B90925", "OCI Monitoring — Ingestion", "Million Datapoints per month", 0],
  ["B90926", "OCI Monitoring — Retrieval", "Million Datapoints per month", 0],
  ["B92593", "OCI Logging — Storage", "Average GB Log Storage per month", 0],
  ["B95634", "OCI Log Analytics — Active Storage", "Active Storage Units per month", 0],
  ["B92809", "OCI Log Analytics — Archival Storage", "Archival Storage Units", 0],
  ["B95634", "OCI Application Performance Monitoring — active-storage commercial presumption", "300 GB active storage units per month", 1],
  ["No standalone SKU", "Log Analytics Kubernetes Monitoring Solution", "Customer-managed Kubernetes clusters", 0],
  ["No standalone SKU", "OCI Management Agent and Management Gateway", "Supported agent/gateway deployments", 0],
  ["No standalone SKU", "OCI Connector Hub", "Service connectors", 0],
  ["B90940", "OCI Notifications — HTTPS Delivery", "Million delivery operations per month", 0],
  ["B90941", "OCI Notifications — Email Delivery", "1,000 emails sent per month", 0],
  ["No standalone SKU", "LoganAI", "Enabled analyst capability", 0],
];
commercial.getRange("D13:G24").values = lineItems;

const apiBase = "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/";
const notes = [
  `First 500 million datapoints/month are free; USD 0.0025 per million above the threshold. ${apiBase}?partNumber=B90925&currencyCode=USD`,
  `First 1,000 million datapoints/month are free; USD 0.0015 per million above the threshold. ${apiBase}?partNumber=B90926&currencyCode=USD`,
  `First 10 GB-month are free; USD 0.05 per GB-month above the threshold. ${apiBase}?partNumber=B92593&currencyCode=USD`,
  `PAYG tiers: first 35 units USD 372/unit-month; units 36–103 USD 260.40; units above 103 USD 223.20. ${apiBase}?partNumber=B95634&currencyCode=USD`,
  `USD 0.02 per storage unit-hour. Use only for the approved archive tier and retention policy. ${apiBase}?partNumber=B92809&currencyCode=USD`,
  `Working assumption: 300 GB APM active storage = 1 × B95634 at USD 372/month. This is not a standalone APM SKU mapping returned by the pricing API; final Oracle quote must confirm.`,
  `No separate list-price line. Consumes Log Analytics active/archive storage and related telemetry services. Manual Helm/manifests deployment per customer-managed Kubernetes cluster.`,
  `No separate list-price line returned. Validate redundant gateways, proxy, certificates, resource footprint and lifecycle where supported hybrid collection requires it.`,
  `No standalone list-price line returned. Destination services remain chargeable; size by approved source/destination/residency routes.`,
  `First 1 million HTTPS deliveries/month are free; USD 0.60 per million above the threshold. ${apiBase}?partNumber=B90940&currencyCode=USD`,
  `First 1,000 emails/month are free; USD 0.02 per additional 1,000. ${apiBase}?partNumber=B90941&currencyCode=USD`,
  `No standalone Observability SKU returned. Analyst assistance only; any optional custom GenAI coordinator and AI/API SKUs are outside this BOM.`,
];
commercial.getRange("N13:N24").values = notes.map((value) => [value]);

const activeStorageFormula = (row) => `=('OCI Price Inputs'!$F$11*MIN($G${row},'OCI Price Inputs'!$E$11)+'OCI Price Inputs'!$F$12*MAX(MIN($G${row},'OCI Price Inputs'!$E$12)-'OCI Price Inputs'!$D$12,0)+'OCI Price Inputs'!$F$13*MAX($G${row}-'OCI Price Inputs'!$D$13,0))*'OCI Price Inputs'!$D$21`;
const annualFormulas = {
  13: `=MAX($G13-'OCI Price Inputs'!$E$5,0)*'OCI Price Inputs'!$F$6*'OCI Price Inputs'!$D$21`,
  14: `=MAX($G14-'OCI Price Inputs'!$E$7,0)*'OCI Price Inputs'!$F$8*'OCI Price Inputs'!$D$21`,
  15: `=MAX($G15-'OCI Price Inputs'!$E$9,0)*'OCI Price Inputs'!$F$10*'OCI Price Inputs'!$D$21`,
  16: activeStorageFormula(16),
  17: `=$G17*'OCI Price Inputs'!$F$14*'OCI Price Inputs'!$D$22`,
  18: activeStorageFormula(18),
  19: "=0",
  20: "=0",
  21: "=0",
  22: `=MAX($G22-'OCI Price Inputs'!$E$15,0)*'OCI Price Inputs'!$F$16*'OCI Price Inputs'!$D$21`,
  23: `=MAX($G23-'OCI Price Inputs'!$E$17,0)*'OCI Price Inputs'!$F$18*'OCI Price Inputs'!$D$21`,
  24: "=0",
};

for (let row = 13; row <= 24; row += 1) {
  commercial.getRange(`H${row}:L${row}`).formulas = [[
    annualFormulas[row], annualFormulas[row], annualFormulas[row], annualFormulas[row], annualFormulas[row],
  ]];
  commercial.getRange(`M${row}`).formulas = [[`=SUM(H${row}:L${row})`]];
}

commercial.mergeCells("C25:D25");
commercial.getRange("C25").values = [["TOTAL (USD)"]];
for (const col of ["H", "I", "J", "K", "L"]) {
  commercial.getRange(`${col}25`).formulas = [[`=SUM(${col}13:${col}24)`]];
}
commercial.getRange("M25").formulas = [["=SUM(M13:M24)"]];
commercial.getRange("N25").values = [["Working estimate using editable quantities and public USD PAYG rates retrieved 2026-08-04."]];

for (const range of ["B27:N27", "B28:N28", "B29:N29", "B30:N30", "B31:N31"]) commercial.mergeCells(range);
commercial.getRange("B27").values = [["Commercial assumptions"]];
commercial.getRange("B28").values = [["APM presumption: 300 GB active storage = 1 × B95634. Quantity defaults to 1, producing USD 4,464/year and USD 22,320 over five years at the first-tier public PAYG rate."]];
commercial.getRange("B29").values = [["All other quantities default to zero until measured. Update G13:G24 with monthly usage/storage drivers; the annual and five-year amounts recalculate automatically. No year-over-year growth, inflation, taxes, support or contracted discounts are applied."]];
commercial.getRange("B30").values = [["Scope: OCI Observability services only. All non-Observability products, platform/database tooling, custom AI-agent/API services, networking/security foundations and professional services are excluded."]];
commercial.getRange("B31").values = [[`Pricing source: ${apiBase} — official USD PAYG API values retrieved 2026-08-04. Final Oracle quote and applicable agreement govern.`]];

// Match the customer visual language: dark teal header, pale-blue editable and
// calculated cells, grey merged category, and peach total row.
commercial.getRange("B12:N12").format = {
  fill: headerBlue,
  font: { name: "Aptos Narrow", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D9E2F3" },
};
commercial.getRange("B13:C24").format = {
  fill: categoryGray,
  font: { name: "Aptos", size: 9, bold: true, color: "#1F1F1F" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: borderGray },
};
commercial.getRange("D13:N24").format = {
  fill: inputBlue,
  font: { name: "Aptos", size: 9, color: "#1F1F1F" },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: borderGray },
};
commercial.getRange("D13:E24").format.horizontalAlignment = "left";
commercial.getRange("F13:G24").format.horizontalAlignment = "center";
commercial.getRange("H13:M25").format.numberFormat = currencyFormat;
commercial.getRange("H13:M25").format.horizontalAlignment = "right";
commercial.getRange("G13:G24").format.numberFormat = "#,##0.00";
commercial.getRange("C25:N25").format = {
  fill: totalPeach,
  font: { name: "Aptos", size: 10, bold: true, color: "#1F1F1F" },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: borderGray },
};
commercial.getRange("H25:M25").format.numberFormat = currencyFormat;
commercial.getRange("B27:N31").format = {
  font: { name: "Aptos", size: 9, color: "#1F1F1F" },
  verticalAlignment: "center",
  wrapText: true,
};
commercial.getRange("B27:N27").format = {
  fill: darkBlue,
  font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
};

commercial.getRange("B12:N12").format.rowHeight = 38;
commercial.getRange("B13:N24").format.rowHeight = 48;
commercial.getRange("B25:N25").format.rowHeight = 28;
commercial.getRange("B27:N31").format.rowHeight = 34;
commercial.getRange("B28:N30").format.rowHeight = 44;
for (const [col, width] of Object.entries({ B: 5, C: 24, D: 20, E: 41, F: 25, G: 14, H: 14, I: 14, J: 14, K: 14, L: 14, M: 16, N: 64 })) {
  commercial.getRange(`${col}:${col}`).format.columnWidth = width;
}

// Replace the old product screenshot on the overview sheet with live scope and
// assumption text. The customer terms sheet is intentionally preserved.
overview.deleteAllDrawings();
overview.showGridLines = false;
for (const range of ["A3:M3", "A4:M4", "A5:M5", "A6:M6", "A7:M7", "A8:M8"]) {
  try { overview.mergeCells(range); } catch { /* already merged */ }
}
overview.getRange("A3").values = [["Pricing Overview — OCI Observability Only"]];
overview.getRange("A4").values = [["Customer-format pricing workbook and five-year TCO"]];
overview.getRange("A5").values = [["The Commercials sheet contains only OCI Observability services and documented supporting components. All service quantities other than the stated APM presumption remain zero until discovery confirms monthly usage, storage, clusters and notification volumes."]];
overview.getRange("A6").values = [["APM working presumption: 300 GB active storage = 1 × B95634 at USD 372/month, USD 4,464/year and USD 22,320 over five years. The final Oracle quote must confirm this commercial mapping."]];
overview.getRange("A7").values = [["The customer provides the Kubernetes platform and required access. Kubernetes Monitoring Solution deployment is manual through Helm/manifests and consumes the listed OCI Observability services."]];
overview.getRange("A8").values = [["Public PAYG values were refreshed from Oracle's official pricing API on 2026-08-04. Contracted pricing, taxes, support, implementation and non-Observability products are excluded."]];
overview.getRange("A3:M3").format = { font: { name: "Aptos", size: 18, bold: true, color: darkBlue } };
overview.getRange("A4:M4").format = { font: { name: "Aptos", size: 13, bold: true, color: "#1F1F1F" } };
overview.getRange("A5:M8").format = { font: { name: "Aptos", size: 11, color: "#1F1F1F" }, wrapText: true, verticalAlignment: "center" };
overview.getRange("A5:M8").format.rowHeight = 52;
overview.getRange("A3:M3").format.rowHeight = 28;
overview.getRange("A4:M4").format.rowHeight = 24;

// Auditable, visible source assumptions used by the Commercials formulas.
priceInputs.showGridLines = false;
priceInputs.getRange("A1:H1").merge();
priceInputs.getRange("A1").values = [["OCI Observability Public PAYG Price Inputs"]];
priceInputs.getRange("A2:H2").merge();
priceInputs.getRange("A2").values = [["Official Oracle pricing API values retrieved 2026-08-04. Final Oracle quote and applicable agreement govern."]];
priceInputs.getRange("A4:H4").values = [["Part Number", "Service", "Metric", "Tier Start", "Tier End", "USD PAYG Rate", "Billing Basis", "Official Source / Note"]];
const pricingRows = [
  ["B90925", "Monitoring — Ingestion", "Million Datapoints", 0, 500, 0, "Per month", `${apiBase}?partNumber=B90925&currencyCode=USD`],
  ["B90925", "Monitoring — Ingestion", "Million Datapoints", 500, 999999999, 0.0025, "Per month", `${apiBase}?partNumber=B90925&currencyCode=USD`],
  ["B90926", "Monitoring — Retrieval", "Million Datapoints", 0, 1000, 0, "Per month", `${apiBase}?partNumber=B90926&currencyCode=USD`],
  ["B90926", "Monitoring — Retrieval", "Million Datapoints", 1000, 999999999, 0.0015, "Per month", `${apiBase}?partNumber=B90926&currencyCode=USD`],
  ["B92593", "OCI Logging — Storage", "GB Log Storage", 0, 10, 0, "GB-month", `${apiBase}?partNumber=B92593&currencyCode=USD`],
  ["B92593", "OCI Logging — Storage", "GB Log Storage", 10, 999999999, 0.05, "GB-month", `${apiBase}?partNumber=B92593&currencyCode=USD`],
  ["B95634", "Log Analytics — Active Storage", "Active Storage Unit", 0, 35, 372, "Unit-month", `${apiBase}?partNumber=B95634&currencyCode=USD`],
  ["B95634", "Log Analytics — Active Storage", "Active Storage Unit", 35, 103, 260.4, "Unit-month", `${apiBase}?partNumber=B95634&currencyCode=USD`],
  ["B95634", "Log Analytics — Active Storage", "Active Storage Unit", 103, 999999999999999, 223.2, "Unit-month", `${apiBase}?partNumber=B95634&currencyCode=USD`],
  ["B92809", "Log Analytics — Archival Storage", "Archival Storage Unit", 0, null, 0.02, "Unit-hour", `${apiBase}?partNumber=B92809&currencyCode=USD`],
  ["B90940", "Notifications — HTTPS Delivery", "Million Delivery Operations", 0, 1, 0, "Per month", `${apiBase}?partNumber=B90940&currencyCode=USD`],
  ["B90940", "Notifications — HTTPS Delivery", "Million Delivery Operations", 1, 999999999, 0.6, "Per month", `${apiBase}?partNumber=B90940&currencyCode=USD`],
  ["B90941", "Notifications — Email Delivery", "1,000 Emails Sent", 0, 1, 0, "Per month", `${apiBase}?partNumber=B90941&currencyCode=USD`],
  ["B90941", "Notifications — Email Delivery", "1,000 Emails Sent", 1, 999999999, 0.02, "Per month", `${apiBase}?partNumber=B90941&currencyCode=USD`],
];
priceInputs.getRange("A5:H18").values = pricingRows;
for (const range of ["A20:C20", "A21:C21", "A22:C22", "A23:C23"]) priceInputs.mergeCells(range);
priceInputs.getRange("A20:A23").values = [
  ["APM active storage GB per assumed B95634 unit"],
  ["Months per year"],
  ["Hours per standard pricing year"],
  ["Pricing retrieval date"],
];
priceInputs.getRange("D20:D23").values = [[300], [12], [8760], ["2026-08-04"]];
priceInputs.getRange("A1:H1").format = { fill: darkBlue, font: { name: "Aptos", size: 16, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
priceInputs.getRange("A2:H2").format = { fill: inputBlue, font: { name: "Aptos", size: 10, italic: true, color: "#1F1F1F" }, wrapText: true };
priceInputs.getRange("A4:H4").format = { fill: headerBlue, font: { name: "Aptos Narrow", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: borderGray } };
priceInputs.getRange("A5:H18").format = { fill: inputBlue, font: { name: "Aptos", size: 9, color: "#1F1F1F" }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: borderGray } };
priceInputs.getRange("A20:D23").format = { fill: categoryGray, font: { name: "Aptos", size: 9, color: "#1F1F1F" }, borders: { preset: "all", style: "thin", color: borderGray } };
priceInputs.getRange("D20:D23").format.horizontalAlignment = "right";
priceInputs.getRange("F5:F18").format.numberFormat = "$#,##0.0000";
priceInputs.getRange("D5:E18").format.numberFormat = "#,##0.00";
priceInputs.getRange("A1:H1").format.rowHeight = 28;
priceInputs.getRange("A2:H2").format.rowHeight = 32;
priceInputs.getRange("A4:H4").format.rowHeight = 34;
priceInputs.getRange("A5:H18").format.rowHeight = 34;
for (const [col, width] of Object.entries({ A: 14, B: 30, C: 24, D: 13, E: 15, F: 15, G: 16, H: 68 })) priceInputs.getRange(`${col}:${col}`).format.columnWidth = width;
priceInputs.freezePanes.freezeRows(4);

await fs.mkdir(outputDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const keyRange = await workbook.inspect({
  kind: "table",
  sheetId: "Commercials",
  range: "B12:N31",
  include: "values,formulas",
  tableMaxRows: 30,
  tableMaxCols: 14,
  maxChars: 10000,
});
console.log(keyRange.ndjson);
console.log(outputPath);
