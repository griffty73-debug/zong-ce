from flask import Blueprint, jsonify, request

from ..agents import OrganizationAgent
from .helpers import current_user, json_payload

organization_bp = Blueprint("organization", __name__)


@organization_bp.get("/colleges")
def list_colleges():
    return jsonify(OrganizationAgent().list_colleges())


@organization_bp.post("/colleges")
def create_college():
    user = current_user()
    return jsonify(OrganizationAgent().create_college(user, json_payload()))


@organization_bp.get("/majors")
def list_majors():
    college_id = request.args.get("collegeId", type=int)
    return jsonify(OrganizationAgent().list_majors(college_id))


@organization_bp.post("/majors")
def create_major():
    user = current_user()
    return jsonify(OrganizationAgent().create_major(user, json_payload()))


@organization_bp.get("/classes")
def list_classes():
    major_id = request.args.get("majorId", type=int)
    return jsonify(OrganizationAgent().list_classes(major_id))


@organization_bp.post("/classes")
def create_class():
    user = current_user()
    return jsonify(OrganizationAgent().create_class(user, json_payload()))


@organization_bp.get("/tree")
def tree():
    return jsonify(OrganizationAgent().tree())
