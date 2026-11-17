"""初始化演示数据（幂等）：账号 + 组织 + 班级 + 题库（音乐/美术各 20+ 道，覆盖全题型/难度/年级）+ 已发布试卷。

运行：python manage.py seed_demo
"""
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
from apps.exam.models import Paper, PaperPublish, PaperQuestion
from apps.org.models import Region, School
from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User


class Command(BaseCommand):
    help = "初始化演示数据：账号/组织/班级 + 音乐/美术题库（各 20+ 道）+ 已发布试卷。"

    @transaction.atomic
    def handle(self, *args, **options):
        # ── 1) 行政区 → 学校 → 班级 ──
        province, _ = Region.objects.get_or_create(
            code="510000", defaults={"name": "四川省", "level": Region.LEVEL_PROVINCE},
        )
        city, _ = Region.objects.get_or_create(
            code="510100", defaults={"name": "成都市", "level": Region.LEVEL_CITY, "parent": province},
        )
        district, _ = Region.objects.get_or_create(
            code="510104", defaults={"name": "锦江区", "level": Region.LEVEL_DISTRICT, "parent": city},
        )
        school, _ = School.objects.get_or_create(
            code="SCH001", defaults={"name": "测试小学", "region": district},
        )
        klass3, _ = ClassRoom.objects.get_or_create(
            code="CLS003", defaults={"name": "三年级一班", "grade": "三年级", "school": school},
        )
        klass5, _ = ClassRoom.objects.get_or_create(
            code="CLS005", defaults={"name": "五年级二班", "grade": "五年级", "school": school},
        )

        # ── 2) 各角色账号（幂等，重复运行会重置角色与密码）──
        def make_user(username, role, real_name, password, **extra):
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
            user.role = role
            user.real_name = real_name
            for key, value in extra.items():
                setattr(user, key, value)
            user.is_active = True
            user.set_password(password)
            user.save()
            return user

        admin = make_user("admin", User.ROLE_QB_ADMIN, "题库管理员", "admin123456")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        teacher = make_user(
            "teacher", User.ROLE_TEACHER, "李老师", "teacher123456",
            school=school, region=district,
        )
        student3 = make_user(
            "student", User.ROLE_STUDENT, "小明", "student123456",
            school=school, region=district, student_no="S2024001",
        )
        student5 = make_user(
            "student5", User.ROLE_STUDENT, "小红", "student123456",
            school=school, region=district, student_no="S2024005",
        )
        make_user("school", User.ROLE_SCHOOL, "校管理员", "school123456", school=school, region=district)
        make_user("district", User.ROLE_DISTRICT, "区县管理员", "district123456", region=district)
        make_user("city", User.ROLE_CITY, "市州管理员", "city123456", region=city)
        make_user("province", User.ROLE_PROVINCE, "省级管理员", "province123456", region=province)

        # ── 3) 学生加入班级（已通过审核）──
        ClassStudent.objects.get_or_create(klass=klass3, student=student3, defaults={"status": APPROVED})
        ClassStudent.objects.get_or_create(klass=klass5, student=student5, defaults={"status": APPROVED})

        # ── 4) 课程 + 章节 ──
        music, _ = Course.objects.get_or_create(code="music", defaults={"name": "音乐"})
        art, _ = Course.objects.get_or_create(code="art", defaults={"name": "美术"})

        music_ch1, _ = Chapter.objects.get_or_create(course=music, name="乐理基础", defaults={"sort": 1})
        music_ch2, _ = Chapter.objects.get_or_create(course=music, name="视唱练耳", defaults={"sort": 2})
        music_ch3, _ = Chapter.objects.get_or_create(course=music, name="乐器认知", defaults={"sort": 3})
        art_ch1, _ = Chapter.objects.get_or_create(course=art, name="色彩基础", defaults={"sort": 1})
        art_ch2, _ = Chapter.objects.get_or_create(course=art, name="素描入门", defaults={"sort": 2})
        art_ch3, _ = Chapter.objects.get_or_create(course=art, name="中国画", defaults={"sort": 3})

        # ── 5) 扩充题库 ──
        # 格式：(course, chapter, qtype, difficulty, grade, stem, options, answer, analysis, score)
        _MUSIC_QUESTIONS = [
            # ── 三年级 easy ──
            (music, music_ch1, "single", "easy", "三年级", "五线谱共有几条线？",
             [{"key": "A", "text": "三条"}, {"key": "B", "text": "四条"}, {"key": "C", "text": "五条"}, {"key": "D", "text": "六条"}],
             "C", "五线谱由五条平行线组成。", 2),
            (music, music_ch1, "judge", "easy", "三年级", "升记号 # 表示将音升高半音。",
             [], "正确", "# 为升记号，表示升高半音。", 1),
            (music, music_ch1, "single", "easy", "三年级", "高音谱号又叫什么？",
             [{"key": "A", "text": "F 谱号"}, {"key": "B", "text": "G 谱号"}, {"key": "C", "text": "低音谱号"}, {"key": "D", "text": "中音谱号"}],
             "B", "高音谱号也叫 G 谱号，因为它起始于第二线（G 音）。", 2),
            (music, music_ch1, "fill", "easy", "三年级", "do re mi 三个音中，____ 是中央 C。",
             [], "do", "do 对应中央 C。", 2),
            (music, music_ch2, "judge", "easy", "三年级", "do 和 re 之间是全音关系。",
             [], "正确", "do-re、re-mi 之间为全音。", 1),
            (music, music_ch2, "single", "easy", "三年级", "下列哪个是八分休止符？",
             [{"key": "A", "text": "𝄾"}, {"key": "B", "text": "𝄿"}, {"key": "C", "text": "𝅃"}, {"key": "D", "text": "♪"}],
             "A", "八分休止符为 𝄾。", 2),

            # ── 三年级 medium ──
            (music, music_ch1, "single", "medium", "三年级", "下列哪个是全音符？",
             [{"key": "A", "text": "♩"}, {"key": "B", "text": "♪"}, {"key": "C", "text": "𝅝"}, {"key": "D", "text": "𝅗𝅥"}],
             "C", "全音符是空心椭圆且不带符杆。", 2),
            (music, music_ch1, "multiple", "medium", "三年级", "以下哪些属于西洋管弦乐器的木管组？",
             [{"key": "A", "text": "长笛"}, {"key": "B", "text": "双簧管"}, {"key": "C", "text": "小提琴"}, {"key": "D", "text": "单簧管"}],
             "ABD", "长笛、双簧管、单簧管属木管组，小提琴属弦乐组。", 3),
            (music, music_ch2, "fill", "medium", "三年级", "国际标准音 A4 的频率为 ____ Hz。",
             [], "440", "国际标准音 A4 = 440Hz。", 2),
            (music, music_ch3, "multiple", "medium", "三年级", "下列哪些是中国民族乐器？",
             [{"key": "A", "text": "二胡"}, {"key": "B", "text": "钢琴"}, {"key": "C", "text": "古筝"}, {"key": "D", "text": "琵琶"}],
             "ACD", "二胡、古筝、琵琶是中国民族乐器，钢琴是西洋乐器。", 3),

            # ── 三年级 hard ──
            (music, music_ch1, "single", "hard", "三年级", "在一个八度内，半音共有多少个？",
             [{"key": "A", "text": "7"}, {"key": "B", "text": "8"}, {"key": "C", "text": "11"}, {"key": "D", "text": "12"}],
             "D", "一个八度内有 12 个半音。", 2),
            (music, music_ch1, "judge", "hard", "三年级", "E-F 之间是半音关系。",
             [], "正确", "E-F、B-C 之间为半音关系。", 1),

            # ── 五年级 easy ──
            (music, music_ch1, "single", "easy", "五年级", "标准音 a1 的频率是多少 Hz？",
             [{"key": "A", "text": "220"}, {"key": "B", "text": "440"}, {"key": "C", "text": "880"}, {"key": "D", "text": "110"}],
             "B", "国际标准音 a1 = 440Hz。", 2),
            (music, music_ch1, "judge", "easy", "五年级", "大调式的第一级音叫主音。",
             [], "正确", "主音是调式的核心音，为第一级。", 1),
            (music, music_ch2, "single", "easy", "五年级", "四分音符的时值相当于几个八分音符？",
             [{"key": "A", "text": "1个"}, {"key": "B", "text": "2个"}, {"key": "C", "text": "3个"}, {"key": "D", "text": "4个"}],
             "B", "四分音符 = 2 个八分音符。", 2),
            (music, music_ch3, "fill", "easy", "五年级", "钢琴共有 ____ 个琴键。",
             [], "88", "标准钢琴有 88 个琴键。", 2),

            # ── 五年级 medium ──
            (music, music_ch1, "single", "medium", "五年级", "下列哪个调式没有升降号？",
             [{"key": "A", "text": "G 大调"}, {"key": "B", "text": "F 大调"}, {"key": "C", "text": "C 大调"}, {"key": "D", "text": "D 大调"}],
             "C", "C 大调无升降号。", 2),
            (music, music_ch1, "multiple", "medium", "五年级", "下列哪些属于西洋乐器？",
             [{"key": "A", "text": "小提琴"}, {"key": "B", "text": "二胡"}, {"key": "C", "text": "钢琴"}, {"key": "D", "text": "长笛"}],
             "ACD", "小提琴、钢琴、长笛是西洋乐器。", 3),
            (music, music_ch2, "fill", "medium", "五年级", "C 大调音阶中的唱名依次是 do re mi fa ____ la si。",
             [], "sol", "C 大调音阶：do re mi fa sol la si。", 2),
            (music, music_ch3, "judge", "medium", "五年级", "大提琴属于弦乐器家族。",
             [], "正确", "大提琴、小提琴、中提琴都属弦乐家族。", 1),

            # ── 五年级 hard ──
            (music, music_ch1, "single", "hard", "五年级", "小三和弦的音程结构是？",
             [{"key": "A", "text": "大三度 + 小三度"}, {"key": "B", "text": "小三度 + 大三度"}, {"key": "C", "text": "大三度 + 大三度"}, {"key": "D", "text": "小三度 + 小三度"}],
             "B", "小三和弦 = 小三度 + 大三度。", 2),
            (music, music_ch1, "multiple", "hard", "五年级", "以下哪些是复拍子？",
             [{"key": "A", "text": "2/4 拍"}, {"key": "B", "text": "6/8 拍"}, {"key": "C", "text": "3/4 拍"}, {"key": "D", "text": "4/4 拍"}],
             "BD", "6/8 和 4/4 是复拍子。", 3),
            (music, music_ch2, "fill", "hard", "五年级", "纯五度包含 ____ 个半音。",
             [], "7", "纯五度 = 7 个半音。", 2),
        ]

        _ART_QUESTIONS = [
            # ── 三年级 easy ──
            (art, art_ch1, "single", "easy", "三年级", "美术中的三原色是指？",
             [{"key": "A", "text": "红黄蓝"}, {"key": "B", "text": "红绿蓝"}, {"key": "C", "text": "青品黄"}, {"key": "D", "text": "黑白灰"}],
             "A", "美术三原色为红、黄、蓝。", 2),
            (art, art_ch1, "judge", "easy", "三年级", "红和黄混合可以得到橙色。",
             [], "正确", "红 + 黄 = 橙。", 1),
            (art, art_ch1, "single", "easy", "三年级", "下列哪个属于暖色？",
             [{"key": "A", "text": "蓝色"}, {"key": "B", "text": "绿色"}, {"key": "C", "text": "红色"}, {"key": "D", "text": "紫色"}],
             "C", "红、橙、黄为暖色。", 2),
            (art, art_ch2, "fill", "easy", "三年级", "素描的基本明暗关系有亮面、暗面和 ____。",
             [], "灰面", "素描三大面：亮面、灰面、暗面。", 2),
            (art, art_ch2, "judge", "easy", "三年级", "HB 铅笔中 H 表示硬度，B 表示黑度。",
             [], "正确", "H（Hard）硬度，B（Black）黑度。", 1),
            (art, art_ch3, "single", "easy", "三年级", "中国画的主要工具是？",
             [{"key": "A", "text": "铅笔"}, {"key": "B", "text": "毛笔"}, {"key": "C", "text": "油画笔"}, {"key": "D", "text": "马克笔"}],
             "B", "中国画以毛笔为主要工具。", 2),

            # ── 三年级 medium ──
            (art, art_ch1, "single", "medium", "三年级", "暖色调通常给人什么样的感觉？",
             [{"key": "A", "text": "寒冷"}, {"key": "B", "text": "温暖"}, {"key": "C", "text": "平静"}, {"key": "D", "text": "忧郁"}],
             "B", "暖色调（红橙黄）给人温暖、热烈的感觉。", 2),
            (art, art_ch1, "multiple", "medium", "三年级", "以下哪些颜色属于冷色？",
             [{"key": "A", "text": "蓝"}, {"key": "B", "text": "绿"}, {"key": "C", "text": "红"}, {"key": "D", "text": "紫"}],
             "AB", "蓝、绿为冷色，红为暖色。", 3),
            (art, art_ch2, "fill", "medium", "三年级", "色彩三要素是色相、明度和 ____。",
             [], "纯度", "色彩三要素：色相、明度、纯度。", 2),
            (art, art_ch3, "judge", "medium", "三年级", "中国画讲究「留白」。",
             [], "正确", "留白是中国画重要的构图手法。", 1),

            # ── 三年级 hard ──
            (art, art_ch1, "single", "hard", "三年级", "互补色在色环上相距多少度？",
             [{"key": "A", "text": "60°"}, {"key": "B", "text": "90°"}, {"key": "C", "text": "120°"}, {"key": "D", "text": "180°"}],
             "D", "互补色相距 180°。", 2),
            (art, art_ch1, "multiple", "hard", "三年级", "以下哪些是间色？",
             [{"key": "A", "text": "橙"}, {"key": "B", "text": "绿"}, {"key": "C", "text": "红"}, {"key": "D", "text": "紫"}],
             "ABD", "橙、绿、紫是三原色两两混合得到的间色。", 3),

            # ── 五年级 easy ──
            (art, art_ch1, "single", "easy", "五年级", "下列哪个属于色彩三原色？",
             [{"key": "A", "text": "橙"}, {"key": "B", "text": "绿"}, {"key": "C", "text": "蓝"}, {"key": "D", "text": "紫"}],
             "C", "色彩三原色：红、黄、蓝。", 2),
            (art, art_ch2, "single", "easy", "五年级", "素描中最基本的形体是？",
             [{"key": "A", "text": "圆柱体"}, {"key": "B", "text": "球体"}, {"key": "C", "text": "立方体"}, {"key": "D", "text": "以上都是"}],
             "D", "球体、立方体、圆柱体是素描三大基本形体。", 2),
            (art, art_ch2, "judge", "easy", "五年级", "近大远小是透视的基本规律。",
             [], "正确", "近大远小是线性透视的基本规律。", 1),
            (art, art_ch3, "fill", "easy", "五年级", "「文房四宝」是笔、墨、纸和 ____。",
             [], "砚", "文房四宝：笔、墨、纸、砚。", 2),

            # ── 五年级 medium ──
            (art, art_ch1, "single", "medium", "五年级", "明度最高的颜色是？",
             [{"key": "A", "text": "黑色"}, {"key": "B", "text": "白色"}, {"key": "C", "text": "红色"}, {"key": "D", "text": "蓝色"}],
             "B", "白色明度最高，黑色明度最低。", 2),
            (art, art_ch1, "multiple", "medium", "五年级", "以下哪些属于对比色搭配？",
             [{"key": "A", "text": "红与绿"}, {"key": "B", "text": "蓝与橙"}, {"key": "C", "text": "黄与紫"}, {"key": "D", "text": "红与橙"}],
             "ABC", "红-绿、蓝-橙、黄-紫是三对互补对比色。", 3),
            (art, art_ch2, "fill", "medium", "五年级", "视平线与地平面的交点叫 ____。",
             [], "消失点", "消失点是透视中平行线汇聚的点。", 2),
            (art, art_ch3, "judge", "medium", "五年级", "《清明上河图》是宋代画家张择端的作品。",
             [], "正确", "《清明上河图》为北宋张择端所绘。", 1),

            # ── 五年级 hard ──
            (art, art_ch1, "single", "hard", "五年级", "颜色的纯度是指？",
             [{"key": "A", "text": "颜色的明暗程度"}, {"key": "B", "text": "颜色的鲜艳程度"}, {"key": "C", "text": "颜色的种类"}, {"key": "D", "text": "颜色的面积"}],
             "B", "纯度（饱和度）指颜色的鲜艳程度。", 2),
            (art, art_ch2, "multiple", "hard", "五年级", "以下哪些属于西方绘画技法？",
             [{"key": "A", "text": "点彩法"}, {"key": "B", "text": "泼墨法"}, {"key": "C", "text": "厚涂法"}, {"key": "D", "text": "留白法"}],
             "AC", "点彩法、厚涂法是西方油画技法。", 3),
            (art, art_ch3, "fill", "hard", "五年级", "中国画按题材可分为人物画、山水画和 ____。",
             [], "花鸟画", "中国画三大题材：人物、山水、花鸟。", 2),
        ]

        all_questions = _MUSIC_QUESTIONS + _ART_QUESTIONS
        created = 0
        for spec in all_questions:
            course, chapter, qtype, difficulty, grade, stem, opts, answer, analysis, score = spec
            _, is_new = Question.objects.get_or_create(
                course=course, chapter=chapter, qtype=qtype, difficulty=difficulty, grade=grade, stem=stem,
                defaults={
                    "options": opts,
                    "answer": answer,
                    "analysis": analysis,
                    "score": Decimal(str(score)),
                    "status": Question.STATUS_APPROVED,
                    "creator": admin,
                    "reviewer": admin,
                },
            )
            created += int(is_new)

        # ── 6) 正式测评试卷 ──
        paper, _ = Paper.objects.get_or_create(
            title="三年级音乐正式测评",
            defaults={
                "ptype": Paper.TYPE_FORMAL,
                "subject": Paper.SUBJECT_MUSIC,
                "level": Paper.LEVEL_CLASS,
                "grade": "三年级",
                "duration": 30,
                "total_score": Decimal("20"),
                "status": Paper.STATUS_PUBLISHED,
                "creator": admin,
            },
        )
        music_paper_qs = Question.objects.filter(
            course=music, status=Question.STATUS_APPROVED, grade="三年级",
        ).order_by("id")[:4]
        for index, question in enumerate(music_paper_qs):
            PaperQuestion.objects.get_or_create(
                paper=paper, question=question, defaults={"sort": index + 1, "score": Decimal("5")},
            )

        publish, _ = PaperPublish.objects.get_or_create(
            paper=paper,
            scope_type=PaperPublish.SCOPE_CLASS,
            defaults={"target_class": klass3, "target_school": school, "status": PaperPublish.STATUS_PUBLISHED},
        )
        publish.target_class = klass3
        publish.target_school = school
        publish.status = PaperPublish.STATUS_PUBLISHED
        publish.save()

        # ── 7) 输出 ──
        total = Question.objects.filter(status=Question.STATUS_APPROVED).count()
        self.stdout.write(self.style.SUCCESS("演示数据初始化完成。"))
        self.stdout.write(f"  题库：已审核共 {total} 道（新增 {created}）")
        self.stdout.write(f"    音乐：{Question.objects.filter(course=music, status='approved').count()} 道")
        self.stdout.write(f"    美术：{Question.objects.filter(course=art, status='approved').count()} 道")
        self.stdout.write("  账号（角色 · 密码）：")
        self.stdout.write("    admin    / admin123456    （超级用户 · 题库管理员）")
        self.stdout.write("    teacher  / teacher123456  （教师）")
        self.stdout.write("    student  / student123456  （学生·三年级一班）")
        self.stdout.write("    student5 / student123456  （学生·五年级二班）")
