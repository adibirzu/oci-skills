"""Bounded, private-only cataloging of labelled SVGs in OOXML icon packs."""
from __future__ import annotations
import argparse, ast, ctypes, errno, hashlib, io, json, os, secrets, shutil, stat, sys, unicodedata
import re
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from storyboard import StoryboardError, canonical_service_context

class IconPackError(ValueError):
    """Raised when a package crosses the private icon-ingestion boundary."""

MAX_MEMBER_COMPRESSED_BYTES=8*1024*1024; MAX_MEMBER_UNCOMPRESSED_BYTES=16*1024*1024
MAX_ARCHIVE_COMPRESSED_BYTES=64*1024*1024; MAX_ARCHIVE_UNCOMPRESSED_BYTES=128*1024*1024
MAX_SOURCE_BYTES=MAX_ARCHIVE_COMPRESSED_BYTES+2*1024*1024; MAX_MEDIA_BYTES=2*1024*1024; MAX_SVG_CANDIDATES=1000; MAX_MEMBERS=4096; MAX_SLIDES=256; MAX_RELATIONSHIPS=512; MAX_SHAPES_PER_SLIDE=512; MAX_LABEL_CHARS=512; MAX_XML_DEPTH=64; MAX_XML_TEXT=512*1024; SLIDE_HEIGHT_EMU=6858000
P_NS="http://schemas.openxmlformats.org/presentationml/2006/main"; A_NS="http://schemas.openxmlformats.org/drawingml/2006/main"; R_NS="http://schemas.openxmlformats.org/officeDocument/2006/relationships"; PKG_REL_NS="http://schemas.openxmlformats.org/package/2006/relationships"
IMAGE_REL="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
STANDARD_NON_IMAGE_RELS=frozenset({"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout","http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide","http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"})
_NOFOLLOW=getattr(os,"O_NOFOLLOW",0); _DIRECTORY=getattr(os,"O_DIRECTORY",0)
_RENAME_EXCL = 0x00000004
_PUBLIC_STENCIL_STYLE = re.compile(r"^shape=mxgraph\.oci\.[a-z][a-z0-9_]{0,79};$")
try:
    _renameatx_np = ctypes.CDLL(None, use_errno=True).renameatx_np
    _renameatx_np.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    _renameatx_np.restype = ctypes.c_int
except AttributeError:
    _renameatx_np = None

def _reject(message:str)->None: raise IconPackError(message)

def _snapshot_source(source:Path)->tuple[bytes,str]:
    """Open a regular source once, with no symlink following, into a bounded snapshot."""
    try: fd=os.open(os.fspath(source),os.O_RDONLY|_NOFOLLOW)
    except OSError as exc: raise IconPackError("icon pack source is unavailable or a symlink") from exc
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_SOURCE_BYTES: _reject("icon pack source is not an allowed bounded regular file")
        chunks=[]; remaining=MAX_SOURCE_BYTES+1
        while remaining:
            block=os.read(fd,min(1024*1024,remaining))
            if not block: break
            chunks.append(block); remaining-=len(block)
        data=b"".join(chunks)
        if len(data)>MAX_SOURCE_BYTES or len(data)!=info.st_size: _reject("icon pack source changed while being snapshotted")
        return data,hashlib.sha256(data).hexdigest()
    except OSError as exc: raise IconPackError("could not snapshot icon pack") from exc
    finally: os.close(fd)

def _safe_name(name:str)->PurePosixPath:
    path=PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name: _reject("archive contains an unsafe member name")
    return path

def _slide_number(name:str)->int|None:
    path=PurePosixPath(name)
    if path.parent!=PurePosixPath("ppt/slides") or path.suffix!=".xml": return None
    stem=path.stem
    if not stem.startswith("slide") or not stem[5:].isdigit() or stem[5:]!=str(int(stem[5:])): _reject("slide name is not canonical")
    return int(stem[5:])

def _rel_number(name:str)->int|None:
    path=PurePosixPath(name)
    if path.parent!=PurePosixPath("ppt/slides/_rels") or not path.name.endswith(".xml.rels"): return None
    number=path.name[5:-9]
    if not path.name.startswith("slide") or not number.isdigit() or number!=str(int(number)): _reject("slide relationship name is not canonical")
    return int(number)

