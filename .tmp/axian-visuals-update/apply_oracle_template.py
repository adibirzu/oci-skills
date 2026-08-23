from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree


CONTENT = Path(".tmp/axian-visuals-update/user-arranged.docx")
BRAND = Path(".tmp/axian-oci-only/current.docx")
OUT = Path(".tmp/axian-visuals-update/AXIAN-OCI-Observability-Management-RFP-Answers-Latest.docx")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS = {"w": W, "wp": WP}


def patch_document_xml(blob: bytes) -> bytes:
    root = etree.fromstring(blob)
    replacements = {
        "No Operations/ involvement is required by this scoped OCI Observability response. Product teams own their platforms, access, remediation and external workflows.":
            "No Operations involvement is required by this scoped OCI Observability response. Product teams own their platforms, access, remediation and external workflows.",
        "Kubernetes is customer-managed, not customer-managed Kubernetes. Budget manual Helm/manifests deployment, cluster-specific compatibility and access validation, agent/gateway placement, upgrades and rollback for every approved cluster.":
            "Kubernetes is customer-managed rather than OKE. Budget manual Helm/manifests deployment, cluster-specific compatibility and access validation, agent/gateway placement, upgrades and rollback for every approved cluster.",
        "OCI Log Analytics Kubernetes Monitoring Solution is proposed for customer-managed Kubernetes. Deployment is manual through the documented Helm/manifests pattern and requires cluster-specific validation; no customer-managed Kubernetes service is assumed.":
            "OCI Log Analytics Kubernetes Monitoring Solution is proposed for customer-managed Kubernetes. Deployment is manual through the documented Helm/manifests pattern and requires cluster-specific validation; no OCI managed Kubernetes service is assumed.",
    }
    found = set()
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        texts = paragraph.xpath(".//w:t", namespaces=NS)
        current = "".join(t.text or "" for t in texts)
        if current in replacements and texts:
            texts[0].text = replacements[current]
            for node in texts[1:]:
                node.text = ""
            found.add(current)
    missing = set(replacements) - found
    if missing:
        raise RuntimeError(f"Expected correction slots not found: {missing}")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def patch_version(blob: bytes) -> bytes:
    return blob.replace(b"Version 1.3", b"Version 1.4")


def patch_header(blob: bytes) -> bytes:
    root = etree.fromstring(patch_version(blob))
    for text_node in root.xpath(".//*[local-name()='t']"):
        if text_node.text:
            text_node.text = text_node.text.replace(
                "Confidential - Oracle Restricted \\Employees Only",
                "Confidential - Oracle Restricted | Employees Only",
            )
    for anchor in root.xpath(".//wp:anchor|.//wp:inline", namespaces=NS):
        docpr = anchor.find("wp:docPr", namespaces=NS)
        if docpr is None or not docpr.get("name", "").startswith("Text Box"):
            continue
        align = anchor.find("wp:positionH/wp:align", namespaces=NS)
        if align is not None:
            align.text = "right"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


brand_parts = {
    "word/header1.xml", "word/header2.xml", "word/header3.xml", "word/header4.xml", "word/header5.xml",
    "word/_rels/header2.xml.rels", "word/_rels/header3.xml.rels", "word/_rels/header4.xml.rels", "word/_rels/header5.xml.rels",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml", "word/footer4.xml", "word/footer5.xml",
    "word/media/image1.png", "word/media/image2.png",
    "word/theme/theme1.xml",
}

with ZipFile(CONTENT, "r") as zin, ZipFile(BRAND, "r") as zbrand, ZipFile(OUT, "w", compression=ZIP_DEFLATED) as zout:
    content_names = set(zin.namelist())
    for info in zin.infolist():
        if info.filename in brand_parts:
            continue
        data = zin.read(info.filename)
        if info.filename == "word/document.xml":
            data = patch_document_xml(data)
        elif info.filename == "docProps/core.xml":
            data = data.replace(
                b"Unified Assurance; OCI Observability and Management; Log Analytics; Oracle Enterprise Manager; ServiceNow; AXIAN",
                b"OCI Observability and Management; Log Analytics; APM; Monitoring; Kubernetes; AXIAN",
            )
        zout.writestr(info, data)
    for name in sorted(brand_parts):
        if name not in zbrand.namelist():
            continue
        data = zbrand.read(name)
        if name.startswith("word/header") and name.endswith(".xml"):
            data = patch_header(data)
        elif name.startswith("word/footer"):
            data = patch_version(data)
        info = zbrand.getinfo(name)
        zout.writestr(info, data)

print(OUT)
