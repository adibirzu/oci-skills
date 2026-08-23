import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "/Users/abirzu/dev/oci-skills/.tmp/axian-observability-bom/outputs/019fb240-515b-7152-b9bb-472642eef1bc/Oracle  OCI Observability_Commercial.xlsx";
const renderDir = "/Users/abirzu/dev/oci-skills/.tmp/axian-observability-bom/final-renders";
await fs.mkdir(renderDir, { recursive: true });

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 });
console.log(sheets.ndjson);

const values = await workbook.inspect({
  kind: "table",
  sheetId: "Commercials",
  range: "D13:N25",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  maxChars: 10000,
});
console.log(values.ndjson);

const formulas = await workbook.inspect({
  kind: "formula",
  sheetId: "Commercials",
  range: "H13:M25",
  maxChars: 12000,
  options: { maxResults: 200 },
});
console.log(formulas.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const renderRanges = {
  "Commercials": "B2:N31",
  "Bill of Material": "A3:M8",
  "Terms & Conditions of Response": "B3:AZ44",
  "OCI Price Inputs": "A1:H23",
};
for (const [sheetName, range] of Object.entries(renderRanges)) {
  const sheet = workbook.worksheets.getItem(sheetName);
  // Remove unsupported EMF drawings only from this in-memory verification
  // copy. The exported workbook remains untouched.
  sheet.deleteAllDrawings();
  const png = await workbook.render({ sheetName, range, scale: 1.35, format: "png" });
  const fileName = `${sheetName.replaceAll(/[^A-Za-z0-9_-]/g, "_")}.png`;
  await fs.writeFile(path.join(renderDir, fileName), new Uint8Array(await png.arrayBuffer()));
  console.log(JSON.stringify({ sheetName, range, render: fileName }));
}