def _is_svg(name:str)->bool:
    path=PurePosixPath(name); return path.parent==PurePosixPath("ppt/media") and path.suffix.lower()==".svg"

def _xml(data:bytes,kind:str)->ET.Element:
    # UTF-16/32 declaration bytes contain NULs; normalize those before the
    # lexical DTD/entity rejection so parser safety is encoding-independent.
    compact=data.replace(b"\x00",b"").upper()
    if b"<!DOCTYPE" in compact or b"<!ENTITY" in compact: _reject(f"unsafe {kind} XML")
    if len(data)>MAX_XML_TEXT: _reject(f"{kind} XML exceeds text limit")
    try: root=ET.fromstring(data)
    except (ET.ParseError,ValueError) as exc: raise IconPackError(f"invalid {kind} XML") from exc
    pending=[(root,1)]; text=0
    while pending:
        node,depth=pending.pop()
        if depth>MAX_XML_DEPTH: _reject(f"{kind} XML exceeds depth limit")
        text+=len(node.text or "")+len(node.tail or "")
        if text>MAX_XML_TEXT: _reject(f"{kind} XML exceeds text limit")
        pending.extend((child,depth+1) for child in list(node))
    return root

def _image_target(target:str)->str:
    path=PurePosixPath(target)
    if path.is_absolute() or "\\" in target or path.parts[:2]!=("..","media") or len(path.parts)!=3: _reject("image relationship target is outside the SVG media allowlist")
    result=str(PurePosixPath("ppt/media")/path.name)
    if not _is_svg(result): _reject("image relationship target is not SVG")
    return result

def _load_snapshot(data:bytes)->tuple[dict[str,bytes],dict[int,dict[str,str]],list[int],int]:
    """Validate ZIP/XML bounds and return only allowed immutable in-memory parts."""
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            infos=archive.infolist(); names=set(); compressed=uncompressed=svg_count=0; parts={}; slides=[]; rel_parts={}
            if len(infos)>MAX_MEMBERS: _reject("archive contains too many members")
            for info in infos:
                _safe_name(info.filename)
                if info.filename in names: _reject("archive contains duplicate members")
                names.add(info.filename)
                if info.flag_bits&1: _reject("encrypted icon packs are not supported")
                if info.compress_size>MAX_MEMBER_COMPRESSED_BYTES or info.file_size>MAX_MEMBER_UNCOMPRESSED_BYTES: _reject("archive member exceeds size limit")
                compressed+=info.compress_size; uncompressed+=info.file_size
                if compressed>MAX_ARCHIVE_COMPRESSED_BYTES or uncompressed>MAX_ARCHIVE_UNCOMPRESSED_BYTES: _reject("archive exceeds total size limit")
                slide=_slide_number(info.filename); rel=_rel_number(info.filename)
                if slide is not None:
                    if slide in slides: _reject("duplicate logical slide number")
                    if len(slides)>=MAX_SLIDES: _reject("archive contains too many slides")
                    slides.append(slide); parts[info.filename]=archive.read(info)
                elif rel is not None:
                    if rel in rel_parts: _reject("duplicate logical slide relationship")
                    rel_parts[rel]=info.filename; parts[info.filename]=archive.read(info)
                elif _is_svg(info.filename):
                    if info.file_size>MAX_MEDIA_BYTES: _reject("SVG media exceeds private cache size limit")
                    svg_count+=1
                    if svg_count>MAX_SVG_CANDIDATES: _reject("archive contains too many SVG candidates")
                    parts[info.filename]=archive.read(info)
                elif info.filename.endswith(".rels"): parts[info.filename]=archive.read(info)
            for name,content in parts.items():
                if name.endswith(".rels"):
                    for rel in _xml(content,"relationship").findall(f"{{{PKG_REL_NS}}}Relationship"):
                        if rel.get("TargetMode","").lower()=="external": _reject("external relationship")
            mapped={}
            for number,name in rel_parts.items():
                relationships={}
                for relationship_count, rel in enumerate(_xml(parts[name],"relationship").findall(f"{{{PKG_REL_NS}}}Relationship"), start=1):
                    if relationship_count>MAX_RELATIONSHIPS: _reject("slide contains too many relationships")
                    rel_id,rel_type,target=rel.get("Id"),rel.get("Type"),rel.get("Target")
                    if not rel_id or not rel_type or not target: _reject("malformed slide relationship")
                    if rel_type==IMAGE_REL:
                        media=_image_target(target)
                        if media not in parts: _reject("image relationship target is absent")
                        if rel_id in relationships: _reject("duplicate relationship identifier")
                        relationships[rel_id]=media
                    elif rel_type not in STANDARD_NON_IMAGE_RELS: _reject("unsupported slide relationship type")
                mapped[number]=relationships
            return parts,mapped,sorted(slides),svg_count
    except (BadZipFile,OSError,RuntimeError) as exc: raise IconPackError("invalid or unreadable icon pack archive") from exc

