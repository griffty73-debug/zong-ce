from flask import Blueprint, jsonify

from ..agents import TermAgent
from .helpers import current_user, json_payload

terms_bp = Blueprint("terms", __name__)


@terms_bp.get("/list")
def list_terms():
    return jsonify(TermAgent().list_terms())


@terms_bp.get("/current")
def current():
    return jsonify({"term": TermAgent().current_term()})


@terms_bp.post("/")
def create():
    user = current_user()
    return jsonify(TermAgent().create(user, json_payload()))


@terms_bp.patch("/<int:term_id>")
def update(term_id: int):
    user = current_user()
    return jsonify(TermAgent().update(user, term_id, json_payload()))


@terms_bp.delete("/<int:term_id>")
def delete(term_id: int):
    user = current_user()
    return jsonify(TermAgent().delete(user, term_id))
