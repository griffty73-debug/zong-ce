from datetime import date, timedelta, datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import Material, ReviewRecord, User, Appeal, PublicityBatch
from app.state_machine import MaterialStatus


def upsert_user(student_no: str, name: str, role: str, class_name: str, password: str) -> User:
    user = User.query.filter_by(student_no=student_no).first()
    if not user:
        user = User(student_no=student_no, name=name, role=role, class_name=class_name)
        user.set_password(password)
        db.session.add(user)
    else:
        user.name = name
        user.role = role
        user.class_name = class_name
        user.set_password(password)
    return user


def seed() -> None:
    # === Users ===
    students = []
    for i in range(1, 81):
        no = f"{20000000000 + i}"
        name = f"学生{i:02d}"
        class_name = "计科2301" if i <= 50 else "软工2301"
        students.append(upsert_user(no, name, "student", class_name, "123456"))

    teacher = upsert_user("10000000001", "张老师", "teacher", "计科2301", "123456")
    teacher_two = upsert_user("10000000002", "李老师", "teacher", "软工2301", "123456")
    counselor = upsert_user("admin", "陈辅导员", "counselor", "计科2301", "admin123")
    db.session.flush()

    # === Materials ===
    categories = ["德育", "智育", "体育", "美育", "劳育"]
    titles = {
        "德育": ["三好学生", "优秀学生干部", "志愿服务之星", "社会实践优秀个人", "道德模范"],
        "智育": ["程序设计竞赛奖", "数学竞赛奖", "英语竞赛奖", "科研创新项目", "学术论文发表"],
        "体育": ["运动会第一名", "篮球赛冠军", "足球赛冠军", "游泳比赛奖", "田径赛奖"],
        "美育": ["文艺汇演优秀奖", "书画比赛奖", "摄影比赛奖", "音乐比赛奖", "舞蹈比赛奖"],
        "劳育": ["劳动实践优秀", "志愿服务时长认证", "社区服务之星", "公益活动奖", "勤工俭学之星"],
    }

    cert_counter = 1000
    for idx, student in enumerate(students):
        for cat_idx, category in enumerate(categories):
            if idx % 5 == cat_idx:
                title_list = titles[category]
                title = title_list[idx % len(title_list)]
                cert_no = f"CERT-{cert_counter:06d}"
                cert_counter += 1

                status_choices = list(MaterialStatus)
                status = status_choices[idx % len(status_choices)]

                material = Material(
                    student_id=student.id,
                    title=f"{title}{(idx // 5) + 1}",
                    category=category,
                    description=f"{category}{title}证明材料",
                    certificate_no=cert_no,
                    issued_at=date.today() - timedelta(days=30 + idx * 2),
                    expires_at=date.today() + timedelta(days=365),
                    score=float(5 + idx % 15),
                    status=status,
                )
                db.session.add(material)
                db.session.flush()

                if status in {MaterialStatus.APPROVED, MaterialStatus.PUBLICIZING,
                              MaterialStatus.PUBLICITY_ENDED, MaterialStatus.APPEALING}:
                    reviewer = teacher if idx % 2 == 0 else teacher_two
                    db.session.add(ReviewRecord(
                        material_id=material.id,
                        reviewer_id=reviewer.id,
                        action="通过",
                        opinion="材料审核通过。",
                        score_delta=0,
                    ))

                if idx % 17 == 0 and status == MaterialStatus.PUBLICIZING:
                    db.session.add(Appeal(
                        material_id=material.id,
                        student_id=student.id,
                        reason="对加分有异议，请重新审核。",
                        status="待处理",
                    ))

    # === Publicity Batches ===
    class_names = ["计科2301", "软工2301"]
    for i in range(1, 4):
        title = f"2023-2024学年第{i}学期综测公示"
        if not PublicityBatch.query.filter_by(title=title).first():
            status = "公示中" if i == 3 else "公示结束"
            starts = datetime.now() - timedelta(days=30 * (3 - i))
            ends = starts + timedelta(days=7) if i == 3 else starts + timedelta(days=7) - timedelta(days=1)
            pb = PublicityBatch(
                title=title,
                class_name=class_names[i % 2],
                status=status,
                starts_at=starts,
                ends_at=ends,
                created_by_id=counselor.id,
            )
            db.session.add(pb)

    db.session.commit()
    print("Demo data seeded.")
    print(f"Students: 20230010001~20230010080 / 123456 ({len(students)} students)")
    print("Teacher: 10000000001 / 123456, 10000000002 / 123456")
    print("Counselor: admin / admin123")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