def _xfrm(node:ET.Element)->tuple[int,int,int,int]|None:
    transform=node.find(f".//{{{A_NS}}}xfrm")
    if transform is None: return None
    off,extent=transform.find(f"{{{A_NS}}}off"),transform.find(f"{{{A_NS}}}ext")
    if off is None or extent is None: return None
    try: values=(int(off.get("x","-1")),int(off.get("y","-1")),int(extent.get("cx","-1")),int(extent.get("cy","-1")))
    except ValueError: return None
    return values if values[0]>=0 and values[1]>=0 and values[2]>0 and values[3]>0 else None

def _pairs(parts:dict[str,bytes],relationships:dict[int,dict[str,str]],slides:list[int])->tuple[list[dict[str,Any]],list[str]]:
    found=[]; warnings=[]
    for number in slides:
        root=_xml(parts[f"ppt/slides/slide{number}.xml"],"slide"); pictures=[]; labels=[]
        raw_pictures=root.findall(f".//{{{P_NS}}}pic"); raw_shapes=root.findall(f".//{{{P_NS}}}sp")
        if len(raw_pictures)+len(raw_shapes)>MAX_SHAPES_PER_SLIDE: _reject("slide contains too many shapes")
        for picture in raw_pictures:
            bounds=_xfrm(picture); blip=picture.find(f".//{{{A_NS}}}blip"); relation=blip.get(f"{{{R_NS}}}embed") if blip is not None else None
            if bounds is not None and relation in relationships.get(number,{}): pictures.append((bounds,relationships[number][relation]))
        for shape in raw_shapes:
            bounds=_xfrm(shape); label="".join(text.text or "" for text in shape.findall(f".//{{{A_NS}}}t")).strip()
            if len(label)>MAX_LABEL_CHARS: _reject("slide label exceeds text limit")
            if bounds is not None and label: labels.append((bounds,label))
        edges=[]; label_degree=[0]*len(labels)
        for picture,_ in pictures:
            px,py,pw,ph=picture
            candidates=[index for index,(bounds,_label) in enumerate(labels) if abs((px+pw/2)-(bounds[0]+bounds[2]/2))<=min(pw,bounds[2]) and py+ph<=bounds[1]<=py+ph+SLIDE_HEIGHT_EMU*.2]
            edges.append(candidates)
            for index in candidates: label_degree[index]+=1
        if any(len(edge)>1 for edge in edges) or any(degree>1 for degree in label_degree): warnings.append(f"slide {number}: ambiguous icon cell omitted")
        for pic_index,edge in enumerate(edges):
            if len(edge)==1 and label_degree[edge[0]]==1:
                bounds,media=pictures[pic_index]; found.append({"label":labels[edge[0]][1],"slide_number":number,"media_name":media,"bounds":list(bounds)})
    return found,warnings

def _open_private_root(path:Path)->int:
    candidate=path if path.is_absolute() else Path.cwd()/path
    try:
        fd=os.open("/",os.O_RDONLY|_DIRECTORY)
        for part in candidate.parts[1:]:
            if part in ("",".",".."): _reject("unsafe private output root")
            try: os.mkdir(part,0o700,dir_fd=fd)
            except FileExistsError: pass
            next_fd=os.open(part,os.O_RDONLY|_DIRECTORY|_NOFOLLOW,dir_fd=fd); os.close(fd); fd=next_fd
        return fd
    except OSError as exc: raise IconPackError("private output root is unavailable or contains a symlink") from exc

