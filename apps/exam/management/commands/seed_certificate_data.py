"""seed_certificate_data：基于已有学校/班级/学生，填充「学生证书 / 证书审核」演示数据。

用法示例：
    python manage.py seed_certificate_data --dry-run
    python manage.py seed_certificate_data --limit 3
    python manage.py seed_certificate_data --districts 510104,510105
    python manage.py seed_certificate_data --reset --yes

只复用 seed_chengdu_data 已创建的学校/班级/学生，不新建学生/班级，
不改 Certificate / StudentCertificate / AnswerSheet 模型与接口。
"""
import os
import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent, ClassTeacher
from apps.exam.models import AnswerSheet, Certificate, Paper, PaperPublish, StudentCertificate
from apps.org.models import Region, School
from apps.users.models import User

SUBJECTS = [(Paper.SUBJECT_MUSIC, "音乐"), (Paper.SUBJECT_ART, "美术")]

# 每张共享模板图片的规格（文件相对 media 根目录）
SEED_IMAGE_DIR = "cert-uploads/seed"

# 中文字体候选（找到即用中文模板，找不到降级为英文模板，不因缺字体而失败）
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

# 上传证书标题模板：按 (学科, 状态) 轮换，避免队列标题全部同名
UPLOAD_TITLES = {
    ("music", "pending"): [
        "成都市中小学生艺术节器乐比赛一等奖",
        "成都市青少年音乐才艺大赛二等奖",
        "成都市校园艺术节合唱比赛一等奖",
        "成都市中小学生艺术节独奏比赛三等奖",
    ],
    ("music", "approved"): [
        "四川省中小学生艺术展演二等奖",
        "成都市中小学生艺术节独唱比赛一等奖",
    ],
    ("music", "rejected"): [
        "成都市青少年音乐比赛参赛证书",
        "校级艺术之星评选证书",
    ],
    ("art", "pending"): [
        "成都市中小学生艺术节绘画比赛一等奖",
        "成都市青少年书画大赛二等奖",
        "成都市校园艺术节手工作品一等奖",
    ],
    ("art", "approved"): [
        "四川省青少年美术作品展二等奖",
        "成都市中小学生艺术节书法比赛一等奖",
    ],
    ("art", "rejected"): [
        "成都市青少年书画大赛参赛证书",
        "校级艺术之星评选证书",
    ],
}

# 每班上传证书的 (状态, 学科) 轮换：保证 pending/approved/rejected 与音乐/美术都覆盖
UPLOAD_SLOTS = [
    (StudentCertificate.STATUS_PENDING, StudentCertificate.SUBJECT_MUSIC),
    (StudentCertificate.STATUS_APPROVED, StudentCertificate.SUBJECT_ART),
    (StudentCertificate.STATUS_REJECTED, StudentCertificate.SUBJECT_MUSIC),
    (StudentCertificate.STATUS_PENDING, StudentCertificate.SUBJECT_ART),
    (StudentCertificate.STATUS_APPROVED, StudentCertificate.SUBJECT_MUSIC),
    (StudentCertificate.STATUS_REJECTED, StudentCertificate.SUBJECT_ART),
]

# 按学科映射的颁发机构
UPLOAD_ISSUER = {
    StudentCertificate.SUBJECT_MUSIC: "成都市教育局",
    StudentCertificate.SUBJECT_ART: "四川省教育厅",
}

# 按状态映射的备注与审核意见（note 不含 [演示数据] 前缀，运行时统一拼接）
UPLOAD_NOTE = {
    StudentCertificate.STATUS_PENDING: "参加艺术比赛获奖，请老师审核。",
    StudentCertificate.STATUS_APPROVED: "已上传证书照片，请老师审核。",
    StudentCertificate.STATUS_REJECTED: "证书照片不够清晰，请老师审核。",
}
UPLOAD_COMMENT = {
    StudentCertificate.STATUS_APPROVED: "证书真实有效，审核通过。",
    StudentCertificate.STATUS_REJECTED: "证书图片模糊，无法辨认颁发单位，请重新上传清晰照片。",
}


