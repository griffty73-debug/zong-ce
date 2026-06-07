from flask import Blueprint, Response, abort, request

from .helpers import current_user, master

export_bp = Blueprint("export", __name__)


def _filename(name: str, fmt: str) -> str:
    from datetime import datetime
    return f"{name}-{datetime.now().strftime('%Y%m%d%H%M%S')}.{fmt}"


@export_bp.get("/student-summary.<fmt>")
def student_summary(fmt: str):
    user = current_user()
    if user.role != "student":
        abort(403, description="仅学生可下载个人成绩单")
    term_id = request.args.get("termId", type=int)
    if fmt == "pdf":
        data = master().export.student_pdf(user, term_id=term_id)
        return Response(
            data,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_filename('student-summary', 'pdf')}"},
        )
    if fmt == "xlsx":
        data = master().export.student_xlsx(user, term_id=term_id)
        return Response(
            data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={_filename('student-summary', 'xlsx')}"},
        )
    abort(400, description="仅支持 pdf/xlsx 格式")


@export_bp.get("/ranking.<fmt>")
def ranking(fmt: str):
    user = current_user()
    if user.role not in {"counselor", "teacher"}:
        abort(403, description="仅老师/辅导员可导出排行榜")
    term_id = request.args.get("termId", type=int)
    anonymous = request.args.get("anonymous", "0") == "1"
    if fmt == "pdf":
        data = master().export.ranking_pdf(user, term_id=term_id, anonymous=anonymous)
        return Response(
            data,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_filename('ranking', 'pdf')}"},
        )
    if fmt == "xlsx":
        data = master().export.ranking_xlsx(user, term_id=term_id, anonymous=anonymous)
        return Response(
            data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={_filename('ranking', 'xlsx')}"},
        )
    abort(400, description="仅支持 pdf/xlsx 格式")
