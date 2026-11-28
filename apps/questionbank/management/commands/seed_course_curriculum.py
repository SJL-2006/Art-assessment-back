"""seed_course_curriculum：按年级重建「音乐/美术」课程章节（两级树）+ 发布到所有班级。

用法示例：
    python manage.py seed_course_curriculum --dry-run
    python manage.py seed_course_curriculum
    python manage.py seed_course_curriculum --reset --yes
    python manage.py seed_course_curriculum --skip-publish

只改 Course.description / Chapter 数据 + ClassCourse 发布，不改模型、不需要迁移；
保留「音乐」「美术」两条主课程，不按年级拆课程、不加 grade 字段。
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.classroom.models import APPROVED, ClassCourse, ClassRoom, ClassStudent, ClassTeacher
from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User

GRADES = [
    "一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
    "七年级", "八年级", "九年级", "高一", "高二", "高三",
]
SEMESTERS = ["上册", "下册"]

CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

MUSIC_DESCRIPTION = (
    "依据《义务教育艺术课程标准（2022年版）》编排，按年级分册组织聆听、演唱、演奏、编创与欣赏等学习内容，"
    "帮助学生在艺术实践中感受美、表现美、创造美。"
)
ART_DESCRIPTION = (
    "依据《义务教育艺术课程标准（2022年版）》编排，按年级分册组织造型·表现、设计·应用、欣赏·评述、综合·探索等学习内容，"
    "培养学生的图像识读、美术表现与审美判断能力。"
)

MUSIC_CURRICULUM = {
    "一年级": {
        "上册": ["好朋友", "快乐的一天", "祖国您好", "可爱的动物", "爱劳动", "小精灵", "过新年", "迎新春"],
        "下册": ["春天", "放牧", "手拉手", "长鼻子", "游戏", "美好的夜", "巧巧手", "时间的歌"],
    },
    "二年级": {
        "上册": ["问声好", "幸福的歌", "音乐会", "咯咯哒", "童趣", "新年好"],
        "下册": ["春天来了", "难忘的歌", "飞呀飞", "美丽家园", "调皮的小闹钟", "新疆好"],
    },
    "三年级": {
        "上册": ["童年", "草原", "好伙伴", "妈妈的歌", "四季的歌", "钟声"],
        "下册": ["春天", "可爱的家", "我们的朋友", "绿色的风", "老师您辛苦了", "家乡美"],
    },
    "四年级": {
        "上册": ["歌唱祖国", "家乡美", "快乐的校园", "甜梦", "水上的歌", "祝你快乐"],
        "下册": ["跳起来", "少年的歌", "水乡", "风景如画", "摇篮曲", "向往"],
    },
    "五年级": {
        "上册": ["朝夕", "足迹", "农家乐", "可爱的家", "快乐的少年", "冬雪"],
        "下册": ["春景", "欢乐的村寨", "飞翔的梦", "你好！大自然", "京韵", "童年的回忆"],
    },
    "六年级": {
        "上册": ["我的祖国", "美丽的草原", "星空", "快乐少年", "京腔京韵", "难忘的歌"],
        "下册": ["古风新韵", "月下踏歌", "明天会更好", "快乐的阳光", "感恩的心", "毕业歌"],
    },
    "七年级": {
        "上册": ["歌唱祖国", "缤纷舞曲", "草原牧歌", "欧洲风情", "音乐与生活"],
        "下册": ["行进之歌", "影视金曲", "天山之春", "亚洲之声", "音乐与戏剧"],
    },
    "八年级": {
        "上册": ["青春舞曲", "多彩音乐剧", "雪域天音", "国乐飘香", "音乐与科技"],
        "下册": ["生命之杯", "乐海泛舟", "山野放歌", "亚洲弦歌", "音乐与影视"],
    },
    "九年级": {
        "上册": ["经典交响", "民歌拾萃", "戏曲天地", "器乐名篇", "音乐与人生"],
        "下册": ["时代旋律", "世界音乐", "艺术歌曲", "影视音乐", "毕业之歌"],
    },
    "高一": {
        "上册": ["音乐鉴赏（一）：音乐与生活", "中国民族音乐", "西方古典音乐", "音乐的形式美"],
        "下册": ["音乐鉴赏（二）：浪漫主义音乐", "民族乐派", "20世纪音乐", "影视与流行音乐"],
    },
    "高二": {
        "上册": ["歌唱（一）：歌唱基础", "中国声乐作品", "外国声乐作品", "合唱实践"],
        "下册": ["演奏与编创（二）：器乐基础", "合奏实践", "音乐编创", "校园艺术活动"],
    },
    "高三": {
        "上册": ["音乐与舞蹈", "戏剧表演", "音乐与社会", "综合艺术实践"],
        "下册": ["艺术展演与测评", "经典作品复习", "毕业音乐会", "艺术素养总结"],
    },
}

ART_CURRICULUM = {
    "一年级": {
        "上册": ["大家一起画", "绕绕涂涂", "大自然中的线条", "美丽的天空", "花点心", "玩泥巴", "可爱的动物", "过新年"],
        "下册": ["春天在哪里", "我们身边的线条", "太阳", "漂亮的瓶子", "船", "手形的联想", "我和昆虫", "童话中的城堡"],
    },
    "二年级": {
        "上册": ["流动的线条", "色彩万花筒", "好看的瓶子", "动物朋友", "手工乐园", "我们的节日"],
        "下册": ["春天来了", "点线面", "花儿朵朵", "设计小天地", "民间美术", "童话王国"],
    },
    "三年级": {
        "上册": ["色彩基础", "点线面", "形的组合", "手工制作", "动物世界", "校园生活"],
        "下册": ["春天的色彩", "设计应用", "中国画启蒙", "版画初体验", "民间美术", "综合探索"],
    },
    "四年级": {
        "上册": ["造型基础", "色彩冷暖", "透视初步", "设计基础", "传统纹样", "综合探索"],
        "下册": ["风景写生", "人物动态", "中国画", "版画", "手工设计", "校园艺术"],
    },
    "五年级": {
        "上册": ["素描基础", "色彩表现", "构图基础", "设计应用", "中国画", "民间美术"],
        "下册": ["风景创作", "人物表现", "版画", "雕塑初步", "摄影基础", "综合探索"],
    },
    "六年级": {
        "上册": ["造型表现", "色彩创作", "透视与空间", "设计应用", "中国画", "欣赏评述"],
        "下册": ["主题创作", "人物写生", "版画", "陶艺", "摄影", "毕业创作"],
    },
    "七年级": {
        "上册": ["美术鉴赏基础", "造型基础", "色彩基础", "设计基础", "中国画"],
        "下册": ["素描", "色彩", "版画", "雕塑", "民间美术"],
    },
    "八年级": {
        "上册": ["中外美术鉴赏", "素描", "色彩", "中国画", "设计"],
        "下册": ["人物速写", "风景写生", "版画", "陶艺", "摄影"],
    },
    "九年级": {
        "上册": ["美术鉴赏", "造型表现", "设计应用", "中国画", "书法篆刻"],
        "下册": ["主题创作", "人物表现", "版画", "雕塑", "数字美术"],
    },
    "高一": {
        "上册": ["美术鉴赏（一）：美术与生活", "中国美术鉴赏", "外国美术鉴赏", "美术的形式美"],
        "下册": ["美术鉴赏（二）：现代美术", "民间美术", "建筑与园林", "设计艺术"],
    },
    "高二": {
        "上册": ["绘画（一）：素描基础", "色彩基础", "中国画基础", "写生实践"],
        "下册": ["绘画（二）：人物画", "风景画", "版画", "综合材料"],
    },
    "高三": {
        "上册": ["设计·工艺：平面设计", "立体设计", "工艺制作", "数字媒体艺术"],
        "下册": ["艺术展演与测评", "毕业创作", "作品集整理", "艺术素养总结"],
    },
}


def _count_curriculum(curriculum):
    """统计一份课程表将产生的顶层学期章节数与单元子章节数。"""
    top = 0
    units = 0
    for grade in GRADES:
        for semester in SEMESTERS:
            top += 1
            units += len(curriculum[grade][semester])
    return top, units


class Command(BaseCommand):
    help = "按年级重建「音乐/美术」课程章节（两级树）并发布到所有班级。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计将创建/删除的章节，不写库")
        parser.add_argument("--reset", action="store_true", help="删除「音乐/美术」现有章节后重建（必须同时 --yes）")
        parser.add_argument("--yes", action="store_true", help="确认执行 --reset")
        parser.add_argument("--skip-publish", action="store_true", help="不发布课程到班级（默认会发布）")

    # ---------------- 课程 ----------------

    def _get_courses(self):
        """读取/创建「音乐」「美术」，写入简介（code 保持 music/art）。"""
        music, _ = Course.objects.get_or_create(name="音乐", defaults={"code": "music"})
        art, _ = Course.objects.get_or_create(name="美术", defaults={"code": "art"})
        if not music.code:
            music.code = "music"
        if not art.code:
            art.code = "art"
        music.description = MUSIC_DESCRIPTION
        art.description = ART_DESCRIPTION
        music.save()
        art.save()
        return music, art

    # ---------------- 章节 ----------------

    def _build_curriculum(self, course, curriculum):
        """为单门课程创建顶层学期章节 + 子级单元章节，返回 (顶层数, 单元数)。"""
        top_count = 0
        unit_count = 0
        for grade_index, grade in enumerate(GRADES):
            for semester in SEMESTERS:
                semester_index = 0 if semester == "上册" else 1
                top, _ = Chapter.objects.update_or_create(
                    course=course, parent=None, name=f"{grade}{semester}",
                    defaults={
                        "sort": grade_index * 10 + semester_index,
                        "is_deleted": False, "deleted_at": None,
                    },
                )
                top_count += 1
                for unit_index, raw_name in enumerate(curriculum[grade][semester], start=1):
                    Chapter.objects.update_or_create(
                        course=course, parent=top, name=f"第{CN[unit_index - 1]}单元 {raw_name}",
                        defaults={"sort": unit_index, "is_deleted": False, "deleted_at": None},
                    )
                    unit_count += 1
        return top_count, unit_count

    def _reset_chapters(self, music, art):
        """删除「音乐/美术」下所有章节；题目 chapter 置空（SET_NULL），不删题目。"""
        chapters = Chapter.objects.filter(course__in=[music, art])
        affected = Question.objects.filter(chapter__in=chapters).count()
        count = chapters.count()
        chapters.delete()
        self.stdout.write(self.style.SUCCESS(f"已删除旧章节 {count} 个，影响题目 {affected} 条（题目 chapter 已置空）"))

    # ---------------- 课程发布 ----------------

    def _publish_all(self, music, art):
        """确保所有班级都有「音乐」「美术」的 ClassCourse（默认执行）。"""
        if "classroom_class_course" not in connection.introspection.table_names():
            self.stdout.write(self.style.WARNING("classroom_class_course 表不存在，请先执行 python manage.py migrate"))
            return

        classes = list(
            ClassRoom.objects.filter(is_deleted=False)
            .select_related("school", "head_teacher")
            .order_by("id")
        )
        if not classes:
            self.stdout.write("没有班级，跳过课程发布。")
            return

        class_ids = [c.id for c in classes]
        course_ids = [music.id, art.id]

        # 任课教师映射 (klass_id, course_id) -> teacher
        ct_map = {}
        for ct in ClassTeacher.objects.filter(
            klass_id__in=class_ids, course_id__in=course_ids,
            status=APPROVED, is_deleted=False,
        ).select_related("teacher"):
            ct_map.setdefault((ct.klass_id, ct.course_id), ct.teacher)

        # 学校管理员映射 school_id -> admin
        school_ids = {c.school_id for c in classes}
        admin_map = {}
        for u in User.objects.filter(role=User.ROLE_SCHOOL, school_id__in=school_ids, is_active=True):
            admin_map.setdefault(u.school_id, u)

        created = 0
        total = len(classes)
        for i, klass in enumerate(classes, start=1):
            for course in (music, art):
                publisher = ct_map.get((klass.id, course.id)) or klass.head_teacher or admin_map.get(klass.school_id)
                link = ClassCourse.objects.filter(class_room=klass, course=course).first()
                if link is None:
                    ClassCourse.objects.create(class_room=klass, course=course, published_by=publisher)
                    created += 1
                elif link.is_deleted:
                    link.is_deleted = False
                    link.deleted_at = None
                    link.published_by = publisher
                    link.save(update_fields=["is_deleted", "deleted_at", "published_by", "updated_at"])
                    created += 1
            if i % 200 == 0:
                self.stdout.write(f"  已处理 {i}/{total} 个班级……")

        self.stdout.write(self.style.SUCCESS(f"课程发布完成：处理 {total} 个班级，新增/恢复 {created} 条 ClassCourse"))

    # ---------------- 罗雨欣验证 ----------------

    def _verify_luoyuxin(self, music, art):
        student = (
            User.objects.filter(real_name="罗雨欣", role=User.ROLE_STUDENT, is_active=True)
            .filter(class_memberships__klass__grade="一年级")
            .order_by("id")
            .first()
        )
        if student is None:
            self.stdout.write(self.style.WARNING("未找到「罗雨欣」的一年级学生，跳过验证。"))
            return
        membership = ClassStudent.objects.filter(
            student=student, status=APPROVED, is_deleted=False,
        ).select_related("klass", "klass__school").first()
        if membership is None:
            self.stdout.write(self.style.WARNING(f"罗雨欣（学号 {student.student_no}）无已通过的一年级班级，跳过验证。"))
            return

        self.stdout.write(self.style.SUCCESS("== 罗雨欣验证 =="))
        self.stdout.write(f"  罗雨欣：{membership.klass.school.name} {membership.klass.name} 学号 {student.student_no}")
        if "classroom_class_course" in connection.introspection.table_names():
            published = list(
                ClassCourse.objects.filter(
                    class_room=membership.klass, course__in=[music, art], is_deleted=False,
                ).values_list("course__name", flat=True)
            )
        else:
            published = ["（classroom_class_course 表不存在，请先 migrate）"]
        self.stdout.write(f"  课程发布：{published}")
        grade_chapters = list(
            Chapter.objects.filter(
                course__in=[music, art], name__startswith="一年级",
            ).order_by("course_id", "sort").values_list("course__name", "name")
        )
        self.stdout.write(f"  一年级章节：{grade_chapters}")

    # ---------------- 主流程 ----------------

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        reset = options["reset"]
        yes = options["yes"]
        skip_publish = options["skip_publish"]

        if dry_run:
            m_top, m_units = _count_curriculum(MUSIC_CURRICULUM)
            a_top, a_units = _count_curriculum(ART_CURRICULUM)
            self.stdout.write(self.style.SUCCESS("== dry-run（不写库） =="))
            self.stdout.write(f"  音乐：顶层学期章节 {m_top} 个 + 单元子章节 {m_units} 个 = {m_top + m_units} 个节点")
            self.stdout.write(f"  美术：顶层学期章节 {a_top} 个 + 单元子章节 {a_units} 个 = {a_top + a_units} 个节点")
            existing = Chapter.objects.filter(
                course__name__in=["音乐", "美术"],
            ).count()
            if existing:
                self.stdout.write(f"  现有「音乐/美术」章节 {existing} 个（--reset --yes 会先删除）")
            return

        music, art = self._get_courses()

        if reset:
            if not yes:
                chapters = Chapter.objects.filter(course__in=[music, art])
                affected = Question.objects.filter(chapter__in=chapters).count()
                self.stdout.write(self.style.WARNING(
                    f"将删除章节 {chapters.count()} 个，影响题目 {affected} 条（题目 chapter 会置空，不删题目）"
                ))
                raise CommandError("--reset 必须同时传 --yes 确认（上面列出了将被删除的数量）")
            self._reset_chapters(music, art)

        m_top, m_units = self._build_curriculum(music, MUSIC_CURRICULUM)
        a_top, a_units = self._build_curriculum(art, ART_CURRICULUM)
        self.stdout.write(self.style.SUCCESS("章节构建完成："))
        self.stdout.write(f"  音乐：{m_top} 个顶层学期章节 + {m_units} 个单元子章节 = {m_top + m_units} 个节点")
        self.stdout.write(f"  美术：{a_top} 个顶层学期章节 + {a_units} 个单元子章节 = {a_top + a_units} 个节点")

        if skip_publish:
            self.stdout.write("跳过课程发布（--skip-publish）。")
        else:
            self._publish_all(music, art)

        self._verify_luoyuxin(music, art)
