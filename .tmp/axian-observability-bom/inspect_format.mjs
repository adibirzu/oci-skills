import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = "/Users/abirzu/Library/CloudStorage/OneDrive-OracleCorporation/00-FY27-Customers/Axian/Oracle  Centralized AIOPS_Commercial.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
for (const [range, label] of [
  ["B2:N3", "title"],
  ["B8:N8", "instructions"],
  ["B12:N12", "table header"],
  ["B13:N19", "core rows"],
  ["B20:N20", "section row"],
  ["B42:N42", "total row"],
]) {
  const result = await workbook.inspect({
    kind: "computedStyle",
    sheetId: "Commercials",
    range,
    maxChars: 12000,
  });
  console.log(`STYLE ${label} ${range}`);
  console.log(result.ndjson);
}
