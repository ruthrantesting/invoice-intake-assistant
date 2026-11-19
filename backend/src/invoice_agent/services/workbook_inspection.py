import io
import zipfile

from invoice_agent.config import settings
from invoice_agent.domain.workbook_safety import UnsupportedWorkbookError
from invoice_agent.services.workbook_service import inspect_workbook

MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_EXPANSION_RATIO = 100
ALLOWED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "docProps/app.xml",
    "docProps/core.xml",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
}


def inspect_workbook_package(data: bytes) -> dict[str, object]:
    if len(data) > min(MAX_PACKAGE_BYTES, settings.max_workbook_bytes):
        raise UnsupportedWorkbookError("The workbook exceeds the configured package size limit.")
    if not settings.workbook_profile_approved:
        raise UnsupportedWorkbookError("The workbook compatibility profile has not been approved.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 500:
                raise UnsupportedWorkbookError("The workbook contains too many package parts.")
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise UnsupportedWorkbookError("The workbook package contains duplicate paths.")
            for item in infos:
                if item.flag_bits & 0x1:
                    raise UnsupportedWorkbookError("Encrypted workbook packages are not supported.")
                if item.file_size > MAX_MEMBER_BYTES:
                    raise UnsupportedWorkbookError(
                        "A workbook package part exceeds the size limit."
                    )
                if item.compress_size and item.file_size / item.compress_size > MAX_EXPANSION_RATIO:
                    raise UnsupportedWorkbookError(
                        "The workbook package has an unsafe compression ratio."
                    )
                if item.filename.startswith("/") or ".." in item.filename.split("/"):
                    raise UnsupportedWorkbookError("The workbook package contains an unsafe path.")
                if item.filename.startswith("xl/externalLinks/") or item.filename.endswith(
                    ".vbaProject.bin"
                ):
                    raise UnsupportedWorkbookError(
                        "Macros and external workbook links are not supported."
                    )
                if (
                    item.filename not in ALLOWED_PARTS
                    and not (
                        item.filename.startswith("xl/worksheets/")
                        and item.filename.endswith(".xml")
                    )
                    and not (
                        item.filename.startswith("xl/theme/") and item.filename.endswith(".xml")
                    )
                    and not (
                        item.filename.startswith("xl/styles") and item.filename.endswith(".xml")
                    )
                    and item.filename != "xl/sharedStrings.xml"
                ):
                    raise UnsupportedWorkbookError(
                        "The workbook contains an unverified package feature."
                    )
    except UnsupportedWorkbookError:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise UnsupportedWorkbookError("The workbook package is corrupt or invalid.") from exc
    return inspect_workbook(data)
