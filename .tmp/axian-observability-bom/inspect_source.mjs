import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = "/Users/abirzu/Library/CloudStorage/OneDrive-OracleCorporation/00-FY27-Customers/Axian/Oracle  Centralized AIOPS_Commercial.xlsx";
const outDir = "/Users/abirzu/dev/oci-skills/.tmp/axian-observability-bom/source-renders";
await fs.mkdir(outDir, { recursive: true });

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary = await workbook.inspect({
  kind: "workbook,sheet,table,definedName,drawing",
  maxChars: 12000,
  tableMaxRows: 12,
  tableMaxCols: 18,
  tableMaxCellChars: 100,
});
console.log(summary.ndjson);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  console.log(JSON.stringify({ sheet: sheet.name, used: used?.address ?? null }));
  if (used) {
    const region = await workbook.inspect({
      kind: "region",
      sheetId: sheet.name,
      range: used.address,
      maxChars: 14000,
      tableMaxRows: 80,
      tableMaxCols: 30,
      tableMaxCellChars: 140,
    });
    console.log(region.ndjson);
    const formulas = await workbook.inspect({
      kind: "formula",
      sheetId: sheet.name,
      range: used.address,
      maxChars: 8000,
      options: { maxResults: 200 },
    });
    console.log(formulas.ndjson);
  }
  // artifact-tool cannot rasterize the embedded EMF Oracle logo. Remove only
  // in-memory drawings for the visual pass; the source workbook is untouched.
  sheet.deleteAllDrawings();
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1.3, format: "png" });
  await fs.writeFile(path.join(outDir, `${sheet.name.replaceAll(/[^A-Za-z0-9_-]/g, "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}
