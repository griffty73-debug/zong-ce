from datetime import date

from flask import abort

from ..models import Material


class RiskAgent:
    def inspect_material(self, payload: dict, material_id: int | None = None) -> dict:
        certificate_no = str(payload.get("certificateNo", "")).strip()
        expires_at = payload.get("expiresAt")
        issued_at = payload.get("issuedAt")
        reasons: list[str] = []

        if certificate_no and certificate_no != "无":
            query = Material.query.filter(Material.certificate_no == certificate_no)
            if material_id:
                query = query.filter(Material.id != material_id)
            if query.first():
                reasons.append("重复证书编号")

        if expires_at:
            expiry = date.fromisoformat(expires_at)
            if expiry < date.today():
                reasons.append("证书已过期")
        if issued_at:
            issued = date.fromisoformat(issued_at)
            if issued > date.today():
                reasons.append("发证日期晚于当前日期")

        risk_level = "high" if reasons else "low"
        return {"riskLevel": risk_level, "riskReasons": reasons}

    def assert_upload_allowed(self, inspection: dict) -> None:
        blocking = {"重复证书编号", "证书已过期", "发证日期晚于当前日期"}
        if blocking.intersection(set(inspection.get("riskReasons", []))):
            abort(422, description="; ".join(inspection["riskReasons"]))

    def report(self) -> dict:
        risky = Material.query.filter(Material.risk_level != "low").all()
        return {
            "totalRisk": len(risky),
            "items": [item.to_dict() for item in risky],
        }
