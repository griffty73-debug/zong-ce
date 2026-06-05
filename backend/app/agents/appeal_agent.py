from flask import abort

from ..extensions import db
from ..models import Appeal, Material, User, utc_now
from ..state_machine import MaterialStatus, assert_transition
from .common import ensure_role
from .responses import agent_response


class AppealAgent:
    def submit(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"student"})
        material = db.session.get(Material, payload.get("materialId"))
        if not material or material.student_id != user.id:
            abort(404, description="材料不存在")
        if material.status != MaterialStatus.PUBLICIZING.value:
            abort(400, description="申诉仅在公示中生效")
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            abort(400, description="申诉原因不能为空")

        assert_transition(material.status, MaterialStatus.APPEALING)
        material.status = MaterialStatus.APPEALING.value
        appeal = Appeal(material_id=material.id, student_id=user.id, reason=reason)
        db.session.add(appeal)
        db.session.commit()
        return agent_response(
            agent="Appeal Agent",
            message="已收到您的异议反馈，当前综测分数已暂停结算。请补充具体争议点和有效证明材料。",
            suggestions_key="appeal",
            data={"appeal": appeal.to_dict()},
        )

    def list(self, user: User) -> dict:
        query = Appeal.query
        if user.role == "student":
            query = query.filter_by(student_id=user.id)
        else:
            ensure_role(user, {"teacher", "counselor"})
            if user.role == "counselor" and user.class_name:
                query = query.join(User, Appeal.student_id == User.id).filter(User.class_name == user.class_name)
        appeals = query.order_by(Appeal.created_at.desc()).all()
        return agent_response(
            agent="Appeal Agent",
            message="申诉列表已加载",
            suggestions_key="appeal",
            data={"items": [item.to_dict() for item in appeals]},
        )

    def detail(self, user: User, appeal_id: int) -> dict:
        appeal = db.session.get(Appeal, appeal_id)
        if not appeal:
            abort(404, description="申诉不存在")
        if user.role == "student" and appeal.student_id != user.id:
            abort(403, description="无权查看该申诉")
        if user.role not in {"student", "teacher", "counselor"}:
            abort(403, description="当前角色无权访问该功能")
        return agent_response(
            agent="Appeal Agent",
            message="申诉详情已加载",
            suggestions_key="appeal",
            data={"appeal": appeal.to_dict()},
        )

    def resolve(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"teacher", "counselor"})
        appeal = db.session.get(Appeal, payload.get("appealId"))
        if not appeal:
            abort(404, description="申诉不存在")
        action = payload.get("action")
        opinion = str(payload.get("opinion", "")).strip()
        if action not in {"accept", "reject"} or not opinion:
            abort(400, description="复核动作和意见不能为空")

        appeal.status = "已通过" if action == "accept" else "已驳回"
        appeal.result_opinion = opinion
        appeal.resolved_at = utc_now()
        target = MaterialStatus.PUBLICIZING if action == "accept" else MaterialStatus.PUBLICITY_ENDED
        assert_transition(appeal.material.status, target)
        appeal.material.status = target.value
        db.session.commit()
        return agent_response(
            agent="Appeal Agent",
            message="复核处理完成",
            suggestions_key="appeal",
            data={"appeal": appeal.to_dict()},
        )

    def confirm_review(self, user: User, payload: dict) -> dict:
        ensure_role(user, {"student"})
        decision = str(payload.get("decision", "")).strip()
        if decision not in {"正确", "有问题"}:
            abort(400, description="请回复“正确”或“有问题”以完成一审结果确认")

        material_id = payload.get("materialId")
        query = Material.query.filter_by(student_id=user.id, status=MaterialStatus.APPROVED.value)
        material = db.session.get(Material, material_id) if material_id else query.order_by(Material.updated_at.desc()).first()
        if not material or material.student_id != user.id:
            abort(404, description="暂无可确认的一审材料")

        if decision == "正确":
            total = self._approved_total(user)
            return agent_response(
                agent="Appeal Agent",
                message=f"您的综测项目及加减分已最终确认无误。正在为您累加并锁定最终综测分数：{total:.2f} 分。数据已同步至班级待公示库，感谢您的配合！",
                suggestions_key="publicity",
                data={"material": material.to_dict(), "totalScore": total},
            )

        reason = str(payload.get("reason", "")).strip()
        if not reason:
            abort(400, description="请说明具体存在的问题，如哪个项目算错或漏算")
        assert_transition(material.status, MaterialStatus.APPEALING)
        material.status = MaterialStatus.APPEALING.value
        appeal = Appeal(material_id=material.id, student_id=user.id, reason=reason)
        db.session.add(appeal)
        db.session.commit()
        return agent_response(
            agent="Appeal Agent",
            message="【二次复核受理报告】\n"
            f"申诉学号：{user.student_no}\n"
            f"争议项目：{reason}\n"
            "新提交证明核验：已记录补充材料入口，等待有效证明上传\n"
            "复核初步意见：申诉材料已打包，正在流转至[辅导员二审]进行最终复核裁决。",
            suggestions_key="appeal",
            data={"appeal": appeal.to_dict(), "material": material.to_dict()},
        )

    def _approved_total(self, user: User) -> float:
        materials = Material.query.filter_by(student_id=user.id).filter(
            Material.status.in_(
                [
                    MaterialStatus.APPROVED.value,
                    MaterialStatus.PUBLICIZING.value,
                    MaterialStatus.PUBLICITY_ENDED.value,
                ]
            )
        )
        return round(sum(float(item.score) for item in materials), 2)