def _pick(ids, start, count):
    """从有序列表里取一段，越界时从头循环补齐，保证确定性。"""
    if not ids:
        return []
    total = len(ids)
    return [ids[(start + i) % total] for i in range(count)]


def _default_font(size=22):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # 老版本 Pillow 不支持 size 参数
        return ImageFont.load_default()


def _load_cjk_font(size=28):
    """尝试加载中文字体，找不到返回 None（降级为英文模板）。"""
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def _image_variant(subject, status, variant):
    """按 (学科, 状态, 变体) 返回 (边框色, 背景色, 印章位置框)，保持同一版式。"""
    width, height = 720, 480
    border = {1: "#c9a227", 2: "#8a6d1a", 3: "#b08d2f"}[variant]
    bg = {1: "#f5f0e6", 2: "#fbf7ef", 3: "#f2ecdd"}[variant]
    if variant == 1:
        seal = [width - 170, height - 170, width - 30, height - 30]  # 右下
    elif variant == 2:
        seal = [30, height - 170, 170, height - 30]                  # 左下
    else:
        seal = [width - 170, 30, width - 30, 170]                     # 右上
    return border, bg, seal


def _ensure_seed_images():
    """生成 18 张共享模板图片（2 学科 × 3 状态 × 3 变体，已存在则跳过）。"""
    from PIL import Image, ImageDraw

    seed_dir = os.path.join(settings.MEDIA_ROOT, SEED_IMAGE_DIR)
    os.makedirs(seed_dir, exist_ok=True)

    width, height = 720, 480
    cjk_font = _load_cjk_font(34)
    cjk_sub = _load_cjk_font(22) if cjk_font else None
    font_title = _default_font(34)
    font_sub = _default_font(20)

    for subject in (Paper.SUBJECT_MUSIC, Paper.SUBJECT_ART):
        for status in (
            StudentCertificate.STATUS_PENDING,
            StudentCertificate.STATUS_APPROVED,
            StudentCertificate.STATUS_REJECTED,
        ):
            for variant in (1, 2, 3):
                filename = f"{subject}_{status}_{variant}.png"
                path = os.path.join(seed_dir, filename)
                if os.path.exists(path):
                    continue

                border_color, bg_color, seal_box = _image_variant(subject, status, variant)
                img = Image.new("RGB", (width, height), bg_color)
                draw = ImageDraw.Draw(img)
                draw.rectangle([20, 20, width - 20, height - 20], outline=border_color, width=6)
                draw.rectangle([30, 30, width - 30, height - 30], outline=border_color, width=2)
                draw.ellipse(seal_box, outline="#c0392b", width=4)

                cx = width // 2
                if cjk_font:
                    lines = ["艺术素质测评证书", "成都市教育局", "2026"]
                    y = 150
                    for idx, text in enumerate(lines):
                        font = cjk_font if idx == 0 else cjk_sub
                        draw.text((cx - draw.textlength(text, font=font) // 2, y), text,
                                  fill="#8a6d1a" if idx == 0 else "#333333", font=font)
                        y += 90
                else:
                    subject_label = "MUSIC" if subject == Paper.SUBJECT_MUSIC else "ART"
                    title = f"{subject_label} CERTIFICATE"
                    draw.text((cx - draw.textlength(title, font=font_title) // 2, 140), title,
                              fill="#8a6d1a", font=font_title)
                    draw.text(
                        (cx - draw.textlength("Chengdu Primary & Secondary School", font=font_sub) // 2, 240),
                        "Chengdu Primary & Secondary School", fill="#333333", font=font_sub,
                    )
                    draw.text(
                        (cx - draw.textlength("Art Assessment 2026", font=font_sub) // 2, 280),
                        "Art Assessment 2026", fill="#333333", font=font_sub,
                    )
                img.save(path)

    return seed_dir


class Command(BaseCommand):
    help = "基于已有学校/班级/学生，填充已颁发证书（Certificate）与学生上传证书（StudentCertificate）演示数据。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计并打印将要生成的数量，不写库")
        parser.add_argument("--limit", type=int, default=None, help="只处理前 N 所学校（联调用）")
        parser.add_argument("--districts", type=str, default=None, help="只处理指定区县（code 或中文名，逗号分隔）")
        parser.add_argument("--per-class", type=int, default=4, help="每个班每学科生成的已颁发证书数，默认 4，范围 1-10")
        parser.add_argument("--uploads-per-class", type=int, default=3, help="每个班生成的上传证书数，默认 3，范围 3-6")
        parser.add_argument("--reset", action="store_true", help="删除本命令生成的演示证书数据（必须同时 --yes）")
        parser.add_argument("--yes", action="store_true", help="确认执行 --reset")

    # ---------------- 范围与前置检查 ----------------

    def _resolve_schools(self, districts, limit):
        schools_qs = School.objects.filter(is_deleted=False).order_by("code")
        if districts:
            tokens = [t.strip() for t in districts.split(",") if t.strip()]
            region_codes = set(
                Region.objects.filter(Q(code__in=tokens) | Q(name__in=tokens))
                .values_list("code", flat=True)
            )
            if not region_codes:
                raise CommandError(f"未找到匹配的区县：{districts}")
            schools_qs = schools_qs.filter(region__code__in=region_codes)
        if limit:
            schools_qs = schools_qs[:limit]
        return list(schools_qs)

    def _check_prerequisites(self):
        if not School.objects.filter(is_deleted=False).exists():
            raise CommandError("没有学校数据，请先执行 python manage.py seed_chengdu_data")
        if not ClassRoom.objects.filter(is_deleted=False).exists():
            raise CommandError("没有班级数据，请先执行 python manage.py seed_chengdu_data")
        if not ClassStudent.objects.filter(status=APPROVED, is_deleted=False).exists():
            raise CommandError("没有已通过审核的学生数据，请先执行 python manage.py seed_chengdu_data")

    # ---------------- 单所学校 ----------------

    @staticmethod
    def _resolve_creator(school):
        """学校管理员优先，其次任一教师；都没有则返回 None。"""
        return (
            User.objects.filter(role=User.ROLE_SCHOOL, school=school, is_active=True).first()
            or User.objects.filter(role=User.ROLE_TEACHER, school=school, is_active=True).first()
        )

    def _ensure_paper(self, school, subject, label, creator, now):
        title = f"【演示】{school.name}2026年秋季艺术素质测评（{label}）"[:128]
        paper = Paper.objects.filter(title=title).first()
        if paper is None:
            paper = Paper.objects.create(
                title=title,
                ptype=Paper.TYPE_FORMAL,
                subject=subject,
                level=Paper.LEVEL_SCHOOL,
                grade="",
                duration=45,
                total_score=Decimal("100"),
                status=Paper.STATUS_PUBLISHED,
                creator=creator,
            )
        elif paper.creator_id is None:
            paper.creator = creator
            paper.save(update_fields=["creator", "updated_at"])

        publish = PaperPublish.objects.filter(paper=paper, target_school=school).first()
        if publish is None:
            publish = PaperPublish.objects.create(
                paper=paper,
                scope_type=PaperPublish.SCOPE_SCHOOL,
                grade="",
                target_school=school,
                status=PaperPublish.STATUS_PUBLISHED,
                start_at=now - timedelta(days=30),
                end_at=now,
            )
        return paper, publish

    def _class_reviewers(self, school, class_ids):
        """返回 {klass_id: {course_code: teacher_id}} 与 {klass_id: head_teacher_id}。"""
        teacher_map = {}
        head_map = {}
        ct_qs = (
            ClassTeacher.objects.filter(
                klass_id__in=class_ids, status=APPROVED, is_deleted=False,
                course__code__in=["music", "art"],
            )
            .select_related("course")
            .order_by("id")
        )
        for ct in ct_qs:
            teacher_map.setdefault((ct.klass_id, ct.course.code if ct.course else ""), ct.teacher_id)
        for klass in ClassRoom.objects.filter(id__in=class_ids, is_deleted=False):
            if klass.head_teacher_id:
                head_map[klass.id] = klass.head_teacher_id
        school_admin_id = (
            User.objects.filter(role=User.ROLE_SCHOOL, school=school, is_active=True)
            .values_list("id", flat=True)
            .first()
        )
        return teacher_map, head_map, school_admin_id

    def _process_class_certificates(self, klass, paper, publish, subject, per_class, now):
        """为一个班级、一个学科生成答卷与已颁发证书。返回 (sheet_count, cert_count)。"""
        student_ids = list(
            ClassStudent.objects.filter(klass=klass, status=APPROVED, is_deleted=False)
            .order_by("student_id")
            .values_list("student_id", flat=True)
        )
        if not student_ids:
            return 0, 0

        start = 0 if subject == Paper.SUBJECT_MUSIC else per_class
        selected = _pick(student_ids, start, per_class)
        selected = list(dict.fromkeys(selected))  # 去重保序，避免同卷同学生重复

        rng = random.Random(f"{klass.code}-{subject}")
        sheets = []
        for sid in selected:
            r = rng.random()
            if r < 0.3:
                score = Decimal(rng.randint(850, 980)) / 10
            elif r < 0.8:
                score = Decimal(rng.randint(700, 840)) / 10
            else:
                score = Decimal(rng.randint(600, 690)) / 10
            sheets.append(AnswerSheet(
                paper=paper, student_id=sid, publish=publish,
                started_at=now - timedelta(days=30),
                submitted_at=now - timedelta(days=29),
                is_submitted=True, total_score=score,
            ))
        AnswerSheet.objects.bulk_create(sheets, batch_size=500, ignore_conflicts=True)

        sheet_qs = AnswerSheet.objects.filter(
            paper=paper, publish=publish, student_id__in=[s.student_id for s in sheets],
        )
        cert_title = f"2026年成都市中小学生艺术素质测评{'音乐' if subject == Paper.SUBJECT_MUSIC else '美术'}证书"
        certs = [
            Certificate(student_id=s.student_id, sheet_id=s.id, subject=subject, title=cert_title)
            for s in sheet_qs
        ]
        Certificate.objects.bulk_create(certs, batch_size=500, ignore_conflicts=True)
        return len(sheet_qs), len(certs)

    def _process_class_uploads(self, klass, student_ids, uploads_per_class,
                               teacher_map, head_map, school_admin_id, now, today):
        """为一个班级生成上传待审核证书。返回 (created_count, {status: count})。"""
        records = []
        for i in range(uploads_per_class):
            if not student_ids:
                break
            status, subject = UPLOAD_SLOTS[i % len(UPLOAD_SLOTS)]
            sid = student_ids[i % len(student_ids)]
            titles = UPLOAD_TITLES[(subject, status)]
            title = titles[sid % len(titles)]
            variant = sid % 3 + 1
            is_pending = status == StudentCertificate.STATUS_PENDING
            reviewer_id = None if is_pending else (
                teacher_map.get((klass.id, subject))
                or head_map.get(klass.id)
                or school_admin_id
            )
            records.append(StudentCertificate(
                student_id=sid,
                title=title,
                cert_type=StudentCertificate.CERT_COMPETITION,
                subject=subject,
                issuer=UPLOAD_ISSUER[subject],
                obtained_at=today - timedelta(days=60 + i * 30),
                image=f"{SEED_IMAGE_DIR}/{subject}_{status}_{variant}.png",
                note=f"[演示数据] {UPLOAD_NOTE[status]}",
                status=status,
                reviewer_id=reviewer_id,
                review_comment="" if is_pending else UPLOAD_COMMENT[status],
                reviewed_at=None if is_pending else now,
            ))

        # 幂等：按 (student, title) 去重
        existing = set(
            StudentCertificate.objects.filter(
                note__startswith="[演示数据]",
                student_id__in=[r.student_id for r in records],
                title__in=[r.title for r in records],
            ).values_list("student_id", "title")
        )
        records = [r for r in records if (r.student_id, r.title) not in existing]
        if records:
            StudentCertificate.objects.bulk_create(records, batch_size=500)

        status_count = {"pending": 0, "approved": 0, "rejected": 0}
        for r in records:
            status_count[r.status] += 1
        return len(records), status_count

    def _process_school(self, school, per_class, uploads_per_class, now, today):
        """处理一所学校：两套演示试卷 + 各班级证书 + 上传证书。返回统计或 None（跳过）。"""
        creator = self._resolve_creator(school)
        if creator is None:
            return None

        papers = {}
        for subject, label in SUBJECTS:
            papers[subject] = self._ensure_paper(school, subject, label, creator, now)

        classes = list(ClassRoom.objects.filter(school=school, is_deleted=False).order_by("code"))
        if not classes:
            return {"school": school, "classes": 0, "sheets": 0, "certs": 0, "uploads": 0,
                    "uploads_by_status": {"pending": 0, "approved": 0, "rejected": 0}}

        teacher_map, head_map, school_admin_id = self._class_reviewers(
            school, [c.id for c in classes],
        )

        sheet_count = cert_count = upload_count = 0
        uploads_by_status = {"pending": 0, "approved": 0, "rejected": 0}
        for klass in classes:
            student_ids = list(
                ClassStudent.objects.filter(klass=klass, status=APPROVED, is_deleted=False)
                .order_by("student_id")
                .values_list("student_id", flat=True)
            )
            for subject, (paper, publish) in papers.items():
                sc, cc = self._process_class_certificates(klass, paper, publish, subject, per_class, now)
                sheet_count += sc
                cert_count += cc
            uc, us = self._process_class_uploads(
                klass, student_ids, uploads_per_class,
                teacher_map, head_map, school_admin_id, now, today,
            )
            upload_count += uc
            for k, v in us.items():
                uploads_by_status[k] += v

        return {
            "school": school, "classes": len(classes),
            "sheets": sheet_count, "certs": cert_count, "uploads": upload_count,
            "uploads_by_status": uploads_by_status,
        }

    # ---------------- 主流程 ----------------

    def _do_reset(self, school_ids, yes):
        papers_qs = Paper.objects.filter(title__startswith="【演示】", creator__school_id__in=school_ids)
        scs_qs = StudentCertificate.objects.filter(
            note__startswith="[演示数据]", student__school_id__in=school_ids,
        )
        paper_count = papers_qs.count()
        sc_count = scs_qs.count()
        self.stdout.write(self.style.WARNING(
            f"即将删除：演示试卷 {paper_count} 份（含其发布记录/答卷/证书）、上传证书 {sc_count} 条"
        ))
        if not yes:
            raise CommandError("--reset 必须同时传 --yes 确认（上面列出了将被删除的数量）")
        papers_qs.delete()
        scs_qs.delete()
        self.stdout.write(self.style.SUCCESS("清理完成，继续生成……"))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        districts = options["districts"]
        per_class = options["per_class"]
        uploads_per_class = options["uploads_per_class"]
        reset = options["reset"]
        yes = options["yes"]

        if not (1 <= per_class <= 10):
            raise CommandError("--per-class 取值范围为 1-10")
        if not (3 <= uploads_per_class <= 6):
            raise CommandError("--uploads-per-class 取值范围为 3-6")

        self._check_prerequisites()

        schools = self._resolve_schools(districts, limit)
        if not schools:
            raise CommandError("没有匹配的学校")
        school_ids = [s.id for s in schools]

        if reset:
            # 不带 --yes 只打印数量并退出；带 --yes 删除后继续执行本次生成
            self._do_reset(school_ids, yes)

        now = timezone.now()
        today = date.today()

        if dry_run:
            self.stdout.write(self.style.SUCCESS("== dry-run（不写库） =="))
            school_count = class_count = sheet_count = cert_count = upload_count = 0
            uploads_by_status = {"pending": 0, "approved": 0, "rejected": 0}
            skipped = 0
            for school in schools:
                if self._resolve_creator(school) is None:
                    skipped += 1
                    continue
                school_count += 1
                classes = ClassRoom.objects.filter(school=school, is_deleted=False).order_by("code")
                class_count += len(classes)
                for klass in classes:
                    n = ClassStudent.objects.filter(
                        klass=klass, status=APPROVED, is_deleted=False,
                    ).count()
                    if n == 0:
                        continue
                    for subject, _label in SUBJECTS:
                        c = min(per_class, n)
                        sheet_count += c
                        cert_count += c
                    u = min(uploads_per_class, n)
                    upload_count += u
                    for i in range(u):
                        uploads_by_status[UPLOAD_SLOTS[i % len(UPLOAD_SLOTS)][0]] += 1

            self.stdout.write(f"  学校：{school_count} 所（跳过无管理员/教师的 {skipped} 所）")
            self.stdout.write(f"  班级：{class_count} 个")
            self.stdout.write(f"  演示试卷：{school_count * 2} 份（每校音乐/美术各 1）")
            self.stdout.write(f"  发布记录：{school_count * 2} 条")
            self.stdout.write(f"  答卷：约 {sheet_count} 份")
            self.stdout.write(f"  已颁发证书：约 {cert_count} 条")
            self.stdout.write(
                f"  上传证书：约 {upload_count} 条"
                f"（待审核 {uploads_by_status['pending']}、已通过 {uploads_by_status['approved']}、"
                f"已驳回 {uploads_by_status['rejected']}）"
            )
            return

        # 生成共享模板图片（幂等，已存在则跳过）
        seed_dir = _ensure_seed_images()
        self.stdout.write(f"共享模板图片目录：{seed_dir}")

        stats = {"schools": 0, "skipped": 0, "classes": 0, "sheets": 0, "certs": 0, "uploads": 0,
                 "uploads_by_status": {"pending": 0, "approved": 0, "rejected": 0}}
        total = len(schools)
        for i, school in enumerate(schools, start=1):
            with transaction.atomic():
                result = self._process_school(school, per_class, uploads_per_class, now, today)
            if result is None:
                stats["skipped"] += 1
                self.stdout.write(self.style.WARNING(
                    f"  跳过 {school.name}：没有学校管理员/教师账号"
                ))
                continue
            stats["schools"] += 1
            stats["classes"] += result["classes"]
            stats["sheets"] += result["sheets"]
            stats["certs"] += result["certs"]
            stats["uploads"] += result["uploads"]
            for k, v in result["uploads_by_status"].items():
                stats["uploads_by_status"][k] += v
            if i % 10 == 0:
                self.stdout.write(f"  已处理 {i}/{total} 所学校……")

        self.stdout.write(self.style.SUCCESS("== 完成 =="))
        self.stdout.write(f"  学校：{stats['schools']} 所（跳过 {stats['skipped']} 所）")
        self.stdout.write(f"  班级：{stats['classes']} 个")
        self.stdout.write(f"  演示试卷：{stats['schools'] * 2} 份")
        self.stdout.write(f"  答卷：{stats['sheets']} 份")
        self.stdout.write(f"  已颁发证书：{stats['certs']} 条")
        self.stdout.write(
            f"  上传证书：{stats['uploads']} 条"
            f"（待审核 {stats['uploads_by_status']['pending']}、"
            f"已通过 {stats['uploads_by_status']['approved']}、"
            f"已驳回 {stats['uploads_by_status']['rejected']}）"
        )