def _mkdir_open(parent_fd:int,name:str)->int:
    try: os.mkdir(name,0o700,dir_fd=parent_fd)
    except FileExistsError: pass
    try: return os.open(name,os.O_RDONLY|_DIRECTORY|_NOFOLLOW,dir_fd=parent_fd)
    except OSError as exc: raise IconPackError("private cache contains an unsafe destination") from exc

def _write_new(directory_fd:int,name:str,data:bytes)->None:
    try:
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|_NOFOLLOW,0o600,dir_fd=directory_fd)
        with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
    except OSError as exc: raise IconPackError("could not create private cache file") from exc

def _publish_no_replace(cache_fd:int,temp_name:str,destination:str)->None:
    """Darwin renameatx_np(RENAME_EXCL): atomically fail if destination exists."""
    if _renameatx_np is None: _reject("atomic no-replace publication is unavailable")
    result=_renameatx_np(cache_fd,os.fsencode(temp_name),cache_fd,os.fsencode(destination),_RENAME_EXCL)
    if result == 0: return
    error=ctypes.get_errno()
    if error in (errno.EEXIST,errno.ENOTEMPTY): _reject("private cache entry already exists")
    raise IconPackError("could not atomically publish private icon cache")

def _materialize(source:Path,private_root:Path)->tuple[dict[str,Any],Path]:
    snapshot,source_digest=_snapshot_source(source); parts,relationships,slides,_svg_count=_load_snapshot(snapshot); pairs,warnings=_pairs(parts,relationships,slides)
    root_fd=_open_private_root(private_root); cache_fd=temp_fd=-1; temp_name=f".pending-{secrets.token_hex(16)}"
    try:
        private_fd=_mkdir_open(root_fd,".visual-summary-private")
        try: cache_fd=_mkdir_open(private_fd,"icon-cache")
        finally: os.close(private_fd)
        os.mkdir(temp_name,0o700,dir_fd=cache_fd); temp_fd=os.open(temp_name,os.O_RDONLY|_DIRECTORY|_NOFOLLOW,dir_fd=cache_fd)
        icons=[]
        for index,pair in enumerate(pairs, start=1):
            media=parts[pair["media_name"]]; digest=hashlib.sha256(media).hexdigest(); filename=f"{digest}.svg"; _write_new(temp_fd,filename,media)
            icons.append({"asset_id":f"icon-{index}","label":pair["label"],"bounds":pair["bounds"],"slide_number":pair["slide_number"],"media_digest":digest,"media_path":f"{source_digest}/{filename}"})
        catalog={"schema_version":1,"classification":"internal-only","source_digest":source_digest,"icons":icons,"warnings":sorted(set(warnings))}
        _write_new(temp_fd,"catalog.json",json.dumps(catalog,sort_keys=True,separators=(",",":")).encode())
        os.close(temp_fd); temp_fd=-1; _publish_no_replace(cache_fd,temp_name,source_digest)
        return catalog,Path(private_root)/".visual-summary-private"/"icon-cache"/source_digest/"catalog.json"
    except (OSError,ValueError) as exc:
        if isinstance(exc,IconPackError): raise
        raise IconPackError("could not publish private icon cache") from exc
    finally:
        # ``_publish_no_replace`` runs after the pending descriptor is closed.
        # Re-open only this invocation's exact private name descriptor-relatively
        # so a failed rename cannot strand a ``.pending-*`` cache directory.
        if cache_fd>=0:
            pending_fd=temp_fd
            try:
                if pending_fd<0:
                    pending_fd=os.open(temp_name,os.O_RDONLY|_DIRECTORY|_NOFOLLOW,dir_fd=cache_fd)
                for entry in os.listdir(pending_fd): os.unlink(entry,dir_fd=pending_fd)
                os.close(pending_fd)
                if pending_fd==temp_fd: temp_fd=-1
                os.rmdir(temp_name,dir_fd=cache_fd)
            except FileNotFoundError: pass
            except OSError: pass
        if temp_fd>=0: os.close(temp_fd)
        if cache_fd>=0: os.close(cache_fd)
        os.close(root_fd)

def catalog_icon_pack(source:Path,private_root:Path)->dict[str,Any]: return _materialize(Path(source),Path(private_root))[0]
def write_private_icon_catalog(source:Path,private_root:Path)->Path: return _materialize(Path(source),Path(private_root))[1]


def _normalized_label(value: str) -> str:
    """Normalize typography only; matching remains strict equality."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def _catalog_icon_matches(catalog: dict[str, Any], label: str) -> list[tuple[int, dict[str, Any]]]:
    icons = catalog.get("icons")
    if not isinstance(icons, list):
        raise IconPackError("icon catalog must contain an icons list")
    normalized_label = _normalized_label(label)
    matches = []
    for index, icon in enumerate(icons, start=1):
        if isinstance(icon, dict) and isinstance(icon.get("label"), str) and _normalized_label(icon["label"]) == normalized_label:
            matches.append((index, icon))
    return matches


def _conceptual_overrides(overrides: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    if overrides is None:
        return {}
    if not isinstance(overrides, dict):
        raise IconPackError("icon overrides must be an object")
    result: dict[str, dict[str, str]] = {}
    for keyed_id, override in overrides.items():
        if not isinstance(keyed_id, str) or not keyed_id.strip() or not isinstance(override, dict):
            raise IconPackError("icon overrides must use canonical service ID keys")
        required = {"canonical_service_id", "label", "mapping_type", "rationale"}
        if set(override) != required:
            raise IconPackError("conceptual override must contain canonical_service_id, label, mapping_type, and rationale")
        canonical_service_id = override.get("canonical_service_id")
        label = override.get("label")
        mapping_type = override.get("mapping_type")
        rationale = override.get("rationale")
        if canonical_service_id != keyed_id:
            raise IconPackError("conceptual override canonical_service_id must match its key")
        if not all(isinstance(value, str) and value.strip() for value in (canonical_service_id, label, rationale)):
            raise IconPackError("conceptual override canonical_service_id, label, and rationale must be non-empty")
        if mapping_type != "conceptual-redwood":
            raise IconPackError("only explicit conceptual-redwood overrides are supported")
        result[keyed_id] = {"label": label, "mapping_type": mapping_type}
    return result


def _portable_record(service: dict[str, str], mapping_type: str, icon: tuple[int, dict[str, Any]] | None) -> dict[str, Any]:
    if icon is None:
        bounds = private_catalog_asset_id = None
    else:
        index, catalog_icon = icon
        candidate_bounds = catalog_icon.get("bounds")
        bounds = list(candidate_bounds) if isinstance(candidate_bounds, (list, tuple)) else None
        asset_id = catalog_icon.get("asset_id")
        private_catalog_asset_id = asset_id if isinstance(asset_id, str) and asset_id.strip() else f"icon-{index}"
    return {
        "unit_id": service["unit_id"],
        "canonical_service_id": service["canonical_service_id"],
        "display_name": service["display_name"],
        "mapping_type": mapping_type,
        "alt_text": service["alt_text"],
        "bounds": bounds,
        "private_catalog_asset_id": private_catalog_asset_id,
    }


def validate_public_stencil_style(style: Any) -> str:
    """Allow only one inert, known-shape OCI mxGraph style declaration."""
    if not isinstance(style, str) or not _PUBLIC_STENCIL_STYLE.fullmatch(style):
        _reject("official public stencil style is invalid")
    return style


def official_public_stencil_catalog() -> dict[str, Any]:
    """Expose the repository's public OCI Draw.io registry without AXM access.

    This is intentionally a registry of service keys and provenance, rather
    than a copy of icon artwork.  It lets public visual summaries select the
    supported OCI stencil before using a neutral renderer motif.  Restricted
    AXM/POTX assets remain outside this path.
    """
    registry_path = Path(__file__).resolve().parents[2] / "oci-diagramming" / "scripts" / "oci_diagram.py"
    if not registry_path.is_file() or registry_path.is_symlink():
        raise IconPackError("official public OCI stencil registry is unavailable")
    try:
        tree = ast.parse(registry_path.read_text(encoding="utf-8"), filename=str(registry_path))
        assignment = next((node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OCI_STENCIL_STYLES" for target in node.targets)), None)
        styles = ast.literal_eval(assignment.value) if assignment is not None else None
    except (OSError, SyntaxError, ValueError) as exc:
        raise IconPackError("official public OCI stencil registry is unreadable") from exc
    if not isinstance(styles, dict) or not all(
        isinstance(key, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", key)
        and validate_public_stencil_style(value)
        for key, value in styles.items()
    ):
        raise IconPackError("official public OCI stencil registry is invalid")
    return {
        "classification": "public",
        "rights": "oracle-public",
        "provenance": "official-public-oci-stencil-registry",
        "registry_path": "skills/oci-diagramming/scripts/oci_diagram.py",
        "stencils": dict(styles),
        "icons": [],
    }


_PUBLIC_STENCIL_BY_CANONICAL_SERVICE = {
    "oci.monitoring": "monitoring", "oci.logging": "logging", "oci.apm": "apm",
    "oci.log-analytics": "log-analytics", "oci.notifications": "notifications",
    "oci.events": "events", "oci.service-connector-hub": "service-connector-hub",
    "oci.streaming": "streaming", "oci.object-storage": "object-storage", "oci.oke": "oke",
    "oci.compute": "compute", "oci.load-balancer": "load-balancer", "oci.network-firewall": "network-firewall",
    "oci.bastion": "bastion", "oci.vault": "vault", "oci.cloud-guard": "cloud-guard",
    "oci.identity": "identity", "oci.generative-ai": "generative-ai", "oci.database": "database",
    "oci.autonomous-database": "database",
    "oci.redis": "redis",
}


def resolve_service_icons(storyboard: dict[str, Any], catalog: dict[str, Any], overrides: dict[str, Any] | None, *, output_classification: str) -> list[dict[str, Any]]:
    """Resolve only grounded service context into renderer-safe portable records."""
    if output_classification not in {"internal", "public"}:
        raise IconPackError("output classification must be internal or public")
    if not isinstance(catalog, dict):
        raise IconPackError("icon catalog must be an object")
    if output_classification == "public":
        if catalog.get("classification") != "public":
            raise IconPackError("public output cannot use an internal-only or unclassified icon catalog")
        if catalog.get("icons") and catalog.get("rights") not in {"oracle-public", "public-domain", "user-supplied-public"}:
            raise IconPackError("public icon catalog requires recognized public rights")
    try:
        services = canonical_service_context(storyboard)
    except StoryboardError as exc:
        raise IconPackError(str(exc)) from exc
    conceptual = _conceptual_overrides(overrides)
    records = []
    for service in services:
        override = conceptual.get(service["canonical_service_id"])
        label = override["label"] if override else service["display_name"]
        matches = _catalog_icon_matches(catalog, label)
        icon = matches[0] if len(matches) == 1 else None
        mapping_type = override["mapping_type"] if override and icon is not None else "exact-service" if icon is not None else "none"
        record = _portable_record(service, mapping_type, icon)
        if icon is None and catalog.get("provenance") == "official-public-oci-stencil-registry":
            stencil_key = _PUBLIC_STENCIL_BY_CANONICAL_SERVICE.get(service["canonical_service_id"])
            if stencil_key and stencil_key in catalog.get("stencils", {}):
                record["mapping_type"] = "official-public-stencil"
                record["public_stencil_key"] = stencil_key
                record["provenance"] = "official-public-oci-stencil-registry"
        records.append(record)
    return records

def _inspect(source:Path)->dict[str,Any]:
    snapshot,_digest=_snapshot_source(source); _parts,_relationships,slides,svg_count=_load_snapshot(snapshot)
    return {"classification":"internal-only","slides":len(slides),"svg_media":svg_count}
def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description="Inspect a private OOXML icon pack safely."); commands=parser.add_subparsers(dest="command",required=True); inspect=commands.add_parser("inspect"); inspect.add_argument("--source",required=True,type=Path); inspect.add_argument("--counts-only",action="store_true"); args=parser.parse_args(argv)
    try:
        if args.command=="inspect" and args.counts_only: print(json.dumps(_inspect(args.source),sort_keys=True)); return 0
        parser.error("inspect requires --counts-only")
    except IconPackError as exc: print(f"icon pack rejected: {exc}",file=sys.stderr); return 2
    return 2
if __name__=="__main__": raise SystemExit(main())
